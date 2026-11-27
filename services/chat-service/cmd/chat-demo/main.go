// chat-demo calls the chat service directly for manual local checks.
// It does not start an HTTP server or connect to real rooms.
package main

import (
	"bufio"
	"context"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"plotina/chat-service/internal/chat"
	"plotina/chat-service/internal/rooms"
	"plotina/chat-service/internal/storage"
	"plotina/chat-service/internal/storage/postgres"
)

type demoUser struct {
	roomID        string
	token         string
	participantID string
	role          chat.Role
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "Ошибка демонстрации:", err)
		os.Exit(1)
	}
}

func run() error {
	users := map[string]demoUser{
		"user-1": {roomID: "room-1", token: "demo-token-1", participantID: "participant-1", role: chat.RoleHost},
	}
	sessions := make(map[string]chat.Membership, len(users))
	for id, user := range users {
		sessions[user.token] = chat.Membership{
			RoomID: user.roomID, ParticipantID: user.participantID,
			DisplayName: id, Role: user.role, Connected: true,
		}
	}
	var messageStorage chat.MessageRepository = storage.NewMemoryRepository()
	if databaseURL := os.Getenv("CHAT_DATABASE_URL"); databaseURL != "" {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		pool, err := postgres.Open(ctx, databaseURL)
		cancel()
		if err != nil {
			return err
		}
		defer pool.Close()
		messageStorage = postgres.NewRepository(pool)
		fmt.Println("Хранилище: PostgreSQL. Перед первым запуском примени миграции.")
	} else {
		fmt.Println("Хранилище: память. Данные будут потеряны после выхода.")
	}
	var runID [16]byte
	if _, err := rand.Read(runID[:]); err != nil {
		return fmt.Errorf("создать идентификатор запуска: %w", err)
	}
	commandPrefix := "demo-" + hex.EncodeToString(runID[:])
	service := chat.NewService(rooms.NewFakeMembershipChecker(sessions), messageStorage)
	userID := "user-1"
	var lastCommand *chat.SendCommand
	commandNumber := 0

	scanner := bufio.NewScanner(os.Stdin)
	scanner.Buffer(make([]byte, 4096), 1024*1024)
	for {
		fmt.Printf("[%s / %s] > ", users[userID].roomID, userID)
		if !scanner.Scan() {
			break
		}
		line := scanner.Text()
		input := strings.TrimSpace(line)
		switch {
		case input == "/quit":
			return nil
		case input == "/help":
			printHelp()
			continue
		case input == "/add" || strings.HasPrefix(input, "/add "):
			fields := strings.Fields(input)
			if len(fields) != 2 {
				fmt.Println("Использование: /add номер_комнаты, например /add 1")
				continue
			}
			roomNumber, err := strconv.Atoi(fields[1])
			if err != nil || roomNumber <= 0 {
				fmt.Println("Номер комнаты должен быть положительным целым числом.")
				continue
			}
			newUserID, newUser := addUserToRoom(users, roomNumber)
			sessions[newUser.token] = chat.Membership{
				RoomID: newUser.roomID, ParticipantID: newUser.participantID,
				DisplayName: newUserID, Role: newUser.role, Connected: true,
			}
			// The fake checker copies sessions, so refresh it while retaining messages.
			service = chat.NewService(rooms.NewFakeMembershipChecker(sessions), messageStorage)
			fmt.Printf("Добавлен %s в %s. Переключиться: /as %s\n", newUserID, newUser.roomID, newUserID)
			lastCommand = nil
			continue
		case input == "/as" || strings.HasPrefix(input, "/as "):
			fields := strings.Fields(input)
			if len(fields) != 2 {
				fmt.Println("Использование: /as user-n, например /as user-1")
				continue
			}
			if _, ok := users[fields[1]]; !ok {
				fmt.Println("Неизвестный пользователь. Посмотреть список: /users")
				continue
			}
			userID = fields[1]
			lastCommand = nil
			continue
		case input == "/users":
			for id, user := range users {
				fmt.Printf("%s -> комната: %s, participant_id: %s, роль: %s, токен: %s\n", id, user.roomID, user.participantID, user.role, user.token)
			}
			continue
		case input == "/retry":
			if lastCommand == nil {
				fmt.Println("Нет команды для повтора. Сначала отправь сообщение.")
				continue
			}
			send(service, *lastCommand)
			continue
		case strings.HasPrefix(input, "/"):
			fmt.Println("Неизвестная команда демонстрации. Список: /help")
			continue
		}

		commandNumber++
		command := chat.SendCommand{
			RoomID:       users[userID].roomID,
			SessionToken: users[userID].token,
			CommandID:    fmt.Sprintf("%s-%d", commandPrefix, commandNumber),
			Text:         line,
		}
		lastCommand = &command
		send(service, command)
	}
	if err := scanner.Err(); err != nil {
		return fmt.Errorf("чтение ввода: %w", err)
	}
	return nil
}

func send(service *chat.Service, command chat.SendCommand) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	result, err := service.SendMessage(ctx, command)
	if err != nil {
		fmt.Println("Ошибка:", err)
		return
	}
	message := result.Message
	fmt.Printf("  command_id:     %s\n", result.CommandID)
	fmt.Printf("  duplicate:      %t\n", result.Duplicate)
	fmt.Printf("  message_id:     %s\n", message.MessageID)
	fmt.Printf("  room_id:        %s\n", message.RoomID)
	fmt.Printf("  participant_id: %s\n", message.ParticipantID)
	fmt.Printf("  text:           %q\n", message.Text)
	fmt.Printf("  messageSeq:     %d\n", message.MessageSeq)
	fmt.Printf("  created_at:     %s\n\n", message.CreatedAt.Format(time.RFC3339Nano))
}

func printHelp() {
	fmt.Println("введи текст и нажми Enter — сообщение будет сохранено.")
	fmt.Println("  /as user-n выбрать n-ого юзера)")
	fmt.Println("  /add n     — добавить пользователя в room-n, например /add 1")
	fmt.Println("  /retry     — повторить последнюю отправку с прежним commandId")
	fmt.Println("  /help      — показать подсказку")
	fmt.Println("  /quit      — выйти")
	fmt.Println("  /users     - выводит список юзеров")

}

func addUserToRoom(users map[string]demoUser, roomNumber int) (string, demoUser) {
	nextID := len(users) + 1
	idStr := strconv.Itoa(nextID)

	userID := "user-" + idStr
	newUser := demoUser{
		roomID:        "room-" + strconv.Itoa(roomNumber),
		token:         "demo-token-" + idStr,
		participantID: "participant-" + idStr,
		role:          chat.RoleMember,
	}

	users[userID] = newUser
	return userID, newUser
}
