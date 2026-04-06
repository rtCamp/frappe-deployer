import typer

from fmd.commands.release.configure import configure
from fmd.commands.release.create import create
from fmd.commands.release.switch import switch
from fmd.commands.release.list import list_releases

app = typer.Typer()
app.command("configure")(configure)
app.command("create")(create)
app.command("switch")(switch)
app.command("list")(list_releases)
