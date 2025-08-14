import atexit
import re
import sys

from frappe_manager.display_manager.DisplayManager import richprint
from frappe_manager.logger import log
from frappe_manager.utils.docker import process_opened
from frappe_manager.utils.helpers import (
    rich_object_to_string,
    remove_zombie_subprocess_process,
)
from rich.traceback import Traceback
import typer

import frappe_deployer
from frappe_deployer.consts import LOG_FILE_NAME

def mask_sensitive_value(value: str) -> str:
    """Mask potentially sensitive values."""
    sensitive_patterns = [
        # Add patterns that could indicate sensitive data
        r'token["\']?\s*[:=]\s*["\']?\w+["\']?',  # Match token values
        r'password["\']?\s*[:=]\s*["\']?\w+["\']?',  # Match password values
        r'secret["\']?\s*[:=]\s*["\']?\w+["\']?',  # Match secret values
        r'https?://[^@]+@',  # Match credentials in URLs
    ]
    
    masked_value = str(value)
    for pattern in sensitive_patterns:
        masked_value = re.sub(pattern, lambda m: re.sub(r'[^:=\s"\']+', '*****', m.group()), masked_value)
    return masked_value

def capture_and_format_exception(traceback_max_frames: int = 100) -> str:
    """Capture the current exception and return a formatted traceback string with sensitive data masked."""
    exc_type, exc_value, exc_traceback = sys.exc_info()

    # Mask sensitive data in exception value if it's string-like
    if hasattr(exc_value, 'args') and exc_value.args:
        masked_args = tuple(mask_sensitive_value(arg) if isinstance(arg, str) else arg 
                          for arg in exc_value.args)
        exc_value.args = masked_args

    traceback = Traceback.from_exception(
        exc_type, exc_value, exc_traceback, 
        show_locals=True, 
        max_frames=traceback_max_frames,
    )
    formatted_traceback = rich_object_to_string(traceback)
    formatted_traceback = mask_sensitive_value(formatted_traceback)

    return formatted_traceback


def cli_entrypoint():
    try:
        frappe_deployer.commands.app()
    except Exception as e:
        logger = log.get_logger()
        richprint.stop()

        richprint.error(f'[red]Error Occured[/red]  {str(e).strip()}', emoji_code="\n:red_square:")
        richprint.error(f"More info about error is logged in {LOG_FILE_NAME}.log", emoji_code=':mag:')

        exception_traceback: str = capture_and_format_exception()
        richprint.print(f"Exception Occured\n{exception_traceback}")

        logger.error(f"Exception Occured:  : \n{exception_traceback}")

        raise typer.Exit(1)

    finally:
        atexit.register(exit_cleanup)



def exit_cleanup():
    """
    This function is used to perform cleanup at the exit.
    """
    remove_zombie_subprocess_process(process_opened)
    richprint.stop()

if __name__ == "__main__":
    cli_entrypoint()
