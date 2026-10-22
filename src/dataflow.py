from __future__ import annotations

from .cfg import CFG
from .tac import reads, writes


def liveness(cfg: CFG) -> tuple[dict[int, frozenset[str]], dict[int, frozenset[str]], int]:
    """Return (in, out, iterations). Standard backward analysis:
    in[b] = use[b] U (out[b] - def[b]);  out[b] = U in[s] for s in succ[b]."""
    use: dict[int, set[str]] = {}
    defs: dict[int, set[str]] = {}
    for b in cfg.blocks:
        seen: set[str] = set()
        u: set[str] = set()
        d: set[str] = set()
        for ins in b.instrs:
            for r in reads(ins):
                if r not in seen:
                    u.add(r)
            w = writes(ins)
            if w is not None:
                seen.add(w)
                d.add(w)
        use[b.index] = u
        defs[b.index] = d

    in_b: dict[int, set[str]] = {b.index: set() for b in cfg.blocks}
    out_b: dict[int, set[str]] = {b.index: set() for b in cfg.blocks}
    iterations = 0
    changed = True
    while changed:
        iterations += 1
        changed = False
        for b in sorted(cfg.blocks, key=lambda blk: blk.index, reverse=True):
            succs = cfg.successors[b.index]
            new_out: set[str] = set()
            if succs:
                new_out = set().union(*(in_b[s] for s in sorted(succs)))
            new_in = use[b.index] | (new_out - defs[b.index])
            if new_in != in_b[b.index] or new_out != out_b[b.index]:
                in_b[b.index] = new_in
                out_b[b.index] = new_out
                changed = True

    return ({k: frozenset(v) for k, v in in_b.items()},
            {k: frozenset(v) for k, v in out_b.items()},
            iterations)


def reaching_definitions(cfg: CFG) -> tuple[dict[int, frozenset[int]], int]:
    """Return (in, iterations) where in[b] is the set of global instruction
    indices that may reach the entry of block b. Forward analysis."""
    def_sites: dict[str, set[int]] = {}
    for b in cfg.blocks:
        for ins in b.instrs:
            w = writes(ins)
            if w is not None:
                def_sites.setdefault(w, set()).add(ins.index)

    gen: dict[int, set[int]] = {}
    kill: dict[int, set[int]] = {}
    for b in cfg.blocks:
        last: dict[str, int] = {}
        for ins in b.instrs:
            w = writes(ins)
            if w is not None:
                last[w] = ins.index
        g = set(last.values())
        k: set[int] = set()
        for v in last:
            k |= def_sites[v]
        k -= g
        gen[b.index] = g
        kill[b.index] = k

    in_b: dict[int, set[int]] = {b.index: set() for b in cfg.blocks}
    out_b: dict[int, set[int]] = {b.index: set(gen[b.index]) for b in cfg.blocks}
    iterations = 0
    changed = True
    while changed:
        iterations += 1
        changed = False
        for b in cfg.blocks:
            preds = cfg.preds[b.index]
            new_in: set[int] = set()
            if preds:
                new_in = set().union(*(out_b[p] for p in sorted(preds)))
            new_out = gen[b.index] | (new_in - kill[b.index])
            if new_in != in_b[b.index] or new_out != out_b[b.index]:
                in_b[b.index] = new_in
                out_b[b.index] = new_out
                changed = True

    return ({k: frozenset(v) for k, v in in_b.items()}, iterations)