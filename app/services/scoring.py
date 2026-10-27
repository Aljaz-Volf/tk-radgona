import re
from dataclasses import dataclass


SET_RE = re.compile(r"^\s*(\d{1,2})\s*[-:]\s*(\d{1,2})(?:\s*\((\d{1,2})\s*[-:]\s*(\d{1,2})\))?\s*$")


@dataclass(frozen=True)
class ParsedSet:
    player1_games: int
    player2_games: int
    tiebreak1: int | None = None
    tiebreak2: int | None = None

    @property
    def winner(self):
        return 1 if self.player1_games > self.player2_games else 2


def _valid_standard_set(a: int, b: int) -> bool:
    high, low = max(a, b), min(a, b)
    if high == 6 and 0 <= low <= 4:
        return True
    if high == 7 and low in {5, 6}:
        return True
    return False


def _valid_match_tiebreak(a: int, b: int) -> bool:
    return max(a, b) >= 10 and abs(a - b) >= 2


def parse_score(score: str, best_of: int = 3) -> tuple[list[ParsedSet], int]:
    if best_of not in {3, 5}:
        raise ValueError("Podprti sta le tekmi na dva ali tri dobljene nize.")
    raw_sets = [part.strip() for part in score.split(",") if part.strip()]
    needed = best_of // 2 + 1
    if not needed <= len(raw_sets) <= best_of:
        raise ValueError(f"Rezultat mora vsebovati od {needed} do {best_of} nizov.")

    parsed = []
    wins = [0, 0]
    for index, raw in enumerate(raw_sets):
        match = SET_RE.match(raw)
        if not match:
            raise ValueError(f"Niz »{raw}« ni v obliki 6-4 ali 7-6 (7-4).")
        a, b = int(match.group(1)), int(match.group(2))
        tb1 = int(match.group(3)) if match.group(3) else None
        tb2 = int(match.group(4)) if match.group(4) else None
        if a == b:
            raise ValueError("Niz ne more biti neodločen.")
        is_last = index == len(raw_sets) - 1
        if not _valid_standard_set(a, b) and not (is_last and _valid_match_tiebreak(a, b)):
            raise ValueError(f"Niz »{raw}« ni veljaven zaključen teniški niz.")
        if (tb1 is None) != (tb2 is None):
            raise ValueError("Rezultat podaljšane igre mora vsebovati obe vrednosti.")
        item = ParsedSet(a, b, tb1, tb2)
        parsed.append(item)
        wins[item.winner - 1] += 1
        if wins[item.winner - 1] == needed and not is_last:
            raise ValueError("Po odločilnem nizu ni dovoljeno dodajati nizov.")

    if max(wins) != needed:
        raise ValueError("Rezultat ne določa zmagovalca tekme.")
    return parsed, 1 if wins[0] > wins[1] else 2


def format_score(match) -> str:
    return ", ".join(f"{item.player1_games}-{item.player2_games}" for item in match.sets)

