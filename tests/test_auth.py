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


def test_member_cannot_access_admin(client, member):
    login(client, "member")
    assert client.get("/admin/").status_code == 403


def test_anonymous_admin_redirects_to_login(client):
    response = client.get("/admin/")
    assert response.status_code == 302
    assert "/racun/prijava" in response.location

