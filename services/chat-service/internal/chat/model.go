package chat

import "time"

// SendCommand contains the data needed to send a text message.
// These are internal models, not an agreed HTTP contract.
type SendCommand struct {
	RoomID       string
	UserID       string
	SessionToken string `json:"-"`
	CommandID    string
	Text         string
}

// Membership is the identity confirmed by Room Service.
type Membership struct {
	RoomID string
	UserID string
}

type Message struct {
	MessageID  string
	RoomID     string
	UserID     string
	Text       string
	SentAt     time.Time
	MessageSeq int64
}

// NewMessage excludes the session token: repositories must not store it.
type NewMessage struct {
	RoomID    string
	UserID    string
	CommandID string
	Text      string
}

type SendResult struct {
	CommandID string
	Duplicate bool
	Message   Message
}
