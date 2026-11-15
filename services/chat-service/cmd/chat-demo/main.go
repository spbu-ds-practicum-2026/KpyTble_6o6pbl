// chat-demo calls the chat service directly for manual local checks.
// It does not start an HTTP server or connect to real rooms.
package main

import (
	"bufio"
	"context"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"plotina/chat-service/internal/chat"
	"plotina/chat-service/internal/rooms"
	"plotina/chat-service/internal/storage"
)

type demoUser struct {
	roomID string
	token  string
}

func main() {
	users := map[string]demoUser{
		"user-1": {roomID: "room-1", token: "demo-token-1"},
	}
	sessions := make(map[string]chat.Membership, len(users))
	for id, user := range users {
		sessions[user.token] = chat.Membership{RoomID: user.roomID, UserID: id}
	}
	messageStorage := storage.NewMemoryRepository()
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
			return
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
			sessions[newUser.token] = chat.Membership{RoomID: newUser.roomID, UserID: newUserID}
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
				fmt.Printf("%s -> комната: %s, токен: %s\n", id, user.roomID, user.token)
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
			UserID:       userID,
			SessionToken: users[userID].token,
			CommandID:    fmt.Sprintf("demo-%d", commandNumber),
			Text:         line,
		}
		lastCommand = &command
		send(service, command)
	}
	if err := scanner.Err(); err != nil {
		fmt.Fprintln(os.Stderr, "Ошибка чтения ввода:", err)
		os.Exit(1)
	}
}

func send(service *chat.Service, command chat.SendCommand) {
	result, err := service.SendMessage(context.Background(), command)
	if err != nil {
		fmt.Println("Ошибка:", err)
		return
	}
	message := result.Message
	fmt.Printf("  commandId:  %s\n", result.CommandID)
	fmt.Printf("  duplicate:  %t\n", result.Duplicate)
	fmt.Printf("  messageId:  %s\n", message.MessageID)
	fmt.Printf("  roomId:     %s\n", message.RoomID)
	fmt.Printf("  userId:     %s\n", message.UserID)
	fmt.Printf("  text:       %q\n", message.Text)
	fmt.Printf("  messageSeq: %d\n", message.MessageSeq)
	fmt.Printf("  sentAt:     %s\n\n", message.SentAt.Format(time.RFC3339Nano))
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
		roomID: "room-" + strconv.Itoa(roomNumber),
		token:  "demo-token-" + idStr,
	}

	users[userID] = newUser
	return userID, newUser
}
