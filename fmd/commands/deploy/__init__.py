import typer

from fmd.commands.deploy.pull import pull
from fmd.commands.deploy.ship import ship

app = typer.Typer()
app.command("pull")(pull)
app.command("ship")(ship)
