package rooms

import (
	"context"

	"plotina/chat-service/internal/chat"
)

type FakeMembershipChecker struct {
	sessions map[string]chat.Membership
}

func NewFakeMembershipChecker(sessions map[string]chat.Membership) *FakeMembershipChecker {
	copy := make(map[string]chat.Membership, len(sessions))
	for token, membership := range sessions {
		copy[token] = membership
	}
	return &FakeMembershipChecker{sessions: copy}
}

func (f *FakeMembershipChecker) CheckMembership(ctx context.Context, roomID, sessionToken string) (chat.Membership, error) {
	if err := ctx.Err(); err != nil {
		return chat.Membership{}, err
	}
	membership, ok := f.sessions[sessionToken]
	if !ok {
		return chat.Membership{}, chat.ErrUnauthorized
	}
	if membership.RoomID != roomID {
		return chat.Membership{}, chat.ErrForbidden
	}
	return membership, nil
}
