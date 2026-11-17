"""Independent seven-card evaluator, written by a separate agent from the ranking rules ONLY
(a counting algorithm that never scores five-card subsets, unlike best_of_seven). Its author
verified it by exact enumeration of all 133,784,560 hands (the published category counts), and
the same enumeration was re-run before it was vendored. Used as a second implementation in the
differential tests; do not rewrite it to resemble the engine.
"""

"""Seven-card Texas hold'em evaluator using rank/suit counting (no subset search)."""

_RANKS = {
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "J": 11,
    "Q": 12,
    "K": 13,
    "A": 14,
}


def _straight_top(present: set[int]) -> int:
    """Highest top card of a 5-run in the rank set (wheel top = 5), or 0."""
    s = set(present)
    if 14 in s:
        s.add(1)
    for top in range(14, 4, -1):
        if all((top - i) in s for i in range(5)):
            return top
    return 0


def evaluate7(cards: list[str]) -> tuple[int, tuple[int, ...]]:
    counts: dict[int, int] = {}
    by_suit: dict[str, set[int]] = {}
    for c in cards:
        r = _RANKS[c[:-1]]
        counts[r] = counts.get(r, 0) + 1
        by_suit.setdefault(c[-1], set()).add(r)

    flush_ranks: list[int] = []
    for ranks in by_suit.values():
        if len(ranks) >= 5:
            flush_ranks = sorted(ranks, reverse=True)

    if flush_ranks:
        sf = _straight_top(set(flush_ranks))
        if sf:
            return 8, (sf,)

    desc = sorted(counts, reverse=True)
    quads = [r for r in desc if counts[r] == 4]
    trips = [r for r in desc if counts[r] == 3]
    pairs = [r for r in desc if counts[r] == 2]

    if quads:
        q = quads[0]
        return 7, (q, max(r for r in desc if r != q))

    if trips and (len(trips) > 1 or pairs):
        t = trips[0]
        under = [r for r in desc if r != t and counts[r] >= 2]
        return 6, (t, under[0])

    if flush_ranks:
        return 5, tuple(flush_ranks[:5])

    st = _straight_top(set(desc))
    if st:
        return 4, (st,)

    if trips:
        t = trips[0]
        return 3, (t,) + tuple([r for r in desc if r != t][:2])

    if len(pairs) >= 2:
        hi, lo = pairs[0], pairs[1]
        kicker = max(r for r in desc if r != hi and r != lo)
        return 2, (hi, lo, kicker)

    if pairs:
        p = pairs[0]
        return 1, (p,) + tuple([r for r in desc if r != p][:3])

    return 0, tuple(desc[:5])
