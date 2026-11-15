package plotina.gateway.command;

public class CommandRejectedException extends RuntimeException {

  private final String code;

  public CommandRejectedException(String code, String message) {
    super(message);
    this.code = code;
  }

  public String code() {
    return code;
  }
}
