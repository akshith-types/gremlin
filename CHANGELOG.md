# GREMLIN development log

## Phase 3 - Final implementation and testing (Review 3)
- Language: `string` type (literals with escapes, `+` concatenation, `len()`, `s[i]`) and fixed-size `int` arrays (initialiser lists, element loads and stores, `len()`, whole-array print).
- Static type checker for `int`, `string`, `int[]`; 8 classes of type error reported with line numbers.
- TAC: new opcodes `len`, `newarr`, load, store; string constants and `++` concatenation (13 opcodes).
- Interpreter: bounds checks and type-confusion traps.
- Mutation rules M4 (off-by-one branch), M5 (unsound commutativity, incl. strings), M6 (unsound store-to-load forwarding); M1 extended to array stores.
- Explanation layer: TAC diff, difficulty 1-5, three-step hint ladder.
- Interactive `report.html` (CFG diagram, dataflow table, puzzle cards), `cfg.dot`, `metrics.json`.
- `--bench` (per-stage time + peak memory) and `--batch` (summary over a folder).
- Bug fix: CFG builder read `goto` targets from the wrong field, so loops had no back edge and liveness was wrong inside loops. Now covered by tests.
- `format_tac` no longer prints `= None` on copy instructions.
- Tests: 8 -> 37; `validator.py` now runs `mypy --strict`.

## Phase 2 - Core implementation (Review 2)
- Full pipeline: ANTLR4 front end, AST, semantic checks, TAC, CFG, liveness, reaching definitions.
- Mutation rules M1 (dead store), M2 (unsound algebra), M3 (unsound copy propagation).
- Differential execution and `bugcards.json`; 8 integration tests.

## Phase 1 - Problem definition and design (Review 1)
- Problem statement, GremlinC language specification, architecture and prototype.
