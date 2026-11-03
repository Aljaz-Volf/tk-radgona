from ..extensions import db
from ..models import LeagueMembership, Match, Standing


def is_separate_league(group) -> bool:
    normalized = group.name.casefold()
    return "žensk" in normalized or "zensk" in normalized or "enska liga" in normalized


def group_display_key(group):
    """Show the separate women's league before the numbered league ladder."""
    return (0 if is_separate_league(group) else 1, group.sort_order, group.id or 0)


def groups_for_display(groups):
    return sorted(groups, key=group_display_key)


def _empty_standing(group_id: int, player_id: int) -> Standing:
    """Create a row whose counters are usable before the first database flush."""
    return Standing(
        group_id=group_id,
        player_id=player_id,
        played=0,
        wins=0,
        losses=0,
        points=0,
        sets_won=0,
        sets_lost=0,
        games_won=0,
        games_lost=0,
    )


def recalculate_group(group) -> list[Standing]:
    Standing.query.filter_by(group_id=group.id).delete()
    rows = {}
    for membership in LeagueMembership.query.filter_by(group_id=group.id).all():
        row = _empty_standing(group.id, membership.player_id)
        db.session.add(row)
        rows[membership.player_id] = row

    matches = Match.query.filter_by(group_id=group.id, status="completed").all()
    for match in matches:
        if match.player1_id not in rows:
            rows[match.player1_id] = _empty_standing(group.id, match.player1_id)
            db.session.add(rows[match.player1_id])
        if match.player2_id not in rows:
            rows[match.player2_id] = _empty_standing(group.id, match.player2_id)
            db.session.add(rows[match.player2_id])
        first, second = rows[match.player1_id], rows[match.player2_id]
        first.played += 1
        second.played += 1
        if match.winner_id == match.player1_id:
            first.wins += 1
            second.losses += 1
            first.points += match.season.win_points
            second.points += match.season.loss_points
        else:
            second.wins += 1
            first.losses += 1
            second.points += match.season.win_points
            first.points += match.season.loss_points
        for set_score in match.sets:
            first.games_won += set_score.player1_games
            first.games_lost += set_score.player2_games
            second.games_won += set_score.player2_games
            second.games_lost += set_score.player1_games
            if set_score.player1_games > set_score.player2_games:
                first.sets_won += 1
                second.sets_lost += 1
            else:
                second.sets_won += 1
                first.sets_lost += 1
    db.session.flush()
    return sorted(rows.values(), key=lambda row: (row.points, row.wins, row.set_difference, row.game_difference), reverse=True)


def ordered_standings(group):
    return sorted(group.standings, key=lambda row: (row.points, row.wins, row.set_difference, row.game_difference), reverse=True)

