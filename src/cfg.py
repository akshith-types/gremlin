from __future__ import annotations

from dataclasses import dataclass

from .tac import Instr, Op


@dataclass(frozen=True)
class Block:
    index: int
    instrs: tuple[Instr, ...]


@dataclass(frozen=True)
class CFG:
    blocks: tuple[Block, ...]
    successors: dict[int, frozenset[int]]
    preds: dict[int, frozenset[int]]
    block_of: dict[int, int]  # instruction index -> block index


def _target(ins: Instr) -> str | None:
    """Jump target label: `goto` keeps it in arg1, `if_false` keeps it in dest."""
    return ins.arg1 if ins.op == Op.GOTO else ins.dest


def build_cfg(tac: tuple[Instr, ...]) -> CFG:
    if not tac:
        raise ValueError("cannot build a CFG from an empty instruction stream")

    label_at: dict[str, int] = {}
    for pos, ins in enumerate(tac):
        if ins.op == Op.LABEL and ins.arg1 is not None:
            label_at[ins.arg1] = pos

    leaders: set[int] = {0}
    for pos, ins in enumerate(tac):
        if ins.op == Op.LABEL:
            leaders.add(pos)
        elif ins.op in (Op.GOTO, Op.IF_FALSE):
            tgt = _target(ins)
            if tgt is not None and tgt in label_at:
                leaders.add(label_at[tgt])
            if pos + 1 < len(tac):
                leaders.add(pos + 1)

    starts = sorted(p for p in leaders if 0 <= p < len(tac))
    blocks: list[Block] = []
    block_of: dict[int, int] = {}
    for bi, start in enumerate(starts):
        end = starts[bi + 1] if bi + 1 < len(starts) else len(tac)
        chunk = tuple(tac[start:end])
        blocks.append(Block(index=bi, instrs=chunk))
        for ins in chunk:
            block_of[ins.index] = bi

    num_blocks = len(blocks)
    successors: dict[int, set[int]] = {b.index: set() for b in blocks}
    for b in blocks:
        last = b.instrs[-1]
        nxt = b.index + 1
        tgt = _target(last)
        if last.op == Op.IF_FALSE and tgt is not None and tgt in label_at:
            successors[b.index].add(block_of[label_at[tgt]])
            if nxt < num_blocks:
                successors[b.index].add(nxt)
        elif last.op == Op.GOTO and tgt is not None and tgt in label_at:
            successors[b.index].add(block_of[label_at[tgt]])
        elif last.op != Op.HALT and nxt < num_blocks:
            successors[b.index].add(nxt)

    preds: dict[int, set[int]] = {b.index: set() for b in blocks}
    for src, succs in successors.items():
        for dst in succs:
            preds[dst].add(src)

    return CFG(
        blocks=tuple(blocks),
        successors={k: frozenset(v) for k, v in successors.items()},
        preds={k: frozenset(v) for k, v in preds.items()},
        block_of=block_of,
    )