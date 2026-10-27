from datetime import timedelta

from sqlalchemy import text

from ..extensions import db
from ..models import Reservation


class ReservationConflict(ValueError):
    pass


def create_reservation(*, court, user, starts_at, ends_at, kind="booking", title=None, notes=None):
    if ends_at <= starts_at:
        raise ValueError("Konec rezervacije mora biti po začetku.")
    if starts_at.date() != ends_at.date():
        raise ValueError("Rezervacija se mora začeti in končati isti dan.")
    if starts_at.time() < court.opening_time or ends_at.time() > court.closing_time:
        raise ValueError("Termin je zunaj odpiralnega časa igrišča.")
    if kind == "booking" and ends_at - starts_at != timedelta(minutes=court.slot_minutes):
        raise ValueError(f"Termin mora trajati {court.slot_minutes} minut.")

    if db.engine.dialect.name == "postgresql":
        db.session.execute(text("SELECT pg_advisory_xact_lock(:court_id)"), {"court_id": court.id})

    conflict = Reservation.query.filter(
        Reservation.court_id == court.id,
        Reservation.status == "confirmed",
        Reservation.starts_at < ends_at,
        Reservation.ends_at > starts_at,
    ).first()
    if conflict:
        raise ReservationConflict("Izbrani termin je že zaseden.")
    reservation = Reservation(
        court=court,
        user=user,
        starts_at=starts_at,
        ends_at=ends_at,
        kind=kind,
        title=title,
        notes=notes,
    )
    db.session.add(reservation)
    db.session.flush()
    return reservation

