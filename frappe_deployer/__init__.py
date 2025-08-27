from unittest.mock import patch
from frappe_deployer.consts import LOG_FILE_NAME
import typer

VERSION = "0.12.0"

def version_callback(show: bool):

    if show:
        typer.echo(f"frappe-deployer version: {VERSION}")
        raise typer.Exit()

class CustomLogger:
    def debug(self, msg):
        print(f"Custom debug: {msg}")

patcher = patch("frappe_manager.logger.log.get_logger.__defaults__", (LOG_FILE_NAME.parent, LOG_FILE_NAME.name))
patcher.start()

