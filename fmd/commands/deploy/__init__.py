import typer
from typer_examples import install

from fmd.commands.deploy.pull import pull
from fmd.commands.deploy.ship import ship

app = typer.Typer(rich_markup_mode="rich", invoke_without_command=True, no_args_is_help=True)
install(app)


@app.callback()
def deploy_callback(ctx: typer.Context):
    """Pull and ship releases to benches."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


app.command("pull", no_args_is_help=True)(pull)
app.command("ship", no_args_is_help=True)(ship)
