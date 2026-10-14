import click
from .methods.canvases import canvases_group
from .methods.channels import channels_group
from .methods.emoji import emoji_group
from .methods.users import users_group

@click.group()
def cli():
    """Slack Migration Tools - Utilities for Slack workspace data extraction."""
    pass


# Register command groups
cli.add_command(canvases_group)
cli.add_command(channels_group)
cli.add_command(emoji_group)
cli.add_command(users_group)

if __name__ == "__main__":
    cli()
