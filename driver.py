#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
import tracemalloc
from pathlib import Path

from config import Config, ConfigError, load_config
from src import frontend, pipeline, report, semantic
from src.tac import format_tac

_USE_COLOR = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def _bug_cards(result: pipeline.PipelineResult) -> list[dict[str, object]]:
    cards: list[dict[str, object]] = []
    for p in result.puzzles:
        e = p.explanation
        cards.append({
            "id": p.mutant.ident,
            "operator": p.mutant.operator,
            "difficulty": e.difficulty,
            "difficulty_score": e.score,
            "inside_loop": e.in_loop,
            "violated_property": p.mutant.violated,
            "location": p.mutant.location,
            "changed_instructions": list(e.changed),
            "description": p.mutant.description,
            "original_output": list(p.original_output),
            "mutant_output": list(p.mutant_output),
            "evidence": p.evidence,
            "diff": e.diff,
            "hints": list(e.hints),
        })
    return cards


def _metrics(result: pipeline.PipelineResult) -> dict[str, object]:
    total = sum(t for _s, t in result.timings)
    return {
        "tac_instructions": result.steps_original,
        "basic_blocks": result.num_blocks,
        "liveness_passes": result.live_iterations,
        "reaching_def_passes": result.rd_iterations,
        "mutants_tried": result.candidates,
        "confirmed_bugs": len(result.puzzles),
        "stage_ms": {name: round(t * 1000, 4) for name, t in result.timings},
        "total_ms": round(total * 1000, 4),
    }


def _bench(source: str, cfg: Config, runs: int) -> dict[str, object]:
    """Wall-clock per stage (mean/min over `runs`) plus peak Python heap for one run."""
    per_stage: dict[str, list[float]] = {s: [] for s in pipeline.STAGES}
    totals: list[float] = []
    for _ in range(runs):
        t0 = time.perf_counter()
        res = pipeline.run_pipeline(source, cfg.max_mutants, cfg.max_steps)
        totals.append(time.perf_counter() - t0)
        for name, t in res.timings:
            per_stage[name].append(t)
    tracemalloc.start()
    pipeline.run_pipeline(source, cfg.max_mutants, cfg.max_steps)
    _cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "runs": runs,
        "total_ms_mean": round(1000 * sum(totals) / runs, 4),
        "total_ms_min": round(1000 * min(totals), 4),
        "peak_heap_kib": round(peak / 1024, 1),
        "stages": {s: {"mean_ms": round(1000 * sum(v) / len(v), 4), "min_ms": round(1000 * min(v), 4)}
                   for s, v in per_stage.items() if v},
    }


def _print_bench(b: dict[str, object]) -> None:
    stages = b["stages"]
    assert isinstance(stages, dict)
    print(f"  benchmark    : {b['runs']} runs, total mean {b['total_ms_mean']} ms "
          f"(min {b['total_ms_min']} ms), peak heap {b['peak_heap_kib']} KiB")
    for name, v in stages.items():
        print(f"    {name:14s} mean {v['mean_ms']:9.4f} ms   min {v['min_ms']:9.4f} ms")


def _run_batch(directory: Path, cfg: Config) -> int:
    rows: list[dict[str, object]] = []
    files = sorted(directory.glob("*.gc"))
    if not files:
        sys.stderr.write(f"error: no .gc files found in '{directory}'\n")
        return 2
    print(f"{'file':20s} {'tac':>5s} {'blk':>4s} {'tried':>6s} {'bugs':>5s} {'ms':>9s}  status")
    for f in files:
        try:
            res = pipeline.run_pipeline(f.read_text(encoding="utf-8"), cfg.max_mutants, cfg.max_steps)
        except (frontend.FrontendError, semantic.SemanticError) as exc:
            kind = "syntax" if isinstance(exc, frontend.FrontendError) else "semantic"
            print(f"{f.name:20s} {'-':>5s} {'-':>4s} {'-':>6s} {'-':>5s} {'-':>9s}  {kind} error")
            rows.append({"file": f.name, "status": f"{kind} error", "detail": str(exc)})
            continue
        ms = sum(t for _s, t in res.timings) * 1000
        print(f"{f.name:20s} {res.steps_original:5d} {res.num_blocks:4d} {res.candidates:6d} "
              f"{len(res.puzzles):5d} {ms:9.3f}  ok")
        rows.append({"file": f.name, "status": "ok", **_metrics(res)})
    try:
        cfg.out_dir.mkdir(parents=True, exist_ok=True)
        (cfg.out_dir / "batch_summary.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        sys.stderr.write(f"error: cannot write batch summary: {exc.strerror or exc}\n")
        return 3
    print(f"summary written to {cfg.out_dir}/batch_summary.json")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gremlin",
                                 description="GREMLIN - adversarial puzzle compiler")
    ap.add_argument("input", nargs="?", default=None,
                    help="source file (.gc); default: GREMLIN_INPUT from .env")
    ap.add_argument("--out", default=None, help="output directory (default: GREMLIN_OUT)")
    ap.add_argument("--max-mutants", type=int, default=None,
                    help="cap on generated mutants (default: GREMLIN_MAX_MUTANTS)")
    ap.add_argument("--debug", action="store_true", help="verbose diagnostics")
    ap.add_argument("--bench", type=int, metavar="N", default=0,
                    help="repeat the pipeline N times and report per-stage timing and peak memory")
    ap.add_argument("--batch", metavar="DIR", default=None,
                    help="run every .gc file in DIR and print a summary table")
    ap.add_argument("--no-report", action="store_true", help="skip report.html / cfg.dot")
    args = ap.parse_args(argv)

    try:
        base = load_config()
    except ConfigError as exc:
        sys.stderr.write(f"configuration error: {exc}\n")
        return 2

    cfg = Config(
        input_path=Path(args.input) if args.input else base.input_path,
        out_dir=Path(args.out) if args.out else base.out_dir,
        debug=(args.debug or base.debug),
        max_mutants=(args.max_mutants if args.max_mutants is not None else base.max_mutants),
        max_steps=base.max_steps,
    )

    if args.batch:
        return _run_batch(Path(args.batch), cfg)

    try:
        source = cfg.input_path.read_text(encoding="utf-8")
    except OSError as exc:
        reason = exc.strerror or str(exc)
        sys.stderr.write(f"error: cannot read input file '{cfg.input_path}': {reason}\n")
        return 2

    try:
        result = pipeline.run_pipeline(source, cfg.max_mutants, cfg.max_steps)
    except frontend.FrontendError as exc:
        sys.stderr.write(f"syntax error: {exc}\n")
        return 1
    except semantic.SemanticError as exc:
        sys.stderr.write(f"semantic error: {exc}\n")
        return 1

    print(_c("1", "GREMLIN - adversarial puzzle compiler"))
    print(f"  input        : {cfg.input_path}")
    print(f"  tac          : {len(result.tac)} instructions, {result.num_blocks} basic blocks")
    print(f"  dataflow     : liveness converged in {result.live_iterations} pass(es), "
          f"reaching-defs in {result.rd_iterations}")
    print(f"  mutants      : {result.candidates} tried, {len(result.puzzles)} confirmed, "
          f"{len(result.discarded)} rejected")
    for p in result.puzzles:
        tag = _c("31;1", "[PUZZLE]")
        print(f"  {tag} {p.mutant.ident:10s} {p.mutant.operator:29s} "
              f"{p.explanation.difficulty:6s} {p.evidence}")
    for d in result.discarded:
        print(f"  {_c('2', '[skip]')}   {d:10s} mutant behaved identically; not a puzzle")
    if not result.puzzles:
        print("  note: no confirmed puzzles for this input (try more arithmetic / branches)")

    try:
        cfg.out_dir.mkdir(parents=True, exist_ok=True)
        (cfg.out_dir / "original.tac").write_text(format_tac(result.tac), encoding="utf-8")
        for p in result.puzzles:
            (cfg.out_dir / f"mutant_{p.mutant.ident}.tac").write_text(
                format_tac(p.mutant.instrs), encoding="utf-8")
        (cfg.out_dir / "bugcards.json").write_text(
            json.dumps(_bug_cards(result), indent=2) + "\n", encoding="utf-8")
        (cfg.out_dir / "metrics.json").write_text(
            json.dumps(_metrics(result), indent=2) + "\n", encoding="utf-8")
        if not args.no_report:
            (cfg.out_dir / "report.html").write_text(
                report.render_html(result, cfg.input_path.name), encoding="utf-8")
            (cfg.out_dir / "cfg.dot").write_text(report.render_dot(result), encoding="utf-8")
    except OSError as exc:
        reason = exc.strerror or str(exc)
        sys.stderr.write(f"error: cannot write artifacts to '{cfg.out_dir}': {reason}\n")
        return 3

    extra = "" if args.no_report else ", report.html, cfg.dot"
    print(f"  artifacts    : {cfg.out_dir}/original.tac, mutant_*.tac, bugcards.json, metrics.json{extra}")

    if args.bench > 0:
        _print_bench(_bench(source, cfg, args.bench))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
