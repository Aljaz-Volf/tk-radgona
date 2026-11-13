import os
from datetime import time

import click
from flask.cli import with_appcontext
from flask_migrate import upgrade

from .extensions import db
from .models import BUILT_IN_ROLES, PASSWORD_MIN_LENGTH, ClubContent, Court, Player, Role, User
from .services.content import sanitize_rich_text, unique_slug


SHOWCASE_MEN = (
    "Luka Novak", "Marko Horvat", "Jure Kovač", "Miha Zupan", "Rok Kralj",
    "Tomaž Mlakar", "Nejc Vidmar", "Žan Kos", "Blaž Potočnik", "Jan Krajnc",
    "Matej Turk", "Aljaž Golob", "Gregor Božič", "Anže Korošec", "Urban Zajc",
    "Klemen Bizjak", "Domen Marin", "Bor Šinko", "Niko Rakuša", "Tim Gomboc",
    "Simon Kolarič", "David Ficko", "Matic Ropoša", "Denis Celec", "Robert Žitek",
    "Aleš Vrbnjak", "Peter Fras", "Martin Šafarič", "Andrej Kocbek", "Dejan Bencak",
    "Matjaž Ploj", "Bojan Kramberger", "Sandi Kous", "Kristjan Škrlec", "Patrik Kuhar",
    "Erik Maučec", "Leon Tivadar", "Gašper Perša", "Sebastjan Čeh", "Uroš Štih",
)

SHOWCASE_WOMEN = (
    "Ana Novak", "Maja Horvat", "Nina Kovač", "Sara Zupan", "Eva Kralj",
    "Lara Mlakar", "Nika Vidmar", "Tjaša Kos", "Ema Potočnik", "Urška Krajnc",
)


def register_commands(app):
    app.cli.add_command(init_db)
    app.cli.add_command(create_admin)
    app.cli.add_command(bootstrap_owner)
    app.cli.add_command(seed_development)
    app.cli.add_command(seed_showcase_players)


@click.command("init-db")
@with_appcontext
def init_db():
    """Apply migrations and ensure the built-in roles exist."""
    upgrade()
    for name, description in BUILT_IN_ROLES:
        role = Role.query.filter_by(name=name).first()
        if role:
            role.description = description
        else:
            db.session.add(Role(name=name, description=description))
    db.session.commit()
    click.echo("Database migrations applied and roles initialized.")


@click.command("create-admin")
@click.option("--email", prompt=True)
@click.option("--username", prompt=True)
@click.password_option(confirmation_prompt=True, prompt="Password")
@with_appcontext
def create_admin(email, username, password):
    """Create the first superadministrator without hardcoded credentials."""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise click.ClickException(
            f"Password must contain at least {PASSWORD_MIN_LENGTH} characters."
        )
    email = email.strip().lower()
    username = username.strip().lower()
    if User.query.filter((User.email == email) | (User.username == username)).first():
        raise click.ClickException("A user with that email or username already exists.")
    role = Role.query.filter_by(name="superadmin").first()
    if not role:
        role = Role(name="superadmin", description="Polni skrbniški dostop")
        db.session.add(role)
    user = User(email=email, username=username, roles=[role])
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f"Superadministrator {username} created.")


@click.command("bootstrap-owner")
@click.option("--username", prompt=True)
@with_appcontext
def bootstrap_owner(username):
    """Promote one existing user when an installation has no owner yet."""
    owner_role = Role.query.filter_by(name="owner").first()
    if not owner_role:
        owner_role = Role(name="owner", description="Najvišji dostop in upravljanje lastnikov")
        db.session.add(owner_role)
        db.session.flush()
    if owner_role.users:
        raise click.ClickException("An owner already exists; manage owners in the application.")

    user = User.query.filter_by(username=username.strip().lower()).first()
    if not user:
        raise click.ClickException("No user with that username exists.")
    user.roles = [owner_role]
    db.session.commit()
    click.echo(f"Owner {user.username} bootstrapped.")


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


@click.command("seed-showcase-players")
@click.option(
    "--confirm-fictional",
    is_flag=True,
    help="Acknowledge that the 50 showcase players are fictional.",
)
@with_appcontext
def seed_showcase_players(confirm_fictional):
    """Add 40 fictional men and 10 fictional women for demonstrations."""
    if not confirm_fictional:
        raise click.ClickException("Pass --confirm-fictional to add showcase players.")

    existing_names = {player.display_name.casefold() for player in Player.query.all()}
    created_men = 0
    created_women = 0
    for category, names in (("moški", SHOWCASE_MEN), ("ženske", SHOWCASE_WOMEN)):
        for name in names:
            if name.casefold() in existing_names:
                continue
            db.session.add(
                Player(
                    display_name=name,
                    slug=unique_slug(Player, name),
                    bio=(
                        "Fiktivni predstavitveni igralec — kategorija: moški."
                        if category == "moški"
                        else "Fiktivna predstavitvena igralka — kategorija: ženske."
                    ),
                    active=True,
                )
            )
            existing_names.add(name.casefold())
            if category == "moški":
                created_men += 1
            else:
                created_women += 1
    db.session.commit()
    click.echo(
        f"Showcase players ready: created {created_men} men and {created_women} women; "
        f"{50 - created_men - created_women} already existed."
    )

