from unittest.mock import patch

from app.extensions import db
from app.models import Role, User
from tests.conftest import login


def test_login_and_logout(client, admin):
    response = login(client)
    assert response.status_code == 302
    profile = client.get("/racun/profil")
    assert profile.status_code == 200
    assert b"admin@example.test" in profile.data
    response = client.post("/racun/odjava")
    assert response.status_code == 302
    assert client.get("/racun/profil").status_code == 302


def test_invalid_login_is_rejected(client, admin):
    response = login(client, password="incorrect password")
    assert response.status_code == 200
    assert "Prijavni podatki niso pravilni" in response.get_data(as_text=True)


def test_password_reset_token_is_time_limited(app, admin):
    with app.app_context():
        user = db.session.get(User, admin)
        token = user.get_reset_token()
        assert User.verify_reset_token(token).id == user.id
        user.set_password("a different secure password")
        db.session.commit()
        assert User.verify_reset_token(token) is None


def test_password_reset_accepts_six_characters(app, client, admin):
    with app.app_context():
        token = db.session.get(User, admin).get_reset_token()
    response = client.post(
        f"/racun/novo-geslo/{token}",
        data={"password": "abc123", "confirm": "abc123"},
    )
    assert response.status_code == 302
    assert login(client, "admin", "abc123").status_code == 302


def test_member_cannot_access_admin(client, member):
    login(client, "member")
    assert client.get("/admin/").status_code == 403


def test_anonymous_admin_redirects_to_login(client):
    response = client.get("/admin/")
    assert response.status_code == 302
    assert "/racun/prijava" in response.location


def test_create_admin_command_bootstraps_a_superadmin(app):
    result = app.test_cli_runner().invoke(
        args=[
            "create-admin",
            "--email",
            "owner@example.test",
            "--username",
            "owner",
            "--password",
            "abc123",
        ]
    )
    assert result.exit_code == 0, result.output
    with app.app_context():
        owner = User.query.filter_by(username="owner").one()
        assert owner.has_any_role("superadmin")


def test_bootstrap_owner_promotes_existing_user_once(app, admin):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["bootstrap-owner", "--username", "admin"])
    assert result.exit_code == 0, result.output
    with app.app_context():
        user = db.session.get(User, admin)
        assert user.has_any_role("owner")
        assert not user.has_any_role("superadmin")
    repeated = runner.invoke(args=["bootstrap-owner", "--username", "admin"])
    assert repeated.exit_code != 0


def test_admin_can_create_user_with_six_character_password(app, client, admin):
    login(client)
    response = client.post(
        "/admin/uporabniki/nov",
        data={
            "email": "six@example.com",
            "username": "sixchars",
            "password": "abc123",
            "roles": ["member"],
        },
    )
    assert response.status_code == 302, response.get_data(as_text=True)
    client.post("/racun/odjava")
    assert login(client, "sixchars", "abc123").status_code == 302


def test_create_user_normalizes_and_rejects_case_insensitive_duplicates(app, client, admin):
    with app.app_context():
        role = Role.query.filter_by(name="member").one()
        existing = User(email="mixed@example.com", username="mixedcase", roles=[role])
        existing.set_password("abc123")
        db.session.add(existing)
        db.session.commit()

    login(client)
    email_duplicate = client.post(
        "/admin/uporabniki/nov",
        data={
            "email": " MIXED@EXAMPLE.COM ",
            "username": "different",
            "password": "abc123",
            "roles": "member",
        },
    )
    assert email_duplicate.status_code == 200
    assert "Ta e-pošta je že v uporabi" in email_duplicate.get_data(as_text=True)

    username_duplicate = client.post(
        "/admin/uporabniki/nov",
        data={
            "email": "different@example.com",
            "username": "MixedCase",
            "password": "abc123",
            "roles": "member",
        },
    )
    assert username_duplicate.status_code == 200
    assert "To uporabniško ime je že zasedeno" in username_duplicate.get_data(as_text=True)


def test_administrator_cannot_create_an_administrator(app, client, administrator):
    login(client, "administrator")
    response = client.post(
        "/admin/uporabniki/nov",
        data={
            "email": "forged-admin@example.com",
            "username": "forged-admin",
            "password": "abc123",
            "roles": "administrator",
        },
    )
    assert response.status_code == 200
    with app.app_context():
        assert User.query.filter_by(username="forged-admin").first() is None


def test_superadmin_can_manage_another_superadmin(app, client, admin):
    with app.app_context():
        role = Role.query.filter_by(name="superadmin").one()
        peer = User(email="peer@example.com", username="peer", roles=[role])
        peer.set_password("abc123")
        db.session.add(peer)
        db.session.commit()
        peer_id = peer.id

    login(client)
    assert client.get(f"/admin/uporabniki/{peer_id}/dostop").status_code == 200
    response = client.post(
        f"/admin/uporabniki/{peer_id}/dostop",
        data={"roles": ["member_news"], "active": "y"},
    )
    assert response.status_code == 302
    with app.app_context():
        peer = db.session.get(User, peer_id)
        assert peer.has_any_role("member_news")
        assert not peer.has_any_role("superadmin")


def test_superadmin_cannot_see_assign_or_manage_owner(app, client, admin, owner):
    login(client)
    create_page = client.get("/admin/uporabniki/nov").get_data(as_text=True)
    assert "Lastnik" not in create_page
    assert client.get(f"/admin/uporabniki/{owner}/dostop").status_code == 403
    forged = client.post(
        "/admin/uporabniki/nov",
        data={
            "email": "forged-owner@example.com",
            "username": "forged-owner",
            "password": "abc123",
            "roles": "owner",
        },
    )
    assert forged.status_code == 200
    with app.app_context():
        assert User.query.filter_by(username="forged-owner").first() is None


def test_owner_can_promote_another_user_to_owner(app, client, owner, member):
    login(client, "owner")
    page = client.get(f"/admin/uporabniki/{member}/dostop").get_data(as_text=True)
    assert "Lastnik" in page
    response = client.post(
        f"/admin/uporabniki/{member}/dostop",
        data={"roles": ["owner"], "active": "y"},
    )
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(User, member).has_any_role("owner")


def test_administrator_can_manage_only_lower_roles(app, client, administrator, member_news):
    login(client, "administrator")
    assert client.get(f"/admin/uporabniki/{member_news}/dostop").status_code == 200
    response = client.post(
        f"/admin/uporabniki/{member_news}/dostop",
        data={"roles": ["member"], "active": "y"},
    )
    assert response.status_code == 302


def test_admin_mail_action_sends_configured_password_change_link(app, client, admin, member):
    app.config.update(
        MAIL_SERVER="smtp.example.com",
        MAIL_DEFAULT_SENDER="club@example.com",
        MAIL_USE_TLS=False,
        PUBLIC_BASE_URL="https://club.example.com",
    )
    login(client)
    with patch("app.services.email.smtplib.SMTP") as smtp_class:
        response = client.post(f"/admin/uporabniki/{member}/mail")

    assert response.status_code == 302
    smtp = smtp_class.return_value.__enter__.return_value
    message = smtp.send_message.call_args.args[0]
    plain = message.get_body(preferencelist=("plain",)).get_content()
    assert "https://club.example.com/racun/novo-geslo/" in plain
    assert "localhost" not in plain


def test_member_cannot_call_admin_mail_action(client, member):
    login(client, "member")
    assert client.post(f"/admin/uporabniki/{member}/mail").status_code == 403


def test_administrator_has_admin_tools_but_not_overview(client, administrator):
    login(client, "administrator")
    response = client.get("/admin/")
    assert response.status_code == 302
    assert response.location.endswith("/admin/novice")
    news = client.get("/admin/novice")
    assert news.status_code == 200
    assert ">Pregled<" not in news.get_data(as_text=True)


def test_member_news_uses_public_create_buttons_only(client, member_news):
    login(client, "editor")

    news = client.get("/novice").get_data(as_text=True)
    gallery = client.get("/galerije").get_data(as_text=True)
    assert "Dodaj novico" in news
    assert "Dodaj album" in gallery
    assert ">Administracija<" not in news

    news_form = client.get("/admin/novice/nova")
    gallery_form = client.get("/admin/galerije/nova")
    assert news_form.status_code == 200
    assert gallery_form.status_code == 200
    assert "Administracija" not in news_form.get_data(as_text=True)
    assert "Administracija" not in gallery_form.get_data(as_text=True)

    assert client.get("/admin/novice").status_code == 403
    assert client.get("/admin/galerije").status_code == 403
    assert client.get("/admin/igralci").status_code == 403

    article = client.post(
        "/admin/novice/nova",
        data={"title": "Nova novica", "body": "Vsebina", "status": "draft"},
    )
    album = client.post(
        "/admin/galerije/nova",
        data={"title": "Nov album", "description": "Opis"},
    )
    assert article.status_code == 302
    assert article.location.endswith("/novice")
    assert album.status_code == 302
    assert album.location.endswith("/galerije")


def test_administrator_cannot_manage_superadmin_access(client, admin, administrator):
    login(client, "administrator")
    assert client.get(f"/admin/uporabniki/{admin}/dostop").status_code == 403

