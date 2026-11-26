DOCUMENTED_ERROR_CODES = frozenset(
    {
        "unauthorized",
        "wrong_room",
        "host_only_mode",
        "host_only_command",
        "no_current_video",
        "room_closed",
        "command_id_conflict",
        "invalid_video_url",
        "invalid_payload",
    }
)


class DomainError(Exception):
    status_code = 400
    code: str = ""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        resolved = code or self.code
        if resolved not in DOCUMENTED_ERROR_CODES:
            raise ValueError(f"Недокументированный код ошибки: {resolved}")
        super().__init__(message)
        self.message = message
        self.code = resolved


class UnauthorizedError(DomainError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(DomainError):
    status_code = 403


class ConflictError(DomainError):
    status_code = 409


class InvalidRequestError(DomainError):
    status_code = 422
    code = "invalid_payload"
