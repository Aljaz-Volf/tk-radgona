from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Reservation
from ..services.audit import record


bp = Blueprint("reservations", __name__)


@bp.get("/")
def calendar():
    return render_template("reservations/calendar.html", courtiplay_url=current_app.config["COURTIPLAY_URL"])


@bp.get("/nova")
def create():
    return redirect(current_app.config["COURTIPLAY_URL"])


@bp.post("/<int:reservation_id>/preklic")
@login_required
def cancel(reservation_id):
    reservation = db.get_or_404(Reservation, reservation_id)
    if reservation.user_id != current_user.id and not current_user.has_any_role("administrator"):
        return ("", 403)
    comparison_time = datetime.now(reservation.starts_at.tzinfo) if reservation.starts_at.tzinfo else datetime.now()
    if reservation.status == "confirmed" and reservation.starts_at > comparison_time:
        reservation.status = "cancelled"
        record("reservation.cancel", reservation)
        db.session.commit()
        flash("Rezervacija je preklicana.", "success")
    else:
        flash("Te rezervacije ni več mogoče preklicati.", "error")
    return redirect(request.referrer or url_for("reservations.calendar"))

