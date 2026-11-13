from app.extensions import db
from app.models import User
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

