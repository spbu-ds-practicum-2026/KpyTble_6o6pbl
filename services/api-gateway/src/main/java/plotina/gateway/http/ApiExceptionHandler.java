package plotina.gateway.http;

import java.util.Map;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class ApiExceptionHandler {

  @ExceptionHandler(GatewayException.class)
  public ResponseEntity<?> handleGateway(GatewayException exception) {
    return ResponseEntity.status(exception.status()).body(Map.of("error", exception.error()));
  }

  @ExceptionHandler(HttpMessageNotReadableException.class)
  public ResponseEntity<?> handleInvalidJson(HttpMessageNotReadableException exception) {
    return handleGateway(new GatewayException(422, "invalid_payload", "Expected a valid JSON request body"));
  }

}
