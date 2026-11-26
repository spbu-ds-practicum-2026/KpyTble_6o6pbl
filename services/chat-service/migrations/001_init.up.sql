CREATE TABLE chat_room_counters (
    room_id TEXT PRIMARY KEY CHECK (btrim(room_id) <> ''),
    last_message_seq BIGINT NOT NULL DEFAULT 0 CHECK (last_message_seq >= 0)
);

CREATE TABLE chat_messages (
    message_id TEXT PRIMARY KEY CHECK (btrim(message_id) <> ''),
    room_id TEXT NOT NULL REFERENCES chat_room_counters(room_id),
    participant_id TEXT NOT NULL CHECK (btrim(participant_id) <> ''),
    message_seq BIGINT NOT NULL CHECK (message_seq > 0),
    text TEXT NOT NULL CHECK (btrim(text) <> ''),
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (room_id, message_seq),
    UNIQUE (room_id, participant_id, message_id)
);

CREATE TABLE chat_commands (
    room_id TEXT NOT NULL,
    participant_id TEXT NOT NULL,
    command_id TEXT NOT NULL CHECK (btrim(command_id) <> ''),
    original_text TEXT NOT NULL,
    message_id TEXT NOT NULL,
    PRIMARY KEY (room_id, participant_id, command_id),
    FOREIGN KEY (room_id, participant_id, message_id)
        REFERENCES chat_messages(room_id, participant_id, message_id)
);
