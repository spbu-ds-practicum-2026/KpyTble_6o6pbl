package rooms

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strings"
	"time"

	"plotina/chat-service/internal/chat"
)

const maxMembershipResponseSize = 64 * 1024

// HTTPClient checks membership using Room Service, not local session data.
type HTTPClient struct {
	baseURL *url.URL
	client  *http.Client
}

var _ chat.MembershipChecker = (*HTTPClient)(nil)

// NewHTTPClient accepts an HTTP(S) base URL and a positive timeout for the
// entire request, including reading the response body. It makes no requests.
func NewHTTPClient(baseURL string, timeout time.Duration) (*HTTPClient, error) {
	parsed, err := url.Parse(baseURL)
	if err != nil || parsed == nil || (parsed.Scheme != "http" && parsed.Scheme != "https") ||
		parsed.Hostname() == "" || parsed.User != nil || parsed.RawQuery != "" ||
		parsed.ForceQuery || parsed.Fragment != "" {
		// Do not include the provided URL: it could contain credentials.
		return nil, errors.New("invalid Room Service URL: expected HTTP(S) address without credentials, query or fragment")
	}
	if timeout <= 0 {
		return nil, errors.New("Room Service timeout must be positive")
	}
	return &HTTPClient{
		baseURL: parsed,
		client: &http.Client{
			Timeout: timeout,
			// Membership requests contain a token; never forward them on redirects.
			CheckRedirect: func(_ *http.Request, _ []*http.Request) error {
				return http.ErrUseLastResponse
			},
		},
	}, nil
}

func (c *HTTPClient) CheckMembership(ctx context.Context, roomID, sessionToken string) (chat.Membership, error) {
	if err := ctx.Err(); err != nil {
		return chat.Membership{}, err
	}
	if strings.TrimSpace(sessionToken) == "" || strings.ContainsAny(sessionToken, " \t\r\n") {
		return chat.Membership{}, chat.ErrUnauthorized
	}
	if strings.TrimSpace(roomID) == "" || roomID == "." || roomID == ".." || strings.ContainsAny(roomID, "/\\?#") {
		return chat.Membership{}, chat.ErrInvalidCommand
	}
	endpoint := *c.baseURL
	endpoint.Path = strings.TrimRight(endpoint.Path, "/") + "/internal/rooms/" + roomID + "/membership"
	endpoint.RawPath = strings.TrimRight(c.baseURL.EscapedPath(), "/") + "/internal/rooms/" + url.PathEscape(roomID) + "/membership"
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint.String(), nil)
	if err != nil {
		return chat.Membership{}, chat.ErrRoomServiceUnavailable
	}
	req.Header.Set("Authorization", "Bearer "+sessionToken)
	req.Header.Set("Accept", "application/json")
	response, err := c.client.Do(req)
	if err != nil {
		return chat.Membership{}, roomRequestError(ctx, err)
	}
	defer response.Body.Close()

	switch response.StatusCode {
	case http.StatusOK, http.StatusUnauthorized, http.StatusForbidden, http.StatusConflict:
		// Only these statuses have a supported response in the current contract.
	default:
		return chat.Membership{}, fmt.Errorf("%w: unexpected HTTP status %d", chat.ErrRoomServiceUnavailable, response.StatusCode)
	}
	body, err := io.ReadAll(io.LimitReader(response.Body, maxMembershipResponseSize+1))
	if err != nil {
		return chat.Membership{}, roomRequestError(ctx, err)
	}
	if len(body) > maxMembershipResponseSize {
		return chat.Membership{}, fmt.Errorf("%w: response is too large", chat.ErrRoomServiceUnavailable)
	}
	if response.StatusCode != http.StatusOK {
		return chat.Membership{}, membershipError(response.StatusCode, body)
	}
	var result struct {
		RoomID        string    `json:"room_id"`
		ParticipantID string    `json:"participant_id"`
		DisplayName   string    `json:"display_name"`
		Role          chat.Role `json:"role"`
		Connected     *bool     `json:"connected"`
	}
	if err := json.Unmarshal(body, &result); err != nil || result.RoomID != roomID ||
		strings.TrimSpace(result.ParticipantID) == "" || result.Connected == nil ||
		(result.Role != chat.RoleHost && result.Role != chat.RoleMember) {
		return chat.Membership{}, fmt.Errorf("%w: invalid membership response", chat.ErrRoomServiceUnavailable)
	}
	return chat.Membership{
		RoomID: result.RoomID, ParticipantID: result.ParticipantID,
		DisplayName: result.DisplayName, Role: result.Role, Connected: *result.Connected,
	}, nil
}

// CheckHealth checks availability without a participant token. Membership and
// permissions must still be checked separately for each application request.
func (c *HTTPClient) CheckHealth(ctx context.Context) error {
	endpoint := *c.baseURL
	endpoint.Path = strings.TrimRight(endpoint.Path, "/") + "/health"
	endpoint.RawPath = ""
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint.String(), nil)
	if err != nil {
		return chat.ErrRoomServiceUnavailable
	}
	req.Header.Set("Accept", "application/json")
	response, err := c.client.Do(req)
	if err != nil {
		return roomRequestError(ctx, err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return chat.ErrRoomServiceUnavailable
	}
	body, err := io.ReadAll(io.LimitReader(response.Body, maxMembershipResponseSize+1))
	if err != nil {
		return roomRequestError(ctx, err)
	}
	var health struct {
		Status string `json:"status"`
	}
	if len(body) > maxMembershipResponseSize || json.Unmarshal(body, &health) != nil || health.Status != "ok" {
		return chat.ErrRoomServiceUnavailable
	}
	return nil
}

func membershipError(status int, body []byte) error {
	var result struct {
		Error struct {
			Code string `json:"code"`
		} `json:"error"`
	}
	if err := json.Unmarshal(body, &result); err == nil {
		switch {
		case status == http.StatusUnauthorized && result.Error.Code == "unauthorized":
			return chat.ErrUnauthorized
		case status == http.StatusForbidden && result.Error.Code == "wrong_room":
			return chat.ErrForbidden
		case status == http.StatusConflict && result.Error.Code == "room_closed":
			return chat.ErrRoomClosed
		}
	}
	// Do not expose arbitrary upstream response text; it may contain secrets.
	return fmt.Errorf("%w: invalid error response", chat.ErrRoomServiceUnavailable)
}

func roomRequestError(ctx context.Context, err error) error {
	if errors.Is(ctx.Err(), context.Canceled) {
		return context.Canceled
	}
	var networkError net.Error
	if errors.Is(err, context.DeadlineExceeded) || errors.As(err, &networkError) && networkError.Timeout() {
		return fmt.Errorf("%w: %w", chat.ErrRoomServiceTimeout, context.DeadlineExceeded)
	}
	// Do not wrap raw transport errors, which can include URLs or header values.
	return chat.ErrRoomServiceUnavailable
}
