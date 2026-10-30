from datetime import date, datetime

import pytest

from app.extensions import db
from app.models import LeagueGroup, LeagueMembership, Match, MatchSet, Player, Season
from app.services.scoring import parse_score
from app.services.standings import ordered_standings, recalculate_group
from tests.conftest import login


@pytest.mark.parametrize("score,winner", [("6-4, 6-2", 1), ("4-6, 6-3, 10-8", 1), ("6-7 (4-7), 2-6", 2)])
def test_valid_tennis_scores(score, winner):
    sets, parsed_winner = parse_score(score)
    assert len(sets) >= 2
    assert parsed_winner == winner


@pytest.mark.parametrize("score", ["6-6, 6-2", "6-4", "6-4, 6-4, 3-0", "7-4, 6-2", "foo"])
def test_invalid_tennis_scores(score):
    with pytest.raises(ValueError):
        parse_score(score)


def _league(app):
    season = Season(name="Liga 2026", slug="liga-2026", starts_on=date(2026, 4, 1), ends_on=date(2026, 10, 1), is_published=True, win_points=2, loss_points=0)
    group = LeagueGroup(name="A liga", season=season)
    first = Player(display_name="Ana Novak", slug="ana-novak")
    second = Player(display_name="Boris Horvat", slug="boris-horvat")
    db.session.add_all([season, group, first, second])
    db.session.flush()
    db.session.add_all([LeagueMembership(group=group, player=first), LeagueMembership(group=group, player=second)])
    match = Match(season=season, group=group, player1=first, player2=second, winner=first, status="completed")
    match.sets = [MatchSet(set_number=1, player1_games=6, player2_games=4), MatchSet(set_number=2, player1_games=6, player2_games=2)]
    db.session.add(match)
    db.session.commit()
    return season, group, first, second, match


def test_standings_are_recalculated_from_completed_matches(app):
    with app.app_context():
        _, group, first, second, _ = _league(app)
        recalculate_group(group)
        db.session.commit()
        table = ordered_standings(group)
        assert [row.player_id for row in table] == [first.id, second.id]
        assert table[0].points == 2
        assert table[0].wins == 1
        assert table[0].sets_won == 2
        assert table[0].games_won == 12


def test_match_players_cannot_be_identical(app):
    with app.app_context():
        season, group, first, _, _ = _league(app)
        invalid = Match(season=season, group=group, player1=first, player2=first)
        db.session.add(invalid)
        with pytest.raises(Exception):
            db.session.commit()
        db.session.rollback()


def test_public_season_page_renders(app, client):
    with app.app_context():
        season, group, *_ = _league(app)
        recalculate_group(group)
        db.session.commit()
    response = client.get("/liga/liga-2026")
    assert response.status_code == 200
    assert "Ana Novak" in response.get_data(as_text=True)


def test_archive_is_separate_from_current_league_page(app, client):
    with app.app_context():
        _league(app)
    league_page = client.get("/liga/").get_data(as_text=True)
    archive_page = client.get("/liga/arhiv").get_data(as_text=True)
    assert "Arhiv sezon" not in league_page
    assert "Iščete stare rezultate?" in league_page
    assert "Arhiv lige" in archive_page
    assert "Liga 2026" in archive_page
    assert 'aria-label="Liga Radgona"' not in archive_page


def test_four_current_league_pages_render_database_data(app, client):
    with app.app_context():
        season, group, *_ = _league(app)
        season.is_current = True
        season.rules = "Tekma se igra na dva dobljena niza."
        recalculate_group(group)
        db.session.commit()
    pages = {
        "/liga/pravilnik": "Pravilnik Teniške lige Radgona 2022",
        "/liga/rezultati": "Ana Novak",
        "/liga/razvrstitve": "A liga",
        "/liga/razpored": "Ni napovedanih tekem",
    }
    for url, expected in pages.items():
        response = client.get(url)
        assert response.status_code == 200
        assert expected in response.get_data(as_text=True)
    assert 'aria-label="Liga Radgona"' not in client.get("/liga/pravilnik").get_data(as_text=True)
    results_page = client.get("/liga/rezultati").get_data(as_text=True)
    assert 'aria-label="Liga Radgona"' in results_page
    section_nav = results_page.split('class="section-tabs"', 1)[1].split("</nav>", 1)[0]
    assert "Pravilnik lige" not in section_nav
    assert "Arhiv" not in section_nav
    pdf = client.get("/static/documents/pravilnik-teniske-lige-radgona-2022.pdf")
    assert pdf.status_code == 200
    assert pdf.data.startswith(b"%PDF")


def test_admin_can_create_public_current_season_with_zero_loss_points(app, client, admin):
    login(client)
    form = client.get("/admin/liga/sezona/nova").get_data(as_text=True)
    assert "Pravila" not in form
    assert 'name="loss_points"' in form
    assert 'min="0"' in form
    assert 'name="is_current"' in form and 'name="is_published"' in form

    response = client.post(
        "/admin/liga/sezona/nova",
        data={
            "name": "Liga 2027",
            "starts_on": "2027-04-01",
            "ends_on": "2027-10-01",
            "win_points": 3,
            "loss_points": 0,
            "is_current": "y",
            "is_published": "y",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        season = Season.query.filter_by(name="Liga 2027").one()
        assert season.loss_points == 0
        assert season.win_points == 3
        assert season.is_current is True
        assert season.is_published is True
    assert "Liga 2027" in client.get("/liga/").get_data(as_text=True)


def test_admin_rejects_negative_loss_points(app, client, admin):
    login(client)
    response = client.post(
        "/admin/liga/sezona/nova",
        data={
            "name": "Neveljavna liga",
            "starts_on": "2027-04-01",
            "ends_on": "2027-10-01",
            "win_points": 2,
            "loss_points": -1,
            "is_current": "y",
            "is_published": "y",
        },
    )
    assert response.status_code == 200
    with app.app_context():
        assert Season.query.filter_by(name="Neveljavna liga").first() is None


def test_scheduled_match_in_current_published_season_is_visible(app, client):
    with app.app_context():
        season, group, first, second, _ = _league(app)
        season.is_current = True
        scheduled = Match(
            season=season,
            group=group,
            player1=first,
            player2=second,
            status="scheduled",
            scheduled_at=datetime(2026, 6, 15, 18, 0),
        )
        db.session.add(scheduled)
        db.session.commit()
    schedule = client.get("/liga/razpored").get_data(as_text=True)
    assert "15. 06. 2026" in schedule
    assert "Ana Novak" in schedule

