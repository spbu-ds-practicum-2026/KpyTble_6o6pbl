from enum import StrEnum


class RoomStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"


class ParticipantRole(StrEnum):
    HOST = "host"
    MEMBER = "member"


class ControlMode(StrEnum):
    HOST_ONLY = "host_only"
    ALL = "all"


class CommandType(StrEnum):
    PLAYPAUSE = "playpause"
    SEEK = "seek"
    NEXT = "next"

    ADD_VIDEO = "add_video"
    REMOVE_VIDEO = "remove_video"
    CHANGE_QUEUE = "change_queue"

    SET_CONTROL_MODE = "set_control_mode"
