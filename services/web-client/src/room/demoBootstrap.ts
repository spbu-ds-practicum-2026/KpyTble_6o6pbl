import type { ChatMessage, RoomBootstrap } from "../api/protocol";

/**
 * Небольшой набор данных, чтобы посмотреть экран комнаты без Gateway.
 * Все действия в демо меняют только локальный экран.
 */
export const DEMO_MESSAGES: ChatMessage[] = [
  {
    messageId: "demo-message-1",
    messageSeq: 1,
    participantId: "Bob",
    text: "Привет! Видео уже в очереди.",
    createdAt: "2026-11-26T12:04:00.000Z"
  },
  {
    messageId: "demo-message-2",
    messageSeq: 2,
    participantId: "Carol",
    text: "Перемотку поставила на 42 секунды 👀",
    createdAt: "2026-11-26T12:04:18.000Z"
  },
  {
    messageId: "demo-message-3",
    messageSeq: 3,
    participantId: "Alice",
    text: "Отлично, тогда начинаем.",
    createdAt: "2026-11-26T12:04:31.000Z"
  }
];

export function createDemoBootstrap(): RoomBootstrap {
  return {
    session: {
      token: "demo-token",
      roomId: "DEMO-ROOM",
      displayName: "Alice",
      role: "host"
    },
    state: {
      roomId: "DEMO-ROOM",
      status: "active",
      controlMode: "host_only",
      stateVersion: 7,
      currentVideoId: "demo-video-1",
      playback: {
        videoId: "demo-video-1",
        positionSeconds: 42.5,
        isPlaying: true
      },
      queue: [
        {
          id: "demo-video-1",
          url: "https://rutube.ru/video/e5c3a1b7d9f24d6c8a0b2e4f6d8c0a2b/",
          position: 0
        },
        {
          id: "demo-video-2",
          url: "https://rutube.ru/video/a1b2c3d4e5f60718293a4b5c6d7e8f90/",
          position: 1
        },
        {
          id: "demo-video-3",
          url: "https://rutube.ru/video/0123456789abcdef0123456789abcdef/",
          position: 2
        }
      ],
      participants: [
        {
          displayName: "Alice",
          role: "host",
          connected: true
        },
        {
          displayName: "Bob",
          role: "member",
          connected: true
        },
        {
          displayName: "Carol",
          role: "member",
          connected: false
        }
      ]
    },
    inviteCode: "Demo_12345",
    inviteLink: "http://localhost:5173/?demo=1",
    demo: true
  };
}
