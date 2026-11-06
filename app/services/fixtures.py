"""Pure round-robin fixture generation and validation.

The functions in this module deliberately know nothing about Flask or the
database.  Keeping the Berger-table implementation here makes it useful to
the HTML workflow, the JSON API and unit tests alike.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class Fixture:
    home_player_id: int
    guest_player_id: int


@dataclass(frozen=True)
class Round:
    round_number: int
    leg: int
    matches: tuple[Fixture, ...]


@dataclass(frozen=True)
class ScheduleValidation:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    checks: Mapping[str, bool]

    @property
    def is_valid(self) -> bool:
        return not self.errors


def generate_round_robin(player_ids: Iterable[int]) -> list[Round]:
    """Return a balanced double round-robin using the circle method.

    Input order is stable and should therefore already represent the desired
    rank/seed order.  The second half mirrors the first exactly, with home and
    guest swapped.  A ``None`` slot is added for odd-sized leagues and all
    pairings that contain it are omitted.
    """

    players = list(player_ids)
    if len(players) != len(set(players)):
        raise ValueError("Igralci v ligi se ne smejo ponavljati.")
    if len(players) < 2:
        raise ValueError("Za razpored sta potrebna vsaj dva igralca.")

    slots: list[int | None] = [*players]
    if len(slots) % 2:
        slots.append(None)

    slot_count = len(slots)
    first_half: list[Round] = []
    for round_index in range(slot_count - 1):
        fixtures: list[Fixture] = []
        for pair_index in range(slot_count // 2):
            left = slots[pair_index]
            right = slots[slot_count - 1 - pair_index]

            # Standard Berger orientation: the fixed player's side alternates;
            # the remaining left-hand positions are home.  This gives every
            # real player a home/guest difference of at most one in each half,
            # including leagues that use a bye slot.
            if pair_index == 0 and round_index % 2:
                home, guest = right, left
            else:
                home, guest = left, right

            if home is not None and guest is not None:
                fixtures.append(Fixture(home, guest))

        first_half.append(Round(round_index + 1, 1, tuple(fixtures)))
        slots = [slots[0], slots[-1], *slots[1:-1]]

    rounds_per_half = len(first_half)
    second_half = [
        Round(
            round_item.round_number + rounds_per_half,
            2,
            tuple(
                Fixture(match.guest_player_id, match.home_player_id)
                for match in round_item.matches
            ),
        )
        for round_item in first_half
    ]
    return [*first_half, *second_half]


def validate_round_robin(
    player_ids: Iterable[int], rounds: Sequence[Round]
) -> ScheduleValidation:
    """Validate hard safety rules and report editable schedule warnings.

    Unknown players and self-play are hard errors.  Completeness, balance and
    at-most-one-match-per-round are warnings because the preview editor is
    intentionally allowed to create an exceptional schedule before saving.
    """

    players = set(player_ids)
    errors: list[str] = []
    warnings: list[str] = []
    ordered_pairs: Counter[tuple[int, int]] = Counter()
    unordered_pairs: Counter[tuple[int, int]] = Counter()
    half_home: dict[int, Counter[int]] = {1: Counter(), 2: Counter()}
    half_guest: dict[int, Counter[int]] = {1: Counter(), 2: Counter()}
    round_conflicts = False
    self_play = False
    unknown_player = False

    for round_item in rounds:
        seen_in_round: Counter[int] = Counter()
        for match in round_item.matches:
            home = match.home_player_id
            guest = match.guest_player_id
            if home == guest:
                self_play = True
            if home not in players or guest not in players:
                unknown_player = True
            seen_in_round.update((home, guest))
            ordered_pairs[(home, guest)] += 1
            unordered_pairs[tuple(sorted((home, guest)))] += 1
            if round_item.leg in (1, 2):
                half_home[round_item.leg][home] += 1
                half_guest[round_item.leg][guest] += 1
        if any(count > 1 for count in seen_in_round.values()):
            round_conflicts = True

    if self_play:
        errors.append("Igralec ne more igrati sam proti sebi.")
    if unknown_player:
        errors.append("V razporedu je igralec, ki ne pripada izbrani ligi.")

    expected_pairs = {tuple(sorted(pair)) for pair in combinations(players, 2)}
    pairs_twice = (
        set(unordered_pairs) == expected_pairs
        and all(unordered_pairs[pair] == 2 for pair in expected_pairs)
        and all(ordered_pairs[(first, second)] == 1 and ordered_pairs[(second, first)] == 1
                for first, second in expected_pairs)
    )
    if not pairs_twice:
        warnings.append("Vsak par mora igrati dvakrat, enkrat v vsaki vlogi.")
    if round_conflicts:
        warnings.append("Igralec je v istem krogu razporejen več kot enkrat.")

    per_half_balanced = True
    whole_season_balanced = True
    for player_id in players:
        for leg in (1, 2):
            if abs(half_home[leg][player_id] - half_guest[leg][player_id]) > 1:
                per_half_balanced = False
        total_home = sum(half_home[leg][player_id] for leg in (1, 2))
        total_guest = sum(half_guest[leg][player_id] for leg in (1, 2))
        if total_home != total_guest:
            whole_season_balanced = False
    if not per_half_balanced or not whole_season_balanced:
        warnings.append("Razmerje domačih in gostujočih tekem ni uravnoteženo.")

    return ScheduleValidation(
        errors=tuple(errors),
        warnings=tuple(warnings),
        checks={
            "pairs_twice": pairs_twice,
            "balanced": per_half_balanced and whole_season_balanced,
            "no_self_play": not self_play,
            "one_match_per_round": not round_conflicts,
            "league_members_only": not unknown_player,
        },
    )
