import {ChatClient} from "./chat-client.js";

const icons = {
  chat: '<svg viewBox="0 0 24 24" fill="none"><path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H5l-3 3V11.5A9 9 0 0 1 11 2h1.5a7.5 7.5 0 0 1 7.5 7.5Z"/><path d="M7 9h8M7 13h5"/></svg>',
  settings: '<svg viewBox="0 0 24 24" fill="none"><path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="15" cy="17" r="3"/></svg>',
  users: '<svg viewBox="0 0 24 24" fill="none"><circle cx="9" cy="8" r="3"/><path d="M3 20v-2a6 6 0 0 1 12 0v2M16 5a3 3 0 0 1 0 6M21 20v-2a6 6 0 0 0-3-5"/></svg>',
  sticker: '<svg viewBox="0 0 24 24" fill="none"><path d="M20 13V6a3 3 0 0 0-3-3H6a3 3 0 0 0-3 3v11a3 3 0 0 0 3 3h7Z"/><path d="M13 20v-4a3 3 0 0 1 3-3h4M7 10h.01M13 10h.01M7 14a4 4 0 0 0 4 1"/></svg>',
  send: '<svg viewBox="0 0 24 24" fill="none"><path d="m12 19 0-14M6 11l6-6 6 6"/></svg>',
  down: '<svg viewBox="0 0 24 24" fill="none"><path d="M12 5v14M6 13l6 6 6-6"/></svg>',
  close: '<svg viewBox="0 0 24 24" fill="none"><path d="m6 6 12 12M18 6 6 18"/></svg>'
};

export class PlotinaChat extends HTMLElement {
  constructor() {
    super();
    const root = this.attachShadow({mode: "open"});
    root.innerHTML = `
      <link rel="stylesheet" href="${new URL("./chat-widget.css", import.meta.url).href}">
      <section class="chat" aria-label="Чат комнаты">
        <header class="header">
          <div class="heading-icon">${icons.chat}</div>
          <div class="heading"><h2>Чат комнаты</h2><span class="status"><i></i><span>Не подключено</span></span></div>
          <span class="live-badge">LIVE</span>
          <button class="icon-button settings-button" type="button" aria-label="Настройки подключения" aria-expanded="false" title="Настройки подключения">${icons.settings}</button>
        </header>
        <form class="connection" hidden>
          <div class="connection-title">Подключение к комнате <button type="button" class="close-settings icon-button" aria-label="Закрыть настройки">${icons.close}</button></div>
          <label>WebSocket Gateway<input name="gateway" type="url" placeholder="ws://127.0.0.1:8080/ws" value="ws://127.0.0.1:8080/ws" required></label>
          <label>Токен участника<input name="token" type="password" autocomplete="off" placeholder="Токен из Room Service" required></label>
          <p>Токен хранится только в памяти этой вкладки.</p>
          <div class="connection-actions"><button type="button" class="demo-button">Деморежим</button><button class="connect-button" type="submit">Подключиться</button></div>
        </form>
        <div class="room-bar"><span class="room-label">Обсуждаем вместе</span><span class="members" title="Количество участников">${icons.users}<span>—</span></span></div>
        <div class="feed-stage">
          <div class="feed" role="log" aria-label="Сообщения чата" aria-live="polite" aria-relevant="additions" tabindex="0">
            <div class="day"><span>Сегодня</span></div>
            <div class="welcome"><div class="welcome-icon">${icons.chat}</div><strong>Начнём разговор?</strong><span>Поделись впечатлениями от просмотра.</span></div>
            <div class="messages"></div>
          </div>
          <button class="new-messages" type="button" hidden>${icons.down}<span>Новые сообщения</span></button>
        </div>
        <div class="notice" role="status" hidden><span></span><button type="button" class="icon-button" aria-label="Скрыть уведомление">${icons.close}</button></div>
        <div class="pending" role="status" hidden><span class="pending-dot"></span><span>Ожидает подтверждения</span><span class="pending-text"></span></div>
        <form class="composer">
          <div class="input-wrap"><textarea name="message" aria-label="Сообщение" placeholder="Написать сообщение…" rows="1" disabled></textarea></div>
          <div class="composer-bottom"><button class="sticker-button" type="button" aria-label="Стикеры — скоро" title="Стикеры — скоро">${icons.sticker}<span>Стикеры</span><span class="soon">скоро</span></button><span class="enter-hint">Enter ↵</span><button class="send-button" type="submit" aria-label="Отправить сообщение" disabled>${icons.send}</button></div>
        </form>
        <div class="footer"><span class="mode-label">Чат комнаты</span><span>Будьте добрее друг к другу <span class="heart">♡</span></span></div>
      </section>`;
    this.$ = selector => root.querySelector(selector);
    this.names = new Map();
    this.client = new ChatClient();
    this.mode = "offline";
    this.online = false;
    this.atBottom = true;
    this.unread = 0;
    this.demoSeq = 0;
    this.bindUI();
    this.bindClient();
  }

  bindUI() {
    this.$(".settings-button").addEventListener("click", () => this.toggleSettings());
    this.$(".close-settings").addEventListener("click", () => this.toggleSettings(false));
    this.$(".demo-button").addEventListener("click", () => this.useDemo());
    this.$(".connection").addEventListener("submit", event => {
      event.preventDefault();
      this.connect(this.$('[name="gateway"]').value, this.$('[name="token"]').value);
    });
    this.$(".composer").addEventListener("submit", event => { event.preventDefault(); this.send(); });
    this.$('[name="message"]').addEventListener("keydown", event => {
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); this.send(); }
    });
    this.$('[name="message"]').addEventListener("input", () => this.updateComposer());
    this.$(".sticker-button").addEventListener("click", () => this.showNotice("Стикеры скоро появятся. Здесь будет выбор из готового набора."));
    this.$(".notice button").addEventListener("click", () => { this.$(".notice").hidden = true; });
    this.$(".new-messages").addEventListener("click", () => this.scrollToBottom());
    this.$(".feed").addEventListener("scroll", () => {
      const feed = this.$(".feed");
      this.atBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 40;
      if (this.atBottom) this.clearUnread();
    });
  }

  bindClient() {
    this.client.addEventListener("status", ({detail}) => {
      if (this.mode === "demo") return;
      this.online = detail.state === "online";
      this.setStatus(detail.state, detail.label);
      this.updateComposer();
    });
    this.client.addEventListener("message", ({detail}) => this.appendMessage(detail));
    this.client.addEventListener("notice", ({detail}) => this.showNotice(detail));
    this.client.addEventListener("pending", ({detail}) => {
      this.$(".pending").hidden = detail === null;
      this.$(".pending-text").textContent = detail || "";
      this.updateComposer();
    });
    this.client.addEventListener("rejected", ({detail}) => {
      if (!this.$('[name="message"]').value) this.$('[name="message"]').value = detail;
      this.updateComposer();
    });
    this.client.addEventListener("participants", ({detail}) => this.setParticipants(detail));
    this.client.addEventListener("self", ({detail}) => {
      this.selfID = detail;
      if (!this.names.has(detail)) this.names.set(detail, "Вы");
      this.refreshAuthors();
    });
    this.client.addEventListener("baseline", () => { this.$(".notice").hidden = true; });
    this.client.addEventListener("gapresolved", () => {
      if (this.$(".notice span").textContent.startsWith("Ожидаем сообщение №")) this.$(".notice").hidden = true;
    });
  }

  toggleSettings(open = this.$(".connection").hidden) {
    this.$(".connection").hidden = !open;
    this.$(".settings-button").setAttribute("aria-expanded", String(open));
    if (open) this.$('[name="gateway"]').focus();
  }

  connect(url, token, authors = {}) {
    const previousMode = this.mode;
    const previousOnline = this.online;
    this.mode = "gateway";
    this.online = false;
    try { this.client.connect(url, token); }
    catch (error) {
      this.mode = previousMode;
      this.online = previousOnline;
      this.showNotice(error.message);
      this.updateComposer();
      return;
    }
    this.names.clear();
    this.setAuthors(authors);
    this.selfID = null;
    this.resetMessages();
    this.$(".pending").hidden = true;
    this.$(".mode-label").textContent = "Комната · Gateway";
    this.$(".members span").textContent = "—";
    this.$(".notice").hidden = true;
    this.$('[name="token"]').value = "";
    this.toggleSettings(false);
    this.updateComposer();
  }

  useDemo() {
    this.mode = "demo";
    this.client.disconnect();
    this.online = true;
    this.selfID = "demo-self";
    this.demoSeq = 0;
    this.names = new Map([["demo-anna", "Аня"], ["demo-dima", "Дима"], ["demo-lena", "Лена"], ["demo-self", "Вы"]]);
    this.resetMessages();
    this.$(".pending").hidden = true;
    this.$(".notice").hidden = true;
    this.$(".mode-label").textContent = "Демо · только эта вкладка";
    this.$(".members span").textContent = "4";
    this.$('[name="token"]').value = "";
    this.toggleSettings(false);
    this.setStatus("demo", "Деморежим");
    const samples = [
      ["demo-anna", "Все на месте? Можно начинать 🎬"],
      ["demo-dima", "Да! Только чай себе налью"],
      ["demo-lena", "Я готова. Давно хотела это посмотреть"],
      ["demo-anna", "Смотрите, какой красивый первый кадр"],
      ["demo-dima", "А музыка уже нравится 👀"],
    ];
    samples.forEach(([participant_id, text], index) => this.appendMessage({
      message_id: "demo-" + index, messageSeq: ++this.demoSeq, participant_id, text,
      created_at: new Date(Date.now() - (samples.length - index) * 60000).toISOString()
    }));
    this.updateComposer();
    this.scrollToBottom();
  }

  setAuthors(authors) {
    for (const [id, name] of Object.entries(authors)) if (typeof name === "string") this.names.set(id, name);
    this.refreshAuthors();
  }

  setParticipants(participants) {
    if (!Array.isArray(participants)) return;
    this.$(".members span").textContent = String(participants.filter(item => item.connected !== false).length);
    for (const item of participants) {
      const id = item.participant_id || item.id;
      if (typeof id === "string" && typeof item.display_name === "string") this.names.set(id, item.display_name);
    }
    this.refreshAuthors();
  }

  authorName(id) { return this.names.get(id) || id; }

  refreshAuthors() {
    for (const row of this.shadowRoot.querySelectorAll(".message")) this.styleAuthor(row, row.dataset.author);
  }

  styleAuthor(row, id) {
    const name = this.authorName(id);
    const label = row.querySelector(".author");
    label.textContent = name;
    label.title = id;
    row.querySelector(".avatar").textContent = [...name].slice(0, 1).join("").toUpperCase();
    row.classList.toggle("own", id === this.selfID);
    row.querySelector(".you").hidden = id !== this.selfID || name === "Вы";
    let hash = 0;
    for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) | 0;
    row.style.setProperty("--author-hue", String([260, 165, 24, 214, 330][Math.abs(hash) % 5]));
  }

  appendMessage(message) {
    const feed = this.$(".feed");
    const follow = this.atBottom;
    const row = document.createElement("article");
    row.className = "message";
    row.dataset.author = message.participant_id;
    row.dataset.seq = String(message.messageSeq);
    // All untrusted content is assigned through textContent, never HTML.
    row.innerHTML = '<span class="avatar" aria-hidden="true"></span><div class="message-content"><div class="message-meta"><span class="author"></span><span class="you" hidden>вы</span><time></time></div><p></p></div>';
    row.querySelector("p").textContent = message.text;
    const date = new Date(message.created_at);
    const time = row.querySelector("time");
    time.textContent = Number.isNaN(date.getTime()) ? "" : date.toLocaleTimeString("ru-RU", {hour: "2-digit", minute: "2-digit"});
    time.dateTime = message.created_at || "";
    this.styleAuthor(row, message.participant_id);
    this.$(".messages").append(row);
    this.$(".welcome").hidden = true;
    const messages = this.$(".messages");
    const previousHeight = feed.scrollHeight;
    while (messages.childElementCount > 300) messages.firstElementChild.remove();
    if (follow) this.scrollToBottom();
    else {
      feed.scrollTop -= Math.max(0, previousHeight - feed.scrollHeight);
      this.unread++;
      this.$(".new-messages").hidden = false;
      this.$(".new-messages span").textContent = `Новые сообщения · ${this.unread}`;
    }
  }

  resetMessages() {
    this.$(".messages").replaceChildren();
    this.$(".welcome").hidden = false;
    this.atBottom = true;
    this.clearUnread();
  }

  scrollToBottom() {
    this.atBottom = true;
    this.clearUnread();
    requestAnimationFrame(() => { const feed = this.$(".feed"); feed.scrollTop = feed.scrollHeight; });
  }

  clearUnread() { this.unread = 0; this.$(".new-messages").hidden = true; }

  setStatus(state, label) {
    this.$(".status").dataset.state = state;
    this.$(".status span").textContent = label;
    this.$(".live-badge").classList.toggle("active", state === "online");
  }

  showNotice(text) { this.$(".notice span").textContent = text; this.$(".notice").hidden = false; }

  updateComposer() {
    const input = this.$('[name="message"]');
    input.disabled = !this.online;
    this.$(".send-button").disabled = !this.online || !input.value.trim() || (this.mode === "gateway" && Boolean(this.client.pending));
  }

  send() {
    const input = this.$('[name="message"]');
    const text = input.value;
    if (!text.trim()) return;
    if (!this.online) { this.showNotice("Сначала подключись к комнате."); return; }
    if (new Blob([JSON.stringify({command_id: "web-" + "x".repeat(32), text})]).size > 65536) {
      this.showNotice("Сообщение слишком большое: запрос должен быть меньше 64 КиБ."); return;
    }
    if (this.mode === "demo") {
      this.appendMessage({message_id: "demo-self-" + this.demoSeq, messageSeq: ++this.demoSeq,
        participant_id: this.selfID, text, created_at: new Date().toISOString()});
    } else {
      try { this.client.send(text); }
      catch (error) { this.showNotice(error.message); return; }
    }
    input.value = "";
    this.updateComposer();
    input.focus();
  }

  disconnectedCallback() { this.client.disconnect(); }
}

customElements.define("plotina-chat", PlotinaChat);
