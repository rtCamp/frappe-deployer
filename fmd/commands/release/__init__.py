import typer
from typer_examples import install

from fmd.commands.release.configure import configure
from fmd.commands.release.create import create
from fmd.commands.release.switch import switch
from fmd.commands.release.list import list_releases
from fmd.commands.info import info

app = typer.Typer(rich_markup_mode="rich", invoke_without_command=True, no_args_is_help=True)
install(app)


@app.callback()
def release_callback(ctx: typer.Context):
    """Manage releases: configure, create, switch, list, and inspect."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


app.command("configure", no_args_is_help=True)(configure)
app.command("create", no_args_is_help=True)(create)
app.command("switch", no_args_is_help=True)(switch)
app.command("list", no_args_is_help=True)(list_releases)
app.command("info", no_args_is_help=True)(info)
