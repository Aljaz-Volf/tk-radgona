from collections import Counter
from datetime import date

import pytest

from app.extensions import db
from app.models import LeagueGroup, LeagueMembership, Match, Player, Season
from app.services.fixtures import generate_round_robin, validate_round_robin
from tests.conftest import login


@pytest.mark.parametrize(
    ("player_count", "round_count", "match_count", "matches_per_round"),
    [(8, 14, 56, 4), (7, 14, 42, 3), (6, 10, 30, 3)],
)
def test_double_round_robin_sizes_and_safety(
    player_count, round_count, match_count, matches_per_round
):
    players = list(range(1, player_count + 1))
    rounds = generate_round_robin(players)
    matches = [match for round_item in rounds for match in round_item.matches]

    assert len(rounds) == round_count
    assert len(matches) == match_count
    assert all(len(round_item.matches) == matches_per_round for round_item in rounds)
    assert all(match.home_player_id != match.guest_player_id for match in matches)
    assert Counter(
        (match.home_player_id, match.guest_player_id) for match in matches
    ) == Counter(
        {(home, guest): 1 for home in players for guest in players if home != guest}
    )


def test_seven_players_have_exactly_two_byes_each():
    players = list(range(1, 8))
    rounds = generate_round_robin(players)
    appearances = Counter(
        player_id
        for round_item in rounds
        for match in round_item.matches
        for player_id in (match.home_player_id, match.guest_player_id)
    )
    assert {player_id: len(rounds) - appearances[player_id] for player_id in players} == {
        player_id: 2 for player_id in players
    }


@pytest.mark.parametrize("player_count", [6, 7, 8])
def test_home_guest_balance_and_mirrored_second_half(player_count):
    players = list(range(1, player_count + 1))
    rounds = generate_round_robin(players)
    per_half = len(rounds) // 2
    homes = Counter(
        match.home_player_id for round_item in rounds for match in round_item.matches
    )
    guests = Counter(
        match.guest_player_id for round_item in rounds for match in round_item.matches
    )

    assert homes == guests
    for first, second in zip(rounds[:per_half], rounds[per_half:]):
        assert second.round_number == first.round_number + per_half
        assert second.leg == 2
        assert second.matches == tuple(
            type(match)(match.guest_player_id, match.home_player_id)
            for match in first.matches
        )
    assert validate_round_robin(players, rounds).checks == {
        "pairs_twice": True,
        "balanced": True,
        "no_self_play": True,
        "one_match_per_round": True,
        "league_members_only": True,
    }


def _season_with_groups(app, player_counts=(4,)):
    with app.app_context():
        season = Season(
            name="2028",
            slug="2028-fixtures",
            starts_on=date(2028, 1, 1),
            ends_on=date(2028, 12, 31),
        )
        db.session.add(season)
        groups = []
        next_player = 1
        for group_index, player_count in enumerate(player_counts, 1):
            group = LeagueGroup(
                season=season, name=f"{group_index}. Liga", sort_order=group_index
            )
            db.session.add(group)
            groups.append(group)
            for seed in range(1, player_count + 1):
                player = Player(
                    display_name=f"Igralec {next_player}",
                    slug=f"fixture-player-{next_player}",
                )
                db.session.add(player)
                group.memberships.append(LeagueMembership(player=player, seed=seed))
                next_player += 1
        db.session.commit()
        return season.id, [group.id for group in groups]


def test_preview_refuses_existing_matches_without_explicit_replace(app, client, admin):
    season_id, (group_id,) = _season_with_groups(app)
    with app.app_context():
        group = db.session.get(LeagueGroup, group_id)
        first, second = [item.player for item in group.memberships[:2]]
        db.session.add(
            Match(
                season_id=season_id,
                group_id=group_id,
                player1_id=first.id,
                player2_id=second.id,
                status="scheduled",
            )
        )
        db.session.commit()

    login(client)
    options = {
        "season_id": season_id,
        "group_ids": [group_id],
        "start_date": "2028-01-07",
        "first_time": "18:00",
        "days_between_rounds": 7,
    }
    refused = client.post("/admin/api/tekme/razpored/predogled", json=options)
    assert refused.status_code == 400
    assert "že ima tekme" in refused.get_json()["error"]

    options["replace_unplayed_group_ids"] = [group_id]
    allowed = client.post("/admin/api/tekme/razpored/predogled", json=options)
    assert allowed.status_code == 200
    assert len(allowed.get_json()["groups"][0]["rounds"]) == 6


def test_preview_never_pairs_players_from_different_leagues(app, client, admin):
    season_id, group_ids = _season_with_groups(app, (4, 4))
    login(client)
    response = client.post(
        "/admin/api/tekme/razpored/predogled",
        json={
            "season_id": season_id,
            "group_ids": group_ids,
            "start_date": "2028-01-07",
            "first_time": "18:00",
            "days_between_rounds": 7,
        },
    )
    assert response.status_code == 200
    for group in response.get_json()["groups"]:
        allowed = {player["id"] for player in group["players"]}
        assert all(
            {match["home_player_id"], match["guest_player_id"]} <= allowed
            for round_item in group["rounds"]
            for match in round_item["matches"]
        )


def test_admin_can_preview_and_save_schedule_in_one_transaction(app, client, admin):
    season_id, (group_id,) = _season_with_groups(app)
    login(client)
    generator_page = client.get(f"/admin/tekme/generiraj?season_id={season_id}")
    assert generator_page.status_code == 200
    assert "Generiraj razpored" in generator_page.get_data(as_text=True)

    options = {
        "season_id": season_id,
        "group_ids": [group_id],
        "start_date": "2028-01-07",
        "first_time": "18:00",
        "days_between_rounds": 7,
    }
    html_preview = client.post(
        "/admin/tekme/razpored/predogled", data=options
    )
    assert html_preview.status_code == 200
    preview_html = html_preview.get_data(as_text=True)
    assert "Predogled razporeda" in preview_html
    assert preview_html.count("data-fixture-round") >= 6

    preview = client.post(
        "/admin/api/tekme/razpored/predogled", json=options
    ).get_json()
    saved = client.post("/admin/api/tekme/razpored/shrani", json=preview)
    assert saved.status_code == 201
    assert saved.get_json()["saved"] == 12

    with app.app_context():
        matches = Match.query.filter_by(group_id=group_id).all()
        assert len(matches) == 12
        assert all(match.generated for match in matches)
        assert {match.round_number for match in matches} == set(range(1, 7))
        assert {match.leg for match in matches} == {1, 2}


def test_save_rejects_self_play_without_partial_write(app, client, admin):
    season_id, (group_id,) = _season_with_groups(app)
    login(client)
    preview = client.post(
        "/admin/api/tekme/razpored/predogled",
        json={
            "season_id": season_id,
            "group_ids": [group_id],
            "start_date": "2028-01-07",
            "first_time": "18:00",
            "days_between_rounds": 7,
        },
    ).get_json()
    first_match = preview["groups"][0]["rounds"][0]["matches"][0]
    first_match["guest_player_id"] = first_match["home_player_id"]
    response = client.post("/admin/api/tekme/razpored/shrani", json=preview)
    assert response.status_code == 400
    assert "sam proti sebi" in response.get_json()["error"]
    with app.app_context():
        assert Match.query.filter_by(group_id=group_id).count() == 0
