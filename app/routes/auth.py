import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from urllib.parse import urljoin, urlparse

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_

from ..extensions import db, limiter
from ..forms import ForgotPasswordForm, LoginForm, ResetPasswordForm
from ..models import User
from ..services.audit import record


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
            _send_reset_email(user)
        flash("Če račun obstaja, smo poslali navodila za ponastavitev gesla.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html", form=form)


def _send_reset_email(user):
    server = current_app.config.get("MAIL_SERVER")
    if not server:
        current_app.logger.warning("Password reset requested but SMTP is not configured for user_id=%s", user.id)
        return
    reset_url = url_for("auth.reset_password", token=user.get_reset_token(), _external=True)
    message = EmailMessage()
    message["Subject"] = "Ponastavitev gesla — TK Gornja Radgona"
    message["From"] = current_app.config["MAIL_DEFAULT_SENDER"]
    message["To"] = user.email
    message.set_content(f"Geslo lahko v eni uri ponastavite na naslovu:\n\n{reset_url}\n")
    with smtplib.SMTP(server, current_app.config["MAIL_PORT"], timeout=15) as smtp:
        if current_app.config["MAIL_USE_TLS"]:
            smtp.starttls()
        if current_app.config["MAIL_USERNAME"]:
            smtp.login(current_app.config["MAIL_USERNAME"], current_app.config["MAIL_PASSWORD"])
        smtp.send_message(message)


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
    return render_template("auth/reset_password.html", form=form)


@bp.get("/profil")
@login_required
def profile():
    return render_template("auth/profile.html")

