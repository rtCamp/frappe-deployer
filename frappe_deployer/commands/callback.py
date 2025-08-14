from typing import Annotated
import typer
from frappe_deployer import VERSION, version_callback
from frappe_deployer.commands import app


@app.callback()
def main(ctx: typer.Context, version: Annotated[bool, typer.Option("--version", "-V", callback=version_callback, is_eager=True)] = False):
    """Frappe Deployer CLI tool"""

    typer.echo(f"frappe-deployer version: {VERSION}")
    # if not version:
    #     version_callback(True)

    # return ctx
