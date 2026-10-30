from pathlib import Path
from types import SimpleNamespace

from flask import Blueprint, abort, current_app, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required

from ..models import ClubCommittee, ClubContent, Gallery, GalleryImage, Member, NewsArticle, Player, Reservation, Season
from ..services.uploads import media_url
from ..services.time import utc_now_naive


bp = Blueprint("public", __name__)


@bp.get("/")
def home():
    now = utc_now_naive()
    public_articles = NewsArticle.query.filter(
        NewsArticle.status == "published", NewsArticle.published_at <= now
    )
    article = public_articles.filter_by(is_pinned=True).order_by(
        NewsArticle.published_at.desc()
    ).first()
    if article is None:
        article = public_articles.order_by(NewsArticle.published_at.desc()).first()
    articles = [article] if article else []
    season = Season.query.filter_by(is_current=True, is_published=True).first()
    upcoming = []
    recent = []
    if season:
        upcoming = sorted(
            [match for match in season.matches if match.status == "scheduled" and match.scheduled_at],
            key=lambda match: match.scheduled_at,
        )[:4]
        recent = sorted(
            [match for match in season.matches if match.status == "completed"],
            key=lambda match: match.played_at or match.updated_at,
            reverse=True,
        )[:4]
    club_sections = {section.section_key: section for section in ClubContent.query.filter_by(is_published=True).all()}
    homepage_stats = {
        "active_players": Player.query.filter_by(active=True).count(),
        "published_seasons": Season.query.filter_by(is_published=True).count(),
        "completed_matches": len([match for match in season.matches if match.status == "completed"]) if season else 0,
        "upcoming_matches": len([match for match in season.matches if match.status == "scheduled"]) if season else 0,
    }
    return render_template(
        "public/home.html",
        articles=articles,
        season=season,
        upcoming=upcoming,
        recent=recent,
        homepage_stats=homepage_stats,
        club_sections=club_sections,
    )


@bp.get("/novice")
def news_index():
    now = utc_now_naive()
    articles = NewsArticle.query.filter(
        NewsArticle.status == "published", NewsArticle.published_at <= now
    ).order_by(NewsArticle.published_at.desc()).all()
    return render_template("public/news_index.html", articles=articles)


@bp.get("/novice/<slug>")
def news_detail(slug):
    article = NewsArticle.query.filter_by(slug=slug).first_or_404()
    if not article.is_public:
        abort(404)
    return render_template("public/news_detail.html", article=article)


@bp.get("/galerije")
@login_required
def gallery_index():
    galleries = Gallery.query.filter_by(is_published=True).order_by(Gallery.created_at.desc()).all()
    return render_template("public/gallery_index.html", galleries=galleries)


@bp.get("/galerije/<slug>")
@login_required
def gallery_detail(slug):
    gallery = Gallery.query.filter_by(slug=slug, is_published=True).first_or_404()
    return render_template("public/gallery_detail.html", gallery=gallery)


@bp.get("/klub/<section_key>")
def club_section(section_key):
    allowed_sections = {
        "about": "O klubu",
        "leadership": "Organi kluba",
        "members": "Člani",
        "documents": "Dokumenti",
        "rules": "Pravila tenisa",
        "contact": "Kontakt",
        "courts": "Igrišča",
    }
    section = ClubContent.query.filter_by(section_key=section_key, is_published=True).first()
    if section_key == "members" and not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.full_path))
    if section_key == "members":
        members = Member.query.filter_by(active=True).order_by(Member.last_name, Member.first_name).all()
        return render_template("public/members.html", members=members, section=section)
    if section_key == "leadership":
        committees = ClubCommittee.query.order_by(ClubCommittee.sort_order, ClubCommittee.name).all()
        return render_template("public/leadership.html", committees=committees)
    if section_key == "membership":
        return render_template("public/membership_fees.html", section=section)
    if section_key == "statute":
        statute_path = Path(current_app.static_folder) / "documents" / "statut-tk-gornja-radgona.pdf"
        return render_template("public/statute.html", section=section, statute_available=statute_path.is_file())
    if section_key not in allowed_sections:
        abort(404)
    if not section:
        section = SimpleNamespace(title=allowed_sections[section_key], body_html="")
    return render_template("public/club_section.html", section=section)


@bp.get("/media/<path:key>")
def media(key):
    gallery_image = GalleryImage.query.filter_by(storage_key=key).first()
    if gallery_image and not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.full_path))
    if current_app.config["STORAGE_BACKEND"] == "s3":
        return redirect(media_url(key))
    upload_root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    return send_from_directory(upload_root, key)


@bp.get("/zdravje")
def health():
    return {"status": "ok"}

