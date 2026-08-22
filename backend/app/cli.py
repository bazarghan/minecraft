import getpass

import typer
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Base, Role, User
from .security import hash_password


app = typer.Typer(help="Minecraft Server Manager administration commands")


def sync_url() -> str:
    return get_settings().database_url.replace("+psycopg", "")


@app.command("bootstrap-admin")
def bootstrap_admin(username: str = typer.Option(..., prompt=True)) -> None:
    """Create the first administrator without exposing a password in process arguments."""
    password = getpass.getpass("New administrator password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise typer.BadParameter("Passwords do not match")
    if len(password) < 12:
        raise typer.BadParameter("Password must contain at least 12 characters")
    engine = create_engine(sync_url())
    with Session(engine) as db:
        if db.scalar(select(User.id)):
            raise typer.BadParameter("A user already exists; create additional users through the API")
        db.add(User(username=username, password_hash=hash_password(password), role=Role.admin))
        db.commit()
    typer.echo("First administrator created.")


@app.command("bootstrap-admin-from-env", hidden=True)
def bootstrap_admin_from_env() -> None:
    """Idempotent container entrypoint helper for optional environment bootstrap."""
    settings = get_settings()
    if not settings.initial_admin_username or not settings.initial_admin_password:
        return
    engine = create_engine(sync_url())
    with Session(engine) as db:
        if not db.scalar(select(User.id)):
            db.add(User(username=settings.initial_admin_username, password_hash=hash_password(settings.initial_admin_password.get_secret_value()), role=Role.admin))
            db.commit()
            typer.echo("Initial administrator created from environment.")


if __name__ == "__main__":
    app()
