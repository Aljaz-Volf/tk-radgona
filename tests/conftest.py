from datetime import time

import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import Court, Role, User


@pytest.fixture()
def app(tmp_path):
    class LocalTestConfig(TestConfig):
        UPLOAD_FOLDER = str(tmp_path / "uploads")

    application = create_app(LocalTestConfig)
    with application.app_context():
        db.create_all()
        db.session.add_all([
            Role(name="administrator", description="Administrator"),
            Role(name="member", description="Član"),
        ])
        db.session.commit()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def admin(app):
    with app.app_context():
        role = Role.query.filter_by(name="administrator").one()
        user = User(email="admin@example.test", username="admin", roles=[role])
        user.set_password("correct horse battery staple")
        db.session.add(user)
        db.session.commit()
        return user.id


@pytest.fixture()
def member(app):
    with app.app_context():
        role = Role.query.filter_by(name="member").one()
        user = User(email="member@example.test", username="member", roles=[role])
        user.set_password("correct horse battery staple")
        db.session.add(user)
        db.session.commit()
        return user.id


@pytest.fixture()
def court(app):
    with app.app_context():
        item = Court(name="Igrišče 1", surface="peščena", opening_time=time(7), closing_time=time(22))
        db.session.add(item)
        db.session.commit()
        return item.id


def login(client, identity="admin", password="correct horse battery staple"):
    return client.post("/racun/prijava", data={"identity": identity, "password": password}, follow_redirects=False)

