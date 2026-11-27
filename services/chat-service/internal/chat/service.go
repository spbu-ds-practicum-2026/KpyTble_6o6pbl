package chat

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"unicode/utf8"
)

// MembershipChecker is implemented by the Room Service HTTP client and a local fake.
type MembershipChecker interface {
	CheckMembership(ctx context.Context, roomID, sessionToken string) (Membership, error)
}

type MessageRepository interface {
	// Append must atomically assign the room sequence, save the message and
	// record the command result. Retries return the original message.
	Append(ctx context.Context, message NewMessage) (SendResult, error)
	// CurrentSeq reads the last committed room sequence; an empty chat returns 0.
	CurrentSeq(ctx context.Context, roomID string) (int64, error)
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

	membership, err := s.checkMembership(ctx, command.RoomID, command.SessionToken)
	if err != nil {
		return SendResult{}, err
	}
	result, err := s.messages.Append(ctx, NewMessage{
		RoomID:        membership.RoomID,
		ParticipantID: membership.ParticipantID,
		CommandID:     command.CommandID,
		Text:          command.Text,
	})
	if err != nil && !errors.Is(err, ErrCommandIDConflict) {
		return SendResult{}, fmt.Errorf("%w: %w", ErrStorageUnavailable, err)
	}
	return result, err
}

func (s *Service) GetChatSeq(ctx context.Context, roomID, sessionToken string) (Sequence, error) {
	if err := ctx.Err(); err != nil {
		return Sequence{}, err
	}
	if strings.TrimSpace(sessionToken) == "" {
		return Sequence{}, ErrUnauthorized
	}
	if strings.TrimSpace(roomID) == "" {
		return Sequence{}, ErrInvalidCommand
	}
	if _, err := s.checkMembership(ctx, roomID, sessionToken); err != nil {
		return Sequence{}, err
	}
	seq, err := s.messages.CurrentSeq(ctx, roomID)
	if err != nil {
		return Sequence{}, fmt.Errorf("%w: %w", ErrStorageUnavailable, err)
	}
	return Sequence{MessageSeq: seq}, nil
}

func (s *Service) checkMembership(ctx context.Context, roomID, token string) (Membership, error) {
	membership, err := s.memberships.CheckMembership(ctx, roomID, token)
	if err != nil {
		return Membership{}, err
	}
	if membership.RoomID != roomID || strings.TrimSpace(membership.ParticipantID) == "" {
		return Membership{}, ErrForbidden
	}
	return membership, nil
}

func validate(command SendCommand) error {
	if strings.TrimSpace(command.SessionToken) == "" {
		return ErrUnauthorized
	}
	if strings.TrimSpace(command.RoomID) == "" ||
		strings.TrimSpace(command.CommandID) == "" ||
		strings.TrimSpace(command.Text) == "" {
		return fmt.Errorf("%w: room ID, command ID and text are required", ErrInvalidCommand)
	}
	for _, value := range []string{command.RoomID, command.CommandID, command.Text} {
		if !utf8.ValidString(value) || strings.ContainsRune(value, '\x00') {
			return fmt.Errorf("%w: invalid text encoding or null character", ErrInvalidCommand)
		}
	}
	return nil
}
