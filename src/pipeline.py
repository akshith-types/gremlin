from __future__ import annotations

import time
from dataclasses import dataclass

from . import cfg as cfgmod
from . import dataflow
from . import explain as explainmod
from . import frontend
from . import interpreter
from . import mutate
from . import semantic
from . import tac as tacmod
from .interpreter import RunResult
from .mutate import Mutant

STAGES = ("parse", "semantic", "tac", "cfg", "liveness", "reaching_defs", "mutate", "execute")


@dataclass(frozen=True)
class Puzzle:
    mutant: Mutant
    original_output: tuple[str, ...]
    mutant_output: tuple[str, ...]
    evidence: str
    explanation: explainmod.Explanation


@dataclass(frozen=True)
class PipelineResult:
    tac: tuple[tacmod.Instr, ...]
    num_blocks: int
    live_iterations: int
    rd_iterations: int
    puzzles: tuple[Puzzle, ...]
    discarded: tuple[str, ...]
    source: str
    declared: tuple[str, ...]
    cfg: cfgmod.CFG
    live_in: dict[int, frozenset[str]]
    live_out: dict[int, frozenset[str]]
    rd_in: dict[int, frozenset[int]]
    original_output: tuple[str, ...]
    candidates: int                       # mutants generated before differential execution
    steps_original: int                   # TAC instructions in the original program
    timings: tuple[tuple[str, float], ...]  # (stage, seconds); NOT part of determinism checks


def _evidence(a: RunResult, b: RunResult) -> str:
    if a.trap != b.trap:
        return f"original: {a.trap or 'clean run'} | mutant: {b.trap or 'clean run'}"
    for i, (x, y) in enumerate(zip(a.output, b.output)):
        if x != y:
            return f"first divergence at output line {i}: original '{x}' vs mutant '{y}'"
    return "outputs differ in length"


class _Clock:
    """Tiny stage timer: lap(name) records the time since the previous lap."""

    def __init__(self) -> None:
        self._t = time.perf_counter()
        self.laps: list[tuple[str, float]] = []

    def lap(self, name: str) -> None:
        now = time.perf_counter()
        self.laps.append((name, now - self._t))
        self._t = now


def run_pipeline(source: str, max_mutants: int, max_steps: int) -> PipelineResult:
    clock = _Clock()
    program = frontend.parse_source(source)
    clock.lap("parse")
    declared = semantic.analyze(program)
    clock.lap("semantic")
    tac = tacmod.generate(program)
    semantic.check_initialized(tac)
    clock.lap("tac")
    graph = cfgmod.build_cfg(tac)
    clock.lap("cfg")
    live_in, live_out, live_iters = dataflow.liveness(graph)
    clock.lap("liveness")
    rd_in, rd_iters = dataflow.reaching_definitions(graph)
    clock.lap("reaching_defs")
    mutants = mutate.find_mutants(tac, graph, live_out, rd_in, declared, max_mutants)
    clock.lap("mutate")
    original = interpreter.run(tac, max_steps)
    puzzles: list[Puzzle] = []
    discarded: list[str] = []
    for m in mutants:
        result = interpreter.run(m.instrs, max_steps)
        if result.output != original.output or result.trap != original.trap:
            ev = _evidence(original, result)
            info = explainmod.explain(m.operator, tac, m.instrs, graph, ev,
                                      original.output, result.output)
            puzzles.append(Puzzle(m, original.output, result.output, ev, info))
        else:
            discarded.append(m.ident)
    clock.lap("execute")
    return PipelineResult(
        tac=tac,
        num_blocks=len(graph.blocks),
        live_iterations=live_iters,
        rd_iterations=rd_iters,
        puzzles=tuple(puzzles),
        discarded=tuple(discarded),
        source=source,
        declared=declared,
        cfg=graph,
        live_in=live_in,
        live_out=live_out,
        rd_in=rd_in,
        original_output=original.output,
        candidates=len(mutants),
        steps_original=len(tac),
        timings=tuple(clock.laps),
    )
