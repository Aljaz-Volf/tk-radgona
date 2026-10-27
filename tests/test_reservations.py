from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.models import Court, Reservation, User
from app.services.reservations import ReservationConflict, create_reservation


def test_overlapping_reservation_is_rejected(app, member, court):
    with app.app_context():
        user = db.session.get(User, member)
        selected_court = db.session.get(Court, court)
        start = datetime(2027, 6, 10, 10, 0)
        create_reservation(court=selected_court, user=user, starts_at=start, ends_at=start + timedelta(hours=1))
        db.session.commit()
        with pytest.raises(ReservationConflict):
            create_reservation(court=selected_court, user=user, starts_at=start + timedelta(minutes=30), ends_at=start + timedelta(minutes=90))
        db.session.rollback()


def test_adjacent_reservations_are_allowed(app, member, court):
    with app.app_context():
        user = db.session.get(User, member)
        selected_court = db.session.get(Court, court)
        start = datetime(2027, 6, 10, 10, 0)
        create_reservation(court=selected_court, user=user, starts_at=start, ends_at=start + timedelta(hours=1))
        db.session.commit()
        create_reservation(court=selected_court, user=user, starts_at=start + timedelta(hours=1), ends_at=start + timedelta(hours=2))
        db.session.commit()
        assert Reservation.query.count() == 2


def test_public_reservation_route_redirects_to_courtiplay(client):
    response = client.get("/rezervacije/nova")
    assert response.status_code == 302
    assert response.location == "https://courtiplay.com"


def test_court_page_contains_registration_and_app_links(client):
    response = client.get("/rezervacije/")
    text = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Rezervirajte s Courtiplay" in text
    assert "apps.apple.com/si/app/courtiplay/id6739180100" in text
    assert "play.google.com/store/apps/details?id=com.courtiplay.app" in text
    assert "info@courtiplay.com" in text

