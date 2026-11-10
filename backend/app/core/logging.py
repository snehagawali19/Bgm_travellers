import logging
import sys

SENSITIVE = ("password", "secret", "authorization", "cookie", "card", "cvv", "razorpay_key")


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = str(record.getMessage())
        lower = message.lower()
        if any(token in lower for token in SENSITIVE):
            record.msg = "[redacted log message]"
            record.args = ()
        return True


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RedactingFilter())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[handler],
        force=True,
    )
