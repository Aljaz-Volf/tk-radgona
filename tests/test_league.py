import json
import re
from datetime import date, datetime

import pytest

from app.extensions import db
from app.models import LeagueGroup, LeagueMembership, Match, MatchSet, Player, Season, Standing
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


def test_admin_can_enter_result_when_players_are_not_group_members(app, client, admin):
    with app.app_context():
        season = Season(
            name="Liga brez članstev",
            slug="liga-brez-clanstev",
            starts_on=date(2026, 4, 1),
            ends_on=date(2026, 10, 1),
            win_points=2,
            loss_points=0,
        )
        group = LeagueGroup(name="A liga", season=season)
        first = Player(display_name="Ana Novak", slug="ana-novak")
        second = Player(display_name="Boris Horvat", slug="boris-horvat")
        match = Match(
            season=season,
            group=group,
            player1=first,
            player2=second,
            status="scheduled",
        )
        db.session.add_all([season, group, first, second, match])
        db.session.commit()
        match_id = match.id
        first_id = first.id
        second_id = second.id

    login(client)
    response = client.post(
        f"/admin/tekme/{match_id}/rezultat",
        data={
            "set1_player1": 6,
            "set1_player2": 4,
            "set2_player1": 6,
            "set2_player2": 2,
        },
    )
    assert response.status_code == 302

    with app.app_context():
        saved_match = db.session.get(Match, match_id)
        assert saved_match.status == "completed"
        assert saved_match.winner_id == first_id
        rows = {row.player_id: row for row in Standing.query.all()}
        assert rows[first_id].played == 1
        assert rows[first_id].wins == 1
        assert rows[first_id].points == 2
        assert rows[second_id].played == 1
        assert rows[second_id].losses == 1
        assert rows[second_id].points == 0


def test_result_form_uses_score_grid_and_saves_deciding_tiebreak(app, client, admin):
    with app.app_context():
        _, _, first, _, match = _league(app)
        match_id = match.id
        first_id = first.id

    login(client)
    page = client.get(f"/admin/tekme/{match_id}/rezultat")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "data-match-result-form" in html
    assert "3. niz · odločilni" in html
    assert "Zapis rezultata" in html
    assert "Zmagovalec" in html
    assert ">Prekliči<" in html
    for field_name in (
        "set1_player1",
        "set1_player2",
        "set2_player1",
        "set2_player2",
        "set3_player1",
        "set3_player2",
    ):
        assert f'name="{field_name}"' in html

    response = client.post(
        f"/admin/tekme/{match_id}/rezultat",
        data={
            "set1_player1": 6,
            "set1_player2": 4,
            "set2_player1": 3,
            "set2_player2": 6,
            "set3_player1": 10,
            "set3_player2": 8,
            "notes": "Dober dvoboj",
        },
    )
    assert response.status_code == 302

    with app.app_context():
        saved_match = db.session.get(Match, match_id)
        assert [(item.player1_games, item.player2_games) for item in saved_match.sets] == [
            (6, 4),
            (3, 6),
            (10, 8),
        ]
        assert saved_match.winner_id == first_id
        assert saved_match.notes == "Dober dvoboj"


def test_match_form_player_picker_contains_group_ranks_points_and_history(app, client, admin):
    with app.app_context():
        season, group, first, second, _ = _league(app)
        third = Player(display_name="Cene Kralj", slug="cene-kralj")
        db.session.add(third)
        db.session.flush()
        db.session.add(LeagueMembership(group=group, player=third, seed=3))
        recalculate_group(group)
        db.session.commit()
        group_id = group.id
        pair_key = ":".join(str(player_id) for player_id in sorted((first.id, second.id)))

    login(client)
    response = client.get("/admin/tekme/nova")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert html.count("data-match-player-picker") == 2
    assert "Išči igralca" in html
    assert "Pokaži vse igralce" in html
    assert 'data-match-player-data' in html
    match = re.search(r'<script type="application/json" data-match-player-data>(.*?)</script>', html, re.S)
    assert match
    picker_data = json.loads(match.group(1))
    group_data = picker_data["groups"][str(group_id)]
    assert [player["name"] for player in group_data["players"]] == [
        "Ana Novak",
        "Cene Kralj",
        "Boris Horvat",
    ]
    assert group_data["players"][0]["rank"] == 1
    assert group_data["players"][0]["points"] == 2
    assert group_data["history"][pair_key] == 1

    script = client.get("/static/js/main.js").get_data(as_text=True)
    assert "Izbran" in script
    assert "Še ni odigrano" in script
    assert "Odigrano ${count}×" in script


def test_womens_league_is_displayed_before_numbered_leagues(app, client, admin):
    with app.app_context():
        season = Season(
            name="Liga 2028",
            slug="liga-2028",
            starts_on=date(2028, 4, 1),
            ends_on=date(2028, 10, 1),
            is_current=True,
            is_published=True,
        )
        first = LeagueGroup(name="1. Liga", season=season, sort_order=0)
        women = LeagueGroup(name="Ženska Liga", season=season, sort_order=4)
        db.session.add_all([season, first, women])
        db.session.commit()
        season_id = season.id

    login(client)
    match_form = client.get("/admin/tekme/nova").get_data(as_text=True)
    group_select = re.search(r'<select[^>]*name="group_id"[^>]*>(.*?)</select>', match_form, re.S)
    assert group_select
    assert group_select.group(1).index("Ženska Liga") < group_select.group(1).index("1. Liga")

    sorting = client.get(f"/admin/liga/sezona/{season_id}/igralci").get_data(as_text=True)
    board = sorting.split("league-sort-board", 1)[1]
    assert board.index("Ženska Liga") < board.index("1. Liga")

    standings = client.get("/liga/razvrstitve").get_data(as_text=True)
    assert standings.index("Ženska Liga") < standings.index("1. Liga")


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
            "apply_promotions": "y",
            "promotions_per_boundary": 2,
            "league_source_group_id": "",
            "league_name": "1. Liga",
            "league_max_players": 8,
        },
    )
    assert response.status_code == 302
    with app.app_context():
        season = Season.query.filter_by(name="Liga 2027").one()
        season_id = season.id
        assert season.loss_points == 0
        assert season.win_points == 3
        assert season.is_current is True
        assert season.is_published is False
        assert season.publish_after_setup is True
        assert season.setup_pending is True
        assert season.groups[0].name == "1. Liga"
        assert season.groups[0].max_players == 8

    confirmation = client.post(
        f"/admin/liga/sezona/{season_id}/premiki",
        data={"skip_moves": "1"},
    )
    assert confirmation.status_code == 302
    with app.app_context():
        season = db.session.get(Season, season_id)
        assert season.is_published is True
        assert season.setup_pending is False
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


def test_seasons_overview_shows_league_counts_and_unassigned_players(app, client, admin):
    with app.app_context():
        season = Season(
            name="Liga 2098",
            slug="liga-2098",
            starts_on=date(2098, 4, 1),
            ends_on=date(2098, 10, 1),
            is_current=True,
            is_published=True,
        )
        group = LeagueGroup(name="1. Liga", season=season, sort_order=0)
        players = [
            Player(display_name="Ana Novak", slug="ana-novak"),
            Player(display_name="Boris Horvat", slug="boris-horvat"),
            Player(display_name="Cene Kralj", slug="cene-kralj"),
        ]
        db.session.add_all([season, group, *players])
        db.session.flush()
        db.session.add_all([
            LeagueMembership(group=group, player=players[0], seed=1),
            LeagueMembership(group=group, player=players[1], seed=2),
        ])
        db.session.commit()
        season_id = season.id

    login(client)
    response = client.get("/admin/liga")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "1. Liga · 2" in html
    assert "1 igralec še nima lige" in html
    assert f'/admin/liga/sezona/{season_id}/igralci' in html
    assert "Razvrsti igralce" in html
    assert "Dodaj ligo" in html


def test_admin_can_save_player_leagues_and_starting_order(app, client, admin):
    with app.app_context():
        season = Season(
            name="Liga 2098",
            slug="liga-2098",
            starts_on=date(2098, 4, 1),
            ends_on=date(2098, 10, 1),
        )
        first_group = LeagueGroup(name="1. Liga", season=season, sort_order=0)
        second_group = LeagueGroup(name="2. Liga", season=season, sort_order=1)
        players = [
            Player(display_name="Ana Novak", slug="ana-novak"),
            Player(display_name="Boris Horvat", slug="boris-horvat"),
            Player(display_name="Cene Kralj", slug="cene-kralj"),
        ]
        db.session.add_all([season, first_group, second_group, *players])
        db.session.commit()
        season_id = season.id
        first_group_id = first_group.id
        second_group_id = second_group.id
        player_ids = [player.id for player in players]

    login(client)
    page = client.get(f"/admin/liga/sezona/{season_id}/igralci")
    html = page.get_data(as_text=True)
    assert page.status_code == 200
    assert "Brez lige" in html
    assert "Spusti igralca sem" in html
    assert "Shrani razvrstitev" in html
    assert "data-league-sorter" in html

    assignments = {
        "groups": {
            str(first_group_id): [player_ids[1]],
            str(second_group_id): [player_ids[2], player_ids[0]],
        },
        "unassigned": [],
    }
    response = client.post(
        f"/admin/liga/sezona/{season_id}/igralci",
        data={"assignments": json.dumps(assignments)},
    )
    assert response.status_code == 302

    with app.app_context():
        rows = LeagueMembership.query.order_by(LeagueMembership.group_id, LeagueMembership.seed).all()
        assert [(row.group_id, row.player_id, row.seed) for row in rows] == [
            (first_group_id, player_ids[1], 1),
            (second_group_id, player_ids[2], 1),
            (second_group_id, player_ids[0], 2),
        ]


def test_previous_standings_suggestion_promotes_and_relegates_two_players(app, client, admin):
    with app.app_context():
        previous = Season(
            name="2097",
            slug="liga-2097",
            starts_on=date(2097, 4, 1),
            ends_on=date(2097, 10, 1),
        )
        current = Season(
            name="2098",
            slug="liga-2098",
            starts_on=date(2098, 4, 1),
            ends_on=date(2098, 10, 1),
        )
        previous_groups = [
            LeagueGroup(name="1. Liga", season=previous, sort_order=0),
            LeagueGroup(name="2. Liga", season=previous, sort_order=1),
        ]
        current_groups = [
            LeagueGroup(name="1. Liga", season=current, sort_order=0),
            LeagueGroup(name="2. Liga", season=current, sort_order=1),
        ]
        players = [Player(display_name=f"Igralec {number}", slug=f"igralec-{number}") for number in range(1, 9)]
        db.session.add_all([previous, current, *previous_groups, *current_groups, *players])
        db.session.flush()
        for index, player in enumerate(players[:4], 1):
            db.session.add(LeagueMembership(group=previous_groups[0], player=player, seed=index))
        for index, player in enumerate(players[4:], 1):
            db.session.add(LeagueMembership(group=previous_groups[1], player=player, seed=index))
        db.session.commit()
        season_id = current.id
        current_group_ids = [group.id for group in current_groups]
        player_ids = [player.id for player in players]

    login(client)
    response = client.get(f"/admin/liga/sezona/{season_id}/igralci")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Predlagaj iz lestvice 2097" in html
    match = re.search(r'<script type="application/json" data-league-suggestion>(.*?)</script>', html, re.S)
    assert match
    suggestion = json.loads(match.group(1))
    assert suggestion["groups"][str(current_group_ids[0])] == [
        player_ids[0],
        player_ids[1],
        player_ids[4],
        player_ids[5],
    ]
    assert suggestion["groups"][str(current_group_ids[1])] == [
        player_ids[2],
        player_ids[3],
        player_ids[6],
        player_ids[7],
    ]


def test_player_sorting_rejects_more_than_eight_players_in_a_league(app, client, admin):
    with app.app_context():
        season = Season(
            name="Liga 2098",
            slug="liga-2098",
            starts_on=date(2098, 4, 1),
            ends_on=date(2098, 10, 1),
        )
        group = LeagueGroup(name="1. Liga", season=season, sort_order=0)
        players = [Player(display_name=f"Igralec {number}", slug=f"igralec-{number}") for number in range(1, 10)]
        db.session.add_all([season, group, *players])
        db.session.commit()
        season_id = season.id
        group_id = group.id
        player_ids = [player.id for player in players]

    login(client)
    response = client.post(
        f"/admin/liga/sezona/{season_id}/igralci",
        data={
            "assignments": json.dumps({
                "groups": {str(group_id): player_ids},
                "unassigned": [],
            })
        },
    )
    assert response.status_code == 302
    with app.app_context():
        assert LeagueMembership.query.count() == 0


def test_new_season_copies_leagues_and_confirms_promotions(app, client, admin):
    with app.app_context():
        previous = Season(
            name="2026",
            slug="liga-2026",
            starts_on=date(2026, 4, 1),
            ends_on=date(2026, 10, 1),
            is_current=True,
            is_published=True,
        )
        upper = LeagueGroup(name="1. Liga", season=previous, sort_order=0, max_players=8)
        lower = LeagueGroup(name="2. Liga", season=previous, sort_order=1, max_players=8)
        women = LeagueGroup(name="Ženska Liga", season=previous, sort_order=2, max_players=8)
        players = [Player(display_name=f"Igralec {number}", slug=f"igralec-{number}") for number in range(1, 14)]
        db.session.add_all([previous, upper, lower, women, *players])
        db.session.flush()
        for seed, player in enumerate(players[:4], 1):
            db.session.add(LeagueMembership(group=upper, player=player, seed=seed))
        for seed, player in enumerate(players[4:8], 1):
            db.session.add(LeagueMembership(group=lower, player=player, seed=seed))
        for seed, player in enumerate(players[8:12], 1):
            db.session.add(LeagueMembership(group=women, player=player, seed=seed))
        db.session.commit()
        previous_id = previous.id
        source_ids = [upper.id, lower.id, women.id]
        promoted_ids = [players[4].id, players[5].id]
        relegated_ids = [players[2].id, players[3].id]
        new_player_id = players[12].id

    login(client)
    form_page = client.get("/admin/liga/sezona/nova")
    form_html = form_page.get_data(as_text=True)
    assert form_page.status_code == 200
    assert "Igralce prenesi v lige, v katerih so igrali lani" in form_html
    assert "Ponastavi na lani" in form_html
    assert "Shrani in nadaljuj na premike" in form_html
    assert form_html.count('data-season-league-row') == 3

    response = client.post(
        "/admin/liga/sezona/nova",
        data={
            "name": "2027",
            "starts_on": "2027-04-01",
            "ends_on": "2027-10-01",
            "win_points": 2,
            "loss_points": 0,
            "carry_players": "y",
            "apply_promotions": "y",
            "promotions_per_boundary": 2,
            "is_current": "y",
            "is_published": "y",
            "league_source_group_id": [str(item) for item in source_ids],
            "league_name": ["1. Liga", "2. Liga", "Ženska Liga"],
            "league_max_players": [8, 8, 8],
        },
    )
    assert response.status_code == 302

    with app.app_context():
        season = Season.query.filter_by(name="2027").one()
        season_id = season.id
        new_groups = sorted(season.groups, key=lambda group: group.sort_order)
        assert [group.source_group_id for group in new_groups] == source_ids
        assert sum(len(group.memberships) for group in new_groups) == 12
        assert all(group.max_players == 8 for group in new_groups)
        assert season.setup_pending is True
        assert season.is_published is False

    movement_page = client.get(f"/admin/liga/sezona/{season_id}/premiki")
    movement_html = movement_page.get_data(as_text=True)
    assert movement_page.status_code == 200
    assert "1. Liga ⇄ 2. Liga" in movement_html
    assert "Ženska Liga" in movement_html
    assert "Potrdi premike" in movement_html
    move_values = re.findall(r'name="moves" value="([^"]+)"', movement_html)
    assert len(move_values) == 4
    assert str(new_player_id) not in " ".join(move_values)

    confirmation = client.post(
        f"/admin/liga/sezona/{season_id}/premiki",
        data={"moves": move_values},
    )
    assert confirmation.status_code == 302

    with app.app_context():
        season = db.session.get(Season, season_id)
        groups = sorted(season.groups, key=lambda group: group.sort_order)
        upper_ids = {membership.player_id for membership in groups[0].memberships}
        lower_ids = {membership.player_id for membership in groups[1].memberships}
        assert set(promoted_ids) <= upper_ids
        assert set(relegated_ids) <= lower_ids
        assert all(membership.player_id not in promoted_ids for membership in groups[1].memberships)
        assert all(membership.player_id not in relegated_ids for membership in groups[0].memberships)
        assert season.setup_pending is False
        assert season.is_published is True
        assert season.is_current is True
        assert db.session.get(Season, previous_id).is_current is False


def test_removing_copied_league_leaves_its_players_unassigned(app, client, admin):
    with app.app_context():
        previous = Season(
            name="2026",
            slug="liga-2026",
            starts_on=date(2026, 4, 1),
            ends_on=date(2026, 10, 1),
        )
        kept_group = LeagueGroup(name="1. Liga", season=previous, sort_order=0)
        removed_group = LeagueGroup(name="2. Liga", season=previous, sort_order=1)
        kept_player = Player(display_name="Ana Novak", slug="ana-novak")
        unassigned_player = Player(display_name="Boris Horvat", slug="boris-horvat")
        db.session.add_all([previous, kept_group, removed_group, kept_player, unassigned_player])
        db.session.flush()
        db.session.add_all([
            LeagueMembership(group=kept_group, player=kept_player, seed=1),
            LeagueMembership(group=removed_group, player=unassigned_player, seed=1),
        ])
        db.session.commit()
        kept_group_id = kept_group.id
        unassigned_player_id = unassigned_player.id

    login(client)
    response = client.post(
        "/admin/liga/sezona/nova",
        data={
            "name": "2027",
            "starts_on": "2027-04-01",
            "ends_on": "2027-10-01",
            "win_points": 2,
            "loss_points": 0,
            "carry_players": "y",
            "apply_promotions": "y",
            "promotions_per_boundary": 2,
            "league_source_group_id": [str(kept_group_id)],
            "league_name": ["1. Liga"],
            "league_max_players": [8],
        },
    )
    assert response.status_code == 302

    with app.app_context():
        season = Season.query.filter_by(name="2027").one()
        assert LeagueMembership.query.join(LeagueGroup).filter(
            LeagueGroup.season_id == season.id,
            LeagueMembership.player_id == unassigned_player_id,
        ).first() is None

