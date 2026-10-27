from datetime import datetime, timezone

from flask import Blueprint, render_template

from ..models import Match, Player, Season
from ..services.standings import ordered_standings


bp = Blueprint("league", __name__)


def _current_season():
    return Season.query.filter_by(is_current=True, is_published=True).first()


@bp.get("/")
def index():
    season = _current_season()
    return render_template("league/index.html", season=season)


@bp.get("/pravilnik")
def rules():
    return render_template("league/rules.html", season=_current_season())


@bp.get("/rezultati")
def results():
    season = _current_season()
    matches = []
    if season:
        matches = Match.query.filter_by(season_id=season.id, status="completed").order_by(Match.played_at.desc()).all()
    return render_template("league/results.html", season=season, matches=matches)


@bp.get("/razvrstitve")
def standings():
    season = _current_season()
    group_tables = [(group, ordered_standings(group)) for group in season.groups] if season else []
    return render_template("league/standings.html", season=season, group_tables=group_tables)


@bp.get("/razpored")
def schedule():
    season = _current_season()
    matches = []
    if season:
        matches = Match.query.filter_by(season_id=season.id, status="scheduled").all()
        matches.sort(key=lambda match: (match.scheduled_at is None, match.scheduled_at or datetime.max.replace(tzinfo=timezone.utc)))
    return render_template("league/schedule.html", season=season, matches=matches)


@bp.get("/arhiv")
def archive():
    seasons = Season.query.filter_by(is_published=True, is_current=False).order_by(Season.starts_on.desc()).all()
    return render_template("league/archive.html", seasons=seasons)


@bp.get("/<slug>")
def season(slug):
    selected = Season.query.filter_by(slug=slug, is_published=True).first_or_404()
    group_tables = [(group, ordered_standings(group)) for group in selected.groups]
    upcoming = Match.query.filter_by(season_id=selected.id, status="scheduled").order_by(Match.scheduled_at.asc()).all()
    results = Match.query.filter_by(season_id=selected.id, status="completed").order_by(Match.played_at.desc()).all()
    return render_template("league/season.html", season=selected, group_tables=group_tables, upcoming=upcoming, results=results)


@bp.get("/igralec/<slug>")
def player(slug):
    selected = Player.query.filter_by(slug=slug, active=True).first_or_404()
    matches = Match.query.filter(
        (Match.player1_id == selected.id) | (Match.player2_id == selected.id), Match.status == "completed"
    ).order_by(Match.played_at.desc()).all()
    return render_template("league/player.html", player=selected, matches=matches)

