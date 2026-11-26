from app.enums import CommandType, ControlMode, ParticipantRole
from app.errors import ForbiddenError, InvalidRequestError
from app.models import Participant, Room

PLAYBACK_AND_QUEUE_COMMANDS = frozenset(
    {
        CommandType.PLAYPAUSE,
        CommandType.SEEK,
        CommandType.NEXT,
        CommandType.ADD_VIDEO,
        CommandType.REMOVE_VIDEO,
        CommandType.CHANGE_QUEUE,
    }
)

HOST_ONLY_COMMANDS = frozenset({CommandType.SET_CONTROL_MODE})


def ensure_can_execute(
    room: Room, participant: Participant, command_type: CommandType
) -> None:
    """Roles are always read from the server-side participant record."""

    if command_type in HOST_ONLY_COMMANDS:
        if participant.role != ParticipantRole.HOST:
            raise ForbiddenError(
                "Команда доступна только ведущему", code="host_only_command"
            )
        return

    if command_type in PLAYBACK_AND_QUEUE_COMMANDS:
        if (
            room.control_mode == ControlMode.HOST_ONLY
            and participant.role != ParticipantRole.HOST
        ):
            raise ForbiddenError(
                "В режиме «только ведущий» управлять может только ведущий",
                code="host_only_mode",
            )
        return

    raise InvalidRequestError("Неизвестная команда", code="invalid_payload")
