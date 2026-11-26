package httpapi

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"mime"
	"net/http"
	"strings"
	"time"
	"unicode/utf8"

	"plotina/chat-service/internal/chat"
	"plotina/chat-service/web"
)

const maxRequestSize = 64 * 1024

type ChatService interface {
	SendMessage(ctx context.Context, command chat.SendCommand) (chat.SendResult, error)
	GetChatSeq(ctx context.Context, roomID, sessionToken string) (chat.Sequence, error)
}

type handler struct {
	service ChatService
	checks  map[string]ReadinessCheck
	logger  *slog.Logger
}

// NewHandler creates the internal HTTP API of the chat service.
func NewHandler(service ChatService, options ...Option) http.Handler {
	h := &handler{service: service}
	for _, option := range options {
		option(h)
	}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", health)
	mux.HandleFunc("GET /ready", h.ready)
	mux.HandleFunc("POST /rooms/{room_id}/messages", h.sendMessage)
	mux.HandleFunc("GET /rooms/{room_id}/messages/seq", h.getChatSeq)
	mux.HandleFunc("/health", methodNotAllowed("GET, HEAD"))
	mux.HandleFunc("/ready", methodNotAllowed("GET, HEAD"))
	mux.Handle("GET /chat/", http.StripPrefix("/chat", web.Handler()))
	mux.HandleFunc("/rooms/{room_id}/messages", methodNotAllowed("POST"))
	mux.HandleFunc("/rooms/{room_id}/messages/seq", methodNotAllowed("GET, HEAD"))
	mux.HandleFunc("/", func(w http.ResponseWriter, _ *http.Request) {
		writeError(w, http.StatusNotFound, "not_found", "Маршрут не найден")
	})
	return h.diagnostics(mux)
}

func health(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte("i'm still standing\n"))
}

func (h *handler) sendMessage(w http.ResponseWriter, r *http.Request) {
	token, ok := bearerToken(w, r)
	if !ok {
		return
	}
	mediaType, _, err := mime.ParseMediaType(r.Header.Get("Content-Type"))
	if err != nil || mediaType != "application/json" {
		writeError(w, http.StatusUnsupportedMediaType, "unsupported_media_type", "Ожидается Content-Type: application/json")
		return
	}
	r.Body = http.MaxBytesReader(w, r.Body, maxRequestSize)
	raw, err := io.ReadAll(r.Body)
	if err != nil {
		invalidBody(w, err)
		return
	}
	if !utf8.Valid(raw) {
		writeError(w, http.StatusUnprocessableEntity, "invalid_payload", "Ожидается корректный текст UTF-8")
		return
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.DisallowUnknownFields()
	// Pointers distinguish missing/null fields from valid string values.
	var body struct {
		CommandID *string `json:"command_id"`
		Text      *string `json:"text"`
	}
	if err := decoder.Decode(&body); err != nil {
		invalidBody(w, err)
		return
	}
	var extra any
	if err := decoder.Decode(&extra); err != io.EOF {
		invalidBody(w, err)
		return
	}
	if body.CommandID == nil || body.Text == nil {
		writeError(w, http.StatusUnprocessableEntity, "invalid_payload", "Обязательны строковые поля command_id и text")
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()
	result, err := h.service.SendMessage(ctx, chat.SendCommand{
		RoomID: r.PathValue("room_id"), SessionToken: token,
		CommandID: *body.CommandID, Text: *body.Text,
	})
	if err != nil {
		serviceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, result)
}

func (h *handler) getChatSeq(w http.ResponseWriter, r *http.Request) {
	token, ok := bearerToken(w, r)
	if !ok {
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()
	result, err := h.service.GetChatSeq(ctx, r.PathValue("room_id"), token)
	if err != nil {
		serviceError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, result)
}

func bearerToken(w http.ResponseWriter, r *http.Request) (string, bool) {
	headers := r.Header.Values("Authorization")
	fields := strings.Fields(r.Header.Get("Authorization"))
	if len(headers) != 1 || len(fields) != 2 || !strings.EqualFold(fields[0], "Bearer") || strings.Contains(fields[1], ",") {
		writeError(w, http.StatusUnauthorized, "unauthorized", "Необходим действительный Bearer-токен")
		return "", false
	}
	return fields[1], true
}

func invalidBody(w http.ResponseWriter, err error) {
	var tooLarge *http.MaxBytesError
	if errors.As(err, &tooLarge) {
		writeError(w, http.StatusRequestEntityTooLarge, "payload_too_large", "Размер запроса превышает 64 КиБ")
		return
	}
	writeError(w, http.StatusUnprocessableEntity, "invalid_payload", "Ожидается один JSON-объект со строковыми полями command_id и text")
}

func serviceError(w http.ResponseWriter, err error) {
	switch {
	case errors.Is(err, chat.ErrUnauthorized):
		writeError(w, 401, "unauthorized", "Токен отсутствует или недействителен")
	case errors.Is(err, chat.ErrForbidden):
		writeError(w, 403, "wrong_room", "Токен не подтверждает участие в этой комнате")
	case errors.Is(err, chat.ErrRoomClosed):
		writeError(w, 409, "room_closed", "Комната закрыта")
	case errors.Is(err, chat.ErrCommandIDConflict):
		writeError(w, 409, "command_id_conflict", "Идентификатор команды уже использован с другими параметрами")
	case errors.Is(err, chat.ErrInvalidCommand):
		writeError(w, 422, "invalid_payload", "Необходимо заполнить комнату, command_id и text")
	case errors.Is(err, chat.ErrRoomServiceTimeout):
		writeError(w, 504, "room_service_timeout", "Истекло время ожидания Room Service")
	case errors.Is(err, context.DeadlineExceeded):
		writeError(w, 504, "request_timeout", "Истекло время обработки запроса; повторите действие с прежним command_id")
	case errors.Is(err, context.Canceled):
		writeError(w, 408, "request_cancelled", "Запрос отменён")
	case errors.Is(err, chat.ErrRoomServiceUnavailable):
		writeError(w, 503, "room_service_unavailable", "Room Service временно недоступен")
	case errors.Is(err, chat.ErrStorageUnavailable):
		writeError(w, 503, "storage_unavailable", "Хранилище чата временно недоступно; повторите действие с прежним command_id")
	default:
		writeError(w, 500, "internal_error", "Внутренняя ошибка сервиса")
	}
}

func methodNotAllowed(allow string) http.HandlerFunc {
	return func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Allow", allow)
		writeError(w, http.StatusMethodNotAllowed, "method_not_allowed", "Метод не поддерживается для этого маршрута")
	}
}

func writeError(w http.ResponseWriter, status int, code, message string) {
	writeJSON(w, status, map[string]any{"error": map[string]string{"code": code, "message": message}})
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}
