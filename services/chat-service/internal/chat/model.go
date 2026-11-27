package chat

import "time"

// SendCommand contains the data needed to send a message.
// RoomID comes from the URL, SessionToken from the Authorization header.
// Only CommandID and Text belong to the JSON request body.
type SendCommand struct {
	RoomID       string `json:"-"`
	SessionToken string `json:"-"`
	CommandID    string `json:"command_id"`
	Text         string `json:"text"`
}

// Membership is the identity confirmed by Room Service.
type Membership struct {
	RoomID        string `json:"room_id"`
	ParticipantID string `json:"participant_id"`
	DisplayName   string `json:"display_name"`
	Role          Role   `json:"role"`
	Connected     bool   `json:"connected"`
}

type Role string

const (
	RoleHost   Role = "host"
	RoleMember Role = "member"
)

type Message struct {
	MessageID     string    `json:"message_id"`
	RoomID        string    `json:"-"`
	ParticipantID string    `json:"participant_id"`
	Text          string    `json:"text"`
	CreatedAt     time.Time `json:"created_at"`
	MessageSeq    int64     `json:"messageSeq"`
}

// NewMessage excludes the session token: repositories must not store it.
type NewMessage struct {
	RoomID        string
	ParticipantID string
	CommandID     string
	Text          string
}

type SendResult struct {
	CommandID string  `json:"command_id"`
	Duplicate bool    `json:"duplicate"`
	Message   Message `json:"message"`
}

type Sequence struct {
	MessageSeq int64 `json:"messageSeq"`
}
