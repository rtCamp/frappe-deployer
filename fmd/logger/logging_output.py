import logging
from typing import Any


class LoggingOutputHandler:
    def __init__(self, delegate, logger: logging.Logger, log_prefix: str = "[OUTPUT]"):
        self.delegate = delegate
        self.logger = logger
        self.log_prefix = log_prefix
        self.verbose = getattr(delegate, "verbose", False)

    def _log_message(self, level: int, message: str) -> None:
        prefixed_message = f"{self.log_prefix} {message}"

        if level == logging.DEBUG:
            self.logger.debug(prefixed_message)
        elif level == logging.INFO:
            self.logger.info(prefixed_message)
        elif level == logging.WARNING:
            self.logger.warning(prefixed_message)
        elif level == logging.ERROR:
            self.logger.error(prefixed_message)
        else:
            self.logger.info(prefixed_message)

    def start(self, text: str) -> None:
        self._log_message(logging.INFO, f"START: {text}")
        self.delegate.start(text)

    def stop(self) -> None:
        self._log_message(logging.INFO, "STOP")
        self.delegate.stop()

    def change_head(self, text: str) -> None:
        self._log_message(logging.INFO, f"CHANGE_HEAD: {text}")
        self.delegate.change_head(text)

    def print(self, message: str, **kwargs) -> None:
        self._log_message(logging.INFO, message)
        self.delegate.print(message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        self._log_message(logging.ERROR, message)
        self.delegate.error(message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        self._log_message(logging.WARNING, message)
        self.delegate.warning(message, **kwargs)

    def live_lines(self, data, **kwargs) -> None:
        def _tee(stream):
            for source, line in stream:
                if isinstance(line, bytes):
                    decoded = line.decode(errors="replace")
                else:
                    decoded = line
                self._log_message(logging.INFO, f"[{source}] {decoded.rstrip()}")
                yield source, line

        self.delegate.live_lines(_tee(data), **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.delegate, name)
