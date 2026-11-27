// Gateway transport only. UI and demo behaviour live in chat-widget.js.
// There is intentionally no invented gap-recovery endpoint.
export class ChatClient extends EventTarget {
  constructor() {
    super();
    this.socket = null;
    this.pending = null;
    this.baseline = null;
    this.cursor = 0;
    this.buffer = new Map();
    this.stopped = true;
    this.reconnectAttempt = 0;
  }

  emit(type, detail) { this.dispatchEvent(new CustomEvent(type, {detail})); }

  connect(url, token) {
    const parsed = new URL(url);
    if (!["ws:", "wss:"].includes(parsed.protocol) || parsed.username || parsed.password || parsed.search || parsed.hash) {
      throw new Error("Нужен адрес ws:// или wss:// без токена в URL.");
    }
    if (!token.trim() || /\s/.test(token)) throw new Error("Введи действительный токен без пробелов.");
    this.disconnect();
    this.url = parsed.href;
    this.token = token;
    this.pending = null;
    this.reconnectAttempt = 0;
    this.stopped = false;
    this.open();
  }

  disconnect() {
    this.stopped = true;
    clearTimeout(this.reconnectTimer);
    clearTimeout(this.initialTimer);
    clearTimeout(this.retryTimer);
    clearInterval(this.pollTimer);
    const socket = this.socket;
    this.socket = null;
    if (socket) socket.close();
    this.token = "";
    this.emit("status", {state: "offline", label: "Не подключено"});
  }

  open() {
    if (this.stopped) return;
    this.baseline = null;
    this.buffer.clear();
    this.gap = false;
    this.emit("status", {state: "connecting", label: "Подключение…"});
    let socket;
    try { socket = new WebSocket(this.url); }
    catch (_) {
      this.emit("notice", "Не удалось открыть WebSocket. Проверь адрес Gateway.");
      this.disconnect();
      return;
    }
    this.socket = socket;
    socket.onopen = () => {
      if (this.socket !== socket) return;
      this.transmit({type: "getState", payload: {}});
      this.initialTimer = setTimeout(() => {
        if (this.baseline === null) this.emit("notice", "Gateway не передал initialMessageSeq. Ожидаем начальный номер чата.");
      }, 7000);
    };
    socket.onmessage = event => {
      if (this.socket !== socket) return;
      let data;
      try { data = JSON.parse(event.data); }
      catch (_) { this.emit("notice", "Gateway вернул сообщение не в формате JSON."); return; }
      if (!data || typeof data !== "object") return;
      if (data.type === "pig") {
        socket.send(JSON.stringify({type: "pong", pigId: data.pigId}));
        return;
      }
      this.receive(data);
    };
    socket.onerror = () => {
      if (this.socket === socket) this.emit("notice", "Нет связи с Gateway. Проверь адрес, доступность и разрешённый Origin.");
    };
    socket.onclose = () => {
      if (this.socket !== socket || this.stopped) return;
      clearTimeout(this.initialTimer);
      clearTimeout(this.retryTimer);
      clearInterval(this.pollTimer);
      this.emit("status", {state: "offline", label: "Переподключение…"});
      const delay = Math.min(1000 * 2 ** this.reconnectAttempt++, 10000);
      this.reconnectTimer = setTimeout(() => this.open(), delay);
    };
  }

  transmit(message) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return false;
    this.socket.send(JSON.stringify({...message, token: this.token}));
    return true;
  }

  receive(data) {
    if (data.type === "sendState") {
      if (data.state) this.emit("participants", data.state.participants || []);
      if (this.baseline === null && Number.isSafeInteger(data.initialMessageSeq) && data.initialMessageSeq >= 0) {
        this.baseline = data.initialMessageSeq;
        this.cursor = this.baseline;
        clearTimeout(this.initialTimer);
        this.emit("status", {state: "online", label: "В сети"});
        if (this.reconnectAttempt > 0) this.emit("notice", "Соединение восстановлено. История за время отключения не загружается.");
        this.reconnectAttempt = 0;
        this.emit("baseline", this.baseline);
        this.flush();
        this.retry();
        clearInterval(this.pollTimer);
        this.pollTimer = setInterval(() => this.transmit({type: "getChatSeq", payload: {}}), 15000);
      }
    } else if (data.type === "sendMessage") {
      this.accept(data.message);
    } else if (data.type === "commandConfirm") {
      if (data.error) {
        const code = data.error.code;
        this.emit("notice", this.errorText(code));
        if (code === "unauthorized" || code === "wrong_room" || code === "room_closed") {
          this.disconnect();
        }
        if (this.pending && data.commandId === this.pending.command.commandId) {
          clearTimeout(this.retryTimer);
          if (["room_service_unavailable", "storage_unavailable", "room_service_timeout", "request_timeout"].includes(code)) {
            this.scheduleRetry();
          } else {
            const text = this.pending.command.payload.text;
            this.pending = null;
            this.emit("rejected", text);
            this.emit("pending", null);
          }
        }
        return;
      }
      if (data.message) {
        if (this.pending && data.commandId === this.pending.command.commandId) {
          this.pending.confirmed = true;
          this.pending.seq = data.message.messageSeq;
          this.emit("self", data.message.participant_id);
        }
        this.accept(data.message);
        this.completePending();
      } else if (Number.isSafeInteger(data.messageSeq) && this.baseline !== null && data.messageSeq > this.cursor) {
        this.reportGap();
      }
    }
  }

  accept(message) {
    if (!message || typeof message.message_id !== "string" || typeof message.participant_id !== "string" ||
        typeof message.text !== "string" || !Number.isSafeInteger(message.messageSeq) || message.messageSeq < 1) return;
    if (this.baseline !== null && message.messageSeq <= this.cursor) return;
    if (this.buffer.size >= 500 && !this.buffer.has(message.messageSeq)) {
      this.emit("notice", "Слишком много пропущенных сообщений. Переподключись, чтобы начать с актуального номера.");
      return;
    }
    this.buffer.set(message.messageSeq, message);
    this.flush();
  }

  flush() {
    if (this.baseline === null) return;
    for (const seq of this.buffer.keys()) if (seq <= this.cursor) this.buffer.delete(seq);
    while (this.buffer.has(this.cursor + 1)) {
      const message = this.buffer.get(++this.cursor);
      this.buffer.delete(this.cursor);
      this.emit("message", message);
    }
    this.completePending();
    if (this.buffer.size) this.reportGap();
    else if (this.gap) {
      this.gap = false;
      this.emit("gapresolved");
    }
  }

  reportGap() {
    this.gap = true;
    this.emit("notice", `Ожидаем сообщение №${this.cursor + 1}. Автоматическое восстановление пропусков ещё не подключено.`);
  }

  send(text) {
    if (this.baseline === null || !this.socket || this.socket.readyState !== WebSocket.OPEN) {
      throw new Error("Сначала подключись к комнате и дождись начального номера чата.");
    }
    if (this.pending) throw new Error("Предыдущее сообщение ещё ожидает подтверждения и своего места в ленте.");
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    const id = Array.from(bytes, value => value.toString(16).padStart(2, "0")).join("");
    this.pending = {command: {type: "sendMessage", commandId: "web-" + id, payload: {text}}, confirmed: false};
    this.emit("pending", text);
    this.retry();
  }

  retry() {
    if (!this.pending || this.baseline === null || this.stopped) return;
    if (this.transmit(this.pending.command)) this.scheduleRetry();
  }

  scheduleRetry() {
    clearTimeout(this.retryTimer);
    if (this.stopped) return;
    this.retryTimer = setTimeout(() => this.retry(), 6000);
  }

  completePending() {
    if (this.baseline !== null && this.pending && this.pending.confirmed && this.pending.seq <= this.cursor) {
      this.pending = null;
      clearTimeout(this.retryTimer);
      this.emit("pending", null);
    }
  }

  errorText(code) {
    return ({unauthorized: "Недействительный токен. Подключись с токеном участника комнаты.",
      wrong_room: "Токен принадлежит другой комнате.", room_closed: "Комната закрыта.",
      command_id_conflict: "Этот ID команды уже использован с другим текстом.",
      invalid_payload: "Сервер не принял сообщение. Проверь его содержимое.",
      room_service_unavailable: "Room Service временно недоступен. Отправка будет повторена.",
      storage_unavailable: "База чата временно недоступна. Отправка будет повторена.",
      room_service_timeout: "Проверка участника заняла слишком много времени.",
      request_timeout: "Сервер не подтвердил сообщение вовремя. Повторяем с прежним ID."})[code] || "Gateway отклонил запрос. Проверь согласованный протокол.";
  }
}
