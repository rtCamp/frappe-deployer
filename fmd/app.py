import typer

from fmd.commands import _utils
from fmd.commands.cleanup import cleanup
from fmd.commands.deploy import app as deploy_app
from fmd.commands.info import info
from fmd.commands.release import app as release_app
from fmd.commands.remote_worker import app as remote_worker_app
from fmd.commands.search_replace import search_replace

app = typer.Typer()


@app.callback()
def main(verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output for all commands.")):
    if verbose:
        _utils.set_verbose(True)


app.add_typer(deploy_app, name="deploy")
app.add_typer(release_app, name="release")
app.add_typer(remote_worker_app, name="remote-worker")
app.command("search-replace")(search_replace)
app.command("info")(info)
app.command("cleanup")(cleanup)


def cli_entrypoint():
    app()
