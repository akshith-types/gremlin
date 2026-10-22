"""Puzzle enrichment: TAC diffs, difficulty rating and a three-step hint ladder.

Everything here is a pure function of the original/mutant programs and the CFG,
so the output stays deterministic (the test-suite relies on that).
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass

from .cfg import CFG
from .tac import Instr, format_tac

# Base difficulty per operator: how hard the *concept* is to spot.
_BASE: dict[str, int] = {
    "M4_OFF_BY_ONE_BRANCH": 1,
    "M5_UNSOUND_COMMUTATIVITY": 1,
    "M2_UNSOUND_ALGEBRA": 2,
    "M1_DEAD_STORE": 2,
    "M3_UNSOUND_COPY_PROP": 3,
    "M6_UNSOUND_STORE_FORWARDING": 3,
}

# Which compiler-theory area the bug lives in (hint level 2).
_CATEGORY: dict[str, str] = {
    "M1_DEAD_STORE": "Liveness analysis: a store was removed that a later read still needs.",
    "M2_UNSOUND_ALGEBRA": "Algebraic simplification: an arithmetic identity was applied where it does not hold for integers.",
    "M3_UNSOUND_COPY_PROP": "Reaching definitions: a copy was propagated into a place it never reaches.",
    "M4_OFF_BY_ONE_BRANCH": "Control flow: a branch test was changed at its boundary value.",
    "M5_UNSOUND_COMMUTATIVITY": "Algebraic simplification: operands of a non-commutative operator "
                                "(subtraction, division, modulo or string concatenation) were reordered.",
    "M6_UNSOUND_STORE_FORWARDING": "Memory dependence: a load from an array was replaced by a value "
                                   "stored to a possibly different element.",
}


@dataclass(frozen=True)
class Explanation:
    diff: str
    changed: tuple[int, ...]       # instruction indices altered or deleted
    difficulty: str                # Easy / Medium / Hard
    score: int
    in_loop: bool
    hints: tuple[str, str, str]


def changed_indices(original: tuple[Instr, ...], mutant: tuple[Instr, ...]) -> tuple[int, ...]:
    mut = {i.index: i for i in mutant}
    return tuple(i.index for i in original if mut.get(i.index) != i)


def unified_diff(original: tuple[Instr, ...], mutant: tuple[Instr, ...]) -> str:
    a = format_tac(original).splitlines()
    b = format_tac(mutant).splitlines()
    lines = difflib.unified_diff(a, b, "original.tac", "mutant.tac", lineterm="", n=2)
    return "\n".join(lines)


def blocks_in_loops(cfg: CFG) -> frozenset[int]:
    """A block is in a loop iff it can reach itself through at least one edge."""
    inside: set[int] = set()
    for start in cfg.successors:
        seen: set[int] = set()
        stack = list(cfg.successors[start])
        while stack:
            b = stack.pop()
            if b == start:
                inside.add(start)
                break
            if b in seen:
                continue
            seen.add(b)
            stack.extend(cfg.successors[b])
    return frozenset(inside)


def _label(score: int) -> str:
    if score <= 2:
        return "Easy"
    if score == 3:
        return "Medium"
    return "Hard"


def explain(operator: str, original: tuple[Instr, ...], mutant: tuple[Instr, ...],
            cfg: CFG, evidence: str, original_output: tuple[str, ...],
            mutant_output: tuple[str, ...]) -> Explanation:
    changed = changed_indices(original, mutant)
    loops = blocks_in_loops(cfg)
    in_loop = any(cfg.block_of.get(i, -1) in loops for i in changed)

    score = _BASE.get(operator, 2)
    if in_loop:
        score += 1  # the wrong value is re-used on every iteration: harder to trace by hand
    if original_output and mutant_output and original_output[0] == mutant_output[0]:
        score += 1  # the first output still looks right, the symptom appears later
    score = min(score, 5)

    where = (", ".join(f"#{i} (block B{cfg.block_of[i]})" for i in changed)
             if changed else "somewhere in the program")
    hints = (
        f"Symptom - {evidence}.",
        f"Category - {_CATEGORY.get(operator, 'an unsound optimisation was applied.')}",
        f"Location - the broken instruction is {where}.",
    )
    return Explanation(
        diff=unified_diff(original, mutant),
        changed=changed,
        difficulty=_label(score),
        score=score,
        in_loop=in_loop,
        hints=hints,
    )
