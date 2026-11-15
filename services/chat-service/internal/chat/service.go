package chat

import (
	"context"
	"fmt"
	"strings"
)

// MembershipChecker will be implemented by an HTTP client of Room Service.
type MembershipChecker interface {
	CheckMembership(ctx context.Context, roomID, sessionToken string) (Membership, error)
}

type MessageRepository interface {
	// Append must atomically assign the room sequence, save the message and
	// record the command result. Retries return the original message.
	Append(ctx context.Context, message NewMessage) (SendResult, error)
}

type Service struct {
	memberships MembershipChecker
	messages    MessageRepository
}

func NewService(memberships MembershipChecker, messages MessageRepository) *Service {
	return &Service{memberships: memberships, messages: messages}
}

func (s *Service) SendMessage(ctx context.Context, command SendCommand) (SendResult, error) {
	if err := ctx.Err(); err != nil {
		return SendResult{}, err
	}
	if err := validate(command); err != nil {
		return SendResult{}, err
	}

	membership, err := s.memberships.CheckMembership(ctx, command.RoomID, command.SessionToken)
	if err != nil {
		return SendResult{}, err
	}
	if membership.RoomID != command.RoomID || membership.UserID != command.UserID {
		return SendResult{}, ErrForbidden
	}

	return s.messages.Append(ctx, NewMessage{
		RoomID:    membership.RoomID,
		UserID:    membership.UserID,
		CommandID: command.CommandID,
		Text:      command.Text,
	})
}

func validate(command SendCommand) error {
	if strings.TrimSpace(command.SessionToken) == "" {
		return ErrUnauthorized
	}
	if strings.TrimSpace(command.RoomID) == "" ||
		strings.TrimSpace(command.UserID) == "" ||
		strings.TrimSpace(command.CommandID) == "" ||
		strings.TrimSpace(command.Text) == "" {
		return fmt.Errorf("%w: room ID, user ID, command ID and text are required", ErrInvalidCommand)
	}
	return nil
}
