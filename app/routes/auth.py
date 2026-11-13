from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from flask import Blueprint, flash, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_

from ..extensions import db, limiter
from ..forms import ForgotPasswordForm, LoginForm, ResetPasswordForm
from ..models import User
from ..services.audit import record
from ..services.email import send_password_reset_email


bp = Blueprint("auth", __name__)


def _safe_next(target):
    if not target:
        return None
    host = urlparse(request.host_url)
    candidate = urlparse(urljoin(request.host_url, target))
    return target if candidate.scheme in {"http", "https"} and host.netloc == candidate.netloc else None


@bp.route("/prijava", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("public.home"))
    form = LoginForm()
    if form.validate_on_submit():
        identity = form.identity.data.strip().lower()
        user = User.query.filter(or_(User.email.ilike(identity), User.username.ilike(identity))).first()
        if user and user.is_active and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            user.last_login_at = datetime.now(timezone.utc)
            record("auth.login", user)
            db.session.commit()
            flash("Uspešno ste se prijavili.", "success")
            return redirect(_safe_next(request.args.get("next")) or url_for("public.home"))
        flash("Prijavni podatki niso pravilni.", "error")
    return render_template("auth/login.html", form=form)


@bp.post("/odjava")
@login_required
def logout():
    record("auth.logout", current_user)
    db.session.commit()
    logout_user()
    flash("Odjava je bila uspešna.", "success")
    return redirect(url_for("public.home"))


@bp.route("/pozabljeno-geslo", methods=["GET", "POST"])
@limiter.limit("3 per hour", methods=["POST"])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user and user.is_active:
            send_password_reset_email(user)
        flash("Če račun obstaja, smo poslali navodila za ponastavitev gesla.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html", form=form)

@bp.route("/novo-geslo/<token>", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def reset_password(token):
    user = User.verify_reset_token(token)
    if not user:
        flash("Povezava je neveljavna ali je potekla.", "error")
        return redirect(url_for("auth.forgot_password"))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        record("auth.password_reset", user)
        db.session.commit()
        flash("Geslo je bilo spremenjeno. Zdaj se lahko prijavite.", "success")
        return redirect(url_for("auth.login"))
    response = make_response(render_template("auth/reset_password.html", form=form))
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@bp.get("/profil")
@login_required
def profile():
    return render_template("auth/profile.html")

