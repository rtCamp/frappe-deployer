import typer
from typer_examples import install

from fmd.__about__ import __version__
from fmd.commands import _utils
from fmd.commands.cleanup import cleanup
from fmd.commands.deploy import app as deploy_app
from fmd.commands.release import app as release_app
from fmd.commands.remote_worker import app as remote_worker_app
from fmd.commands.search_replace import search_replace

app = typer.Typer(rich_markup_mode="rich", invoke_without_command=True)
install(app)


def _version_callback(value: bool):
    if value:
        typer.echo(f"fmd {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output for all commands."),
    version: bool = typer.Option(
        False, "--version", "-V", help="Show version.", callback=_version_callback, is_eager=True
    ),
):
    if verbose:
        _utils.set_verbose(True)
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


app.add_typer(deploy_app, name="deploy")
app.add_typer(release_app, name="release")
app.add_typer(remote_worker_app, name="remote-worker")
app.command("search-replace")(search_replace)
app.command("cleanup")(cleanup)


def cli_entrypoint():
    app()
