package chat

import "errors"

var (
	ErrInvalidCommand    = errors.New("invalid message command")
	ErrUnauthorized      = errors.New("invalid session")
	ErrForbidden         = errors.New("sender is not a member of this room")
	ErrCommandIDConflict = errors.New("command ID was already used with different content")
)
