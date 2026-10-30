import os
from datetime import time

import click
from flask.cli import with_appcontext
from flask_migrate import upgrade

from .extensions import db
from .models import ClubContent, Court, Role, User
from .services.content import sanitize_rich_text


def register_commands(app):
    app.cli.add_command(init_db)
    app.cli.add_command(create_admin)
    app.cli.add_command(seed_development)


@click.command("init-db")
@with_appcontext
def init_db():
    """Apply migrations and ensure the built-in roles exist."""
    upgrade()
    for name, description in [("administrator", "Polni skrbniški dostop"), ("member", "Član kluba")]:
        if not Role.query.filter_by(name=name).first():
            db.session.add(Role(name=name, description=description))
    db.session.commit()
    click.echo("Database migrations applied and roles initialized.")


@click.command("create-admin")
@click.option("--email", prompt=True)
@click.option("--username", prompt=True)
@click.password_option(confirmation_prompt=True, prompt="Password")
@with_appcontext
def create_admin(email, username, password):
    """Create the first administrator without hardcoded credentials."""
    if len(password) < 12:
        raise click.ClickException("Password must contain at least 12 characters.")
    if User.query.filter((User.email == email.lower()) | (User.username == username)).first():
        raise click.ClickException("A user with that email or username already exists.")
    role = Role.query.filter_by(name="administrator").first()
    if not role:
        role = Role(name="administrator", description="Polni skrbniški dostop")
        db.session.add(role)
    user = User(email=email.lower(), username=username, roles=[role])
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f"Administrator {username} created.")


@click.command("seed-development")
@click.option("--confirm-fictional", is_flag=True, help="Acknowledge that seed records are fictional development data.")
@with_appcontext
def seed_development(confirm_fictional):
    """Add clearly labelled fictional data for local UI development only."""
    if not confirm_fictional:
        raise click.ClickException("Pass --confirm-fictional to add development-only content.")
    if os.getenv("FLASK_ENV") == "production":
        raise click.ClickException("Development seed is disabled in production.")
    if not Court.query.first():
        db.session.add(Court(name="Razvojno igrišče 1 (demo)", surface="peščena", opening_time=time(7), closing_time=time(22)))
    if not ClubContent.query.filter_by(section_key="about").first():
        db.session.add(ClubContent(section_key="about", title="O klubu", body_html=sanitize_rich_text("<p>Razvojna predstavitvena vsebina — pred objavo jo zamenjajte s potrjenimi podatki kluba.</p>"), is_published=False))
    db.session.commit()
    click.echo("Fictional development data added; none of it is published as real club information.")

