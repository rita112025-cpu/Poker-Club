"""Independent reference settlement, written by a separate agent from the contract text ONLY
(it never saw the engine code). Used by the differential tests as a second, unrelated
implementation; do not "tidy" it to look like the engine. Behaviour on cases that cannot
arise in a real hand (a folded seat holding the largest commitment) differs on purpose and
the tests only feed it reachable inputs.
"""


def settle(committed, folded, strength, button):
    seats = list(committed)
    live = [s for s in seats if s not in folded]
    if not live:
        raise ValueError("no non-folded seat")
    net = {s: -committed[s] for s in seats}
    c = dict(committed)

    # 1. uncalled return
    top = max(c.values())
    if len(c) > 1:
        top_seat = max(c, key=lambda s: c[s])
        second = max(v for s, v in c.items() if s != top_seat)
        if top > second:
            net[top_seat] += top - second
            c[top_seat] = second

    # 2. layers
    levels = sorted({v for v in c.values() if v > 0})
    layers = []  # [amount, frozenset eligible]
    prev = 0
    for lv in levels:
        amount = sum(min(v, lv) - min(v, prev) for v in c.values())
        elig = frozenset(s for s in live if c[s] >= lv)
        layers.append([amount, elig])
        prev = lv

    # layers with nobody eligible (only possible if a folded seat out-committed
    # every live seat): fold their chips into the pot below; if none, the pot above.
    pots = []
    orphan = 0
    for amount, elig in layers:
        if not elig:
            if pots:
                pots[-1][0] += amount
            else:
                orphan += amount
            continue
        # 3. merge adjacent identical eligible sets
        if pots and pots[-1][1] == elig:
            pots[-1][0] += amount
        else:
            pots.append([amount + orphan, elig])
            orphan = 0
    # note: merging after an orphan absorb keeps the same eligible set, fine.

    order_key = lambda s: (0, s) if s > button else (1, s)  # noqa: E731
    # 4. distribute
    for amount, elig in pots:
        if len(elig) == 1:
            net[next(iter(elig))] += amount
            continue
        best = max(strength[s] for s in elig)
        winners = sorted((s for s in elig if strength[s] == best), key=order_key)
        share, rem = divmod(amount, len(winners))
        for i, w in enumerate(winners):
            net[w] += share + (1 if i < rem else 0)
    return net
