from ..extensions import db
from ..models import LeagueMembership, Match, Standing


def recalculate_group(group) -> list[Standing]:
    Standing.query.filter_by(group_id=group.id).delete()
    rows = {}
    for membership in LeagueMembership.query.filter_by(group_id=group.id).all():
        row = Standing(group_id=group.id, player_id=membership.player_id)
        db.session.add(row)
        rows[membership.player_id] = row

    matches = Match.query.filter_by(group_id=group.id, status="completed").all()
    for match in matches:
        if match.player1_id not in rows:
            rows[match.player1_id] = Standing(group_id=group.id, player_id=match.player1_id)
            db.session.add(rows[match.player1_id])
        if match.player2_id not in rows:
            rows[match.player2_id] = Standing(group_id=group.id, player_id=match.player2_id)
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

