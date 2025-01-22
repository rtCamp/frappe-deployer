import atexit
from pathlib import Path

from frappe_manager.display_manager.DisplayManager import richprint
from frappe_manager.logger import log
from frappe_manager.utils.docker import process_opened
from frappe_manager.utils.helpers import (
    capture_and_format_exception,
    remove_zombie_subprocess_process,
)
import typer

import frappe_deployer
from frappe_deployer.consts import LOG_FILE_NAME


def cli_entrypoint():
    try:
        frappe_deployer.cli()
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
