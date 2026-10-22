from __future__ import annotations

from pathlib import Path

import pytest

from src import cfg as cfgmod
from src import dataflow
from src import frontend
from src import interpreter
from src import mutate
from src import pipeline as pl
from src import semantic
from src import tac as tacmod

DATA = Path(__file__).parent / "data"
MAX_STEPS = 200000


def _source(name: str) -> str:
    return (DATA / name).read_text(encoding="utf-8")


def test_1_valid_input_produces_tac_and_confirmed_puzzle() -> None:
    result = pl.run_pipeline(_source("valid1.gc"), max_mutants=6, max_steps=MAX_STEPS)
    assert len(result.tac) > 0
    assert result.num_blocks >= 1
    original = interpreter.run(result.tac, MAX_STEPS)
    assert original.trap is None
    assert original.output == ("c=13", "r=6")  # 7/2=3, 3*2=6, 7+6=13
    assert len(result.puzzles) >= 1
    assert any(p.mutant.operator == mutate.OP_ALGEBRA for p in result.puzzles)


def test_2_syntax_error_is_reported_friendly() -> None:
    with pytest.raises(frontend.FrontendError) as excinfo:
        pl.run_pipeline(_source("syntax_err.gc"), max_mutants=1, max_steps=MAX_STEPS)
    assert "line" in str(excinfo.value)


def test_3_semantic_error_undeclared_variable() -> None:
    with pytest.raises(semantic.SemanticError) as excinfo:
        pl.run_pipeline(_source("semantic_err.gc"), max_mutants=1, max_steps=MAX_STEPS)
    assert "'b'" in str(excinfo.value)


def test_4_empty_input_rejected_friendly() -> None:
    with pytest.raises(frontend.FrontendError) as excinfo:
        pl.run_pipeline(_source("empty.gc"), max_mutants=1, max_steps=MAX_STEPS)
    assert "no statements" in str(excinfo.value)


def test_5_large_loop_bounded_execution() -> None:
    result = pl.run_pipeline(_source("large_loop.gc"), max_mutants=2, max_steps=MAX_STEPS)
    original = interpreter.run(result.tac, MAX_STEPS)
    assert original.trap is None
    assert "s=49995000" in original.output  # sum of 0..9999
    assert "i=10000" in original.output


def test_6_liveness_fixpoint_satisfies_dataflow_equations() -> None:
    program = frontend.parse_source(_source("branchy2.gc"))
    declared = semantic.analyze(program)
    assert declared == ("a", "b", "x")
    tac = tacmod.generate(program)
    graph = cfgmod.build_cfg(tac)
    live_in, live_out, _it = dataflow.liveness(graph)
    for b in graph.blocks:
        expected: set[str] = set()
        if graph.successors[b.index]:
            expected = set().union(*(set(live_in[s]) for s in sorted(graph.successors[b.index])))
        assert set(live_out[b.index]) == expected
    all_out: set[str] = set()
    for b in graph.blocks:
        all_out |= set(live_out[b.index])
    assert {"a", "b"} <= all_out  # x is always redefined before use: never live-out


def test_7_two_runs_are_byte_identical() -> None:
    src = _source("valid1.gc")
    r1 = pl.run_pipeline(src, max_mutants=6, max_steps=MAX_STEPS)
    r2 = pl.run_pipeline(src, max_mutants=6, max_steps=MAX_STEPS)
    assert tacmod.format_tac(r1.tac) == tacmod.format_tac(r2.tac)
    sig1 = [(p.mutant.ident, p.evidence, p.mutant_output) for p in r1.puzzles]
    sig2 = [(p.mutant.ident, p.evidence, p.mutant_output) for p in r2.puzzles]
    assert sig1 == sig2


def test_8_copy_propagation_mutant_diverges() -> None:
    result = pl.run_pipeline(_source("branchy2.gc"), max_mutants=8, max_steps=MAX_STEPS)
    ops = {p.mutant.operator for p in result.puzzles}
    assert mutate.OP_COPY_PROP in ops
    original = interpreter.run(result.tac, MAX_STEPS)
    assert original.output == ("x=2",)

# ---------------------------------------------------------------- extended suite
from src import explain as explainmod  # noqa: E402
from src import report as reportmod  # noqa: E402


def _run(name: str, cap: int = 20) -> pl.PipelineResult:
    return pl.run_pipeline(_source(name), max_mutants=cap, max_steps=MAX_STEPS)


def test_9_cfg_has_loop_back_edge_and_branch_diamond() -> None:
    result = _run("collatz.gc")
    cfg = result.cfg
    back = [(b, s) for b, succ in cfg.successors.items() for s in succ if s <= b]
    assert back, "while-loop must produce a back edge (goto target resolved)"
    assert explainmod.blocks_in_loops(cfg), "loop blocks must be detected"
    # both arms of the if/else must rejoin at one block
    joins = [b for b, preds in cfg.preds.items() if len(preds) >= 2 and b not in {s for _, s in back}]
    assert joins


def test_10_liveness_flows_around_the_back_edge() -> None:
    result = _run("collatz.gc")
    header = result.cfg.block_of[next(i.index for i in result.tac if i.op == tacmod.Op.LABEL)]
    assert {"n", "steps"} <= set(result.live_in[header])


def test_11_off_by_one_branch_mutant_is_proven() -> None:
    result = _run("countdown.gc")
    assert any(p.mutant.operator == mutate.OP_OFF_BY_ONE for p in result.puzzles)


def test_12_noncommutative_swap_mutant_is_proven() -> None:
    result = _run("gcd.gc")
    swaps = [p for p in result.puzzles if p.mutant.operator == mutate.OP_COMMUTE]
    assert swaps
    assert swaps[0].original_output == ("a=21",)


def test_13_every_puzzle_is_explained() -> None:
    for name in ("valid1.gc", "branchy2.gc", "collatz.gc", "digits.gc"):
        for p in _run(name).puzzles:
            e = p.explanation
            assert e.diff.startswith("--- original.tac")
            assert e.changed, "a mutant must alter at least one instruction"
            assert e.difficulty in {"Easy", "Medium", "Hard"}
            assert len(e.hints) == 3 and all(e.hints)
            assert 1 <= e.score <= 5


def test_14_tac_text_has_no_placeholder_noise() -> None:
    text = tacmod.format_tac(_run("collatz.gc").tac)
    assert "None" not in text
    assert "n = t1" in text


def test_15_html_report_is_self_contained_and_escaped() -> None:
    result = _run("collatz.gc")
    html = reportmod.render_html(result, "<script>alert(1)</script>")
    assert "<svg" in html and "Locate in CFG" in html
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "http://" not in html.replace("http://www.w3.org", "") and "https://" not in html
    for p in result.puzzles:
        assert f"puz-{p.mutant.ident}" in html


def test_16_dot_export_lists_every_edge() -> None:
    result = _run("collatz.gc")
    dot = reportmod.render_dot(result)
    assert dot.startswith("digraph CFG")
    edges = sum(len(s) for s in result.cfg.successors.values())
    assert dot.count("->") == edges


def test_17_stage_timings_cover_the_whole_pipeline() -> None:
    result = _run("valid1.gc")
    assert tuple(name for name, _t in result.timings) == pl.STAGES
    assert all(t >= 0 for _n, t in result.timings)


# ---------------------------------------------------------------- strings & arrays
from src import ast_nodes as astn  # noqa: E402


def _out(name: str) -> tuple[str, ...]:
    result = _run(name)
    run = interpreter.run(result.tac, MAX_STEPS)
    assert run.trap is None
    return run.output


def test_18_frontend_builds_string_and_array_nodes() -> None:
    prog = frontend.parse_source('int a[3] = {1, 2}; string s = "a\\"b\\n"; a[2] = len(s) + a[0];')
    decl, sdecl, store = prog.body
    assert isinstance(decl, astn.ArrayDecl) and decl.size == 3 and len(decl.init) == 2
    assert isinstance(sdecl, astn.Decl) and sdecl.ty == astn.T_STRING
    assert isinstance(sdecl.init, astn.StrLit) and sdecl.init.value == 'a"b\n'
    assert isinstance(store, astn.Store)


def test_19_type_checker_tracks_three_types() -> None:
    prog = frontend.parse_source('int x = 1; string s = "hi"; int a[2];')
    assert semantic.check(prog) == {"x": "int", "s": "string", "a": "int[]"}


@pytest.mark.parametrize("src, needle", [
    ('int x = "no";', "expected int, got string"),
    ('string s = "a"; int x = 1; string t = s + x;', "cannot combine string and int"),
    ("int a[2]; int b[2]; a = b;", "as a whole"),
    ('string s = "abc"; s[0] = 1;', "immutable"),
    ('int a[2]; string i = "0"; int v = a[i];', "must be an int"),
    ("int x = 4; int y = x[0];", "cannot be indexed"),
    ("int a[2] = {1, 2, 3};", "too many initializers"),
    ('int x = 1; string s = "1"; if (x == s) { x = 2; }', "cannot compare"),
])
def test_20_type_errors_are_reported(src: str, needle: str) -> None:
    with pytest.raises(semantic.SemanticError) as excinfo:
        pl.run_pipeline(src, max_mutants=1, max_steps=MAX_STEPS)
    assert needle in str(excinfo.value)


def test_21_type_error_sample_file() -> None:
    with pytest.raises(semantic.SemanticError) as excinfo:
        pl.run_pipeline(_source("type_err.gc"), max_mutants=1, max_steps=MAX_STEPS)
    assert "line 3" in str(excinfo.value)


def test_22_array_programs_compute_correctly() -> None:
    assert _out("arrays.gc") == ("first=4", "a=[42,23,16,15,8,4]", "best=42")
    assert _out("bubble.gc") == ("a=[1,3,8,11,17,29,42]", "swaps=12")


def test_23_string_programs_compute_correctly() -> None:
    assert _out("strings.gc") == ('rev="nilmerg"', "pal=0", 'tag="hello, gremlin!"')


def test_24_tac_uses_array_and_string_opcodes() -> None:
    text = tacmod.format_tac(_run("strings.gc").tac) + tacmod.format_tac(_run("arrays.gc").tac)
    for frag in (" = newarr 6", "a[t", " = len ", ' = "gremlin"', " ++ "):
        assert frag in text, frag


def test_25_out_of_bounds_access_traps_cleanly() -> None:
    tac = tacmod.generate(frontend.parse_source("int a[2]; int i = 5; a[i] = 1; print a;"))
    run = interpreter.run(tac, MAX_STEPS)
    assert run.trap is not None and "out of bounds" in run.trap
    assert run.output == ()


def test_26_store_forwarding_mutant_is_proven_on_arrays() -> None:
    puzzles = [p for p in _run("arrays.gc").puzzles if p.mutant.operator == mutate.OP_ALIAS]
    assert puzzles
    assert puzzles[0].mutant_output[0] == "first=42"  # a[5] forwarded into a[0]


def test_27_concatenation_is_treated_as_non_commutative() -> None:
    swaps = [p for p in _run("strings.gc").puzzles
             if p.mutant.operator == mutate.OP_COMMUTE and "concatenation" in p.mutant.violated]
    assert swaps


def test_28_deleting_an_array_store_is_a_liveness_bug() -> None:
    stores = [p for p in _run("bubble.gc").puzzles
              if p.mutant.operator == mutate.OP_DEAD_STORE and "array" in p.mutant.violated]
    assert stores


def test_29_arrays_are_live_across_the_loop() -> None:
    result = _run("bubble.gc")
    assert any("a" in result.live_in[b] for b in explainmod.blocks_in_loops(result.cfg))


def test_30_mutant_runs_never_corrupt_the_original() -> None:
    result = _run("bubble.gc")
    again = interpreter.run(result.tac, MAX_STEPS)
    assert again.output == result.original_output
