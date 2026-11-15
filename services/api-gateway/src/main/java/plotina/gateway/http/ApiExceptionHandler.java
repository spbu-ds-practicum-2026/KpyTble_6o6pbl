package plotina.gateway.http;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import plotina.gateway.room.backend.RoomNotFoundException;

@RestControllerAdvice
public class ApiExceptionHandler {

  @ExceptionHandler(RoomNotFoundException.class)
  public ResponseEntity<ApiError> handleRoomNotFound(RoomNotFoundException exception) {
    ApiError error = new ApiError(
        "ROOM_NOT_FOUND",
        exception.getMessage());
    return ResponseEntity.status(HttpStatus.NOT_FOUND).body(error);
  }

  public record ApiError(String code, String message) {
  }

}
