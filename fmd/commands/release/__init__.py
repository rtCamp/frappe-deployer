import typer
from typer_examples import install

from fmd.commands.release.configure import configure
from fmd.commands.release.create import create
from fmd.commands.release.switch import switch
from fmd.commands.release.list import list_releases
from fmd.commands.info import info

app = typer.Typer(rich_markup_mode="rich", invoke_without_command=True)
install(app)


@app.callback()
def release_callback(ctx: typer.Context):
    """Manage releases: configure, create, switch, list, and inspect."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


app.command("configure")(configure)
app.command("create")(create)
app.command("switch")(switch)
app.command("list")(list_releases)
app.command("info")(info)
