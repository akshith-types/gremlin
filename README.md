# GREMLIN - adversarial puzzle compiler (Compiler Lab)

Compiles a small C-like language (ints, strings, int arrays, if/while) to three-address code, runs liveness and
reaching-definitions analysis, then deliberately emits *unsound* optimized
mutants. Each mutant is validated by differential execution: if its observable
behaviour differs from the original, it is confirmed as a debugging puzzle and
shipped as a bug card with a TAC diff, a difficulty rating and a 3-step hint ladder.

## the GremlinC language
    int x = 7;                      // integers (C-style truncating / and %)
    string s = "hi\n";              // strings: + concatenates, s[i] is a 1-char string
    int a[5] = {3, 1, 4};           // fixed-size int arrays, rest zero-filled
    a[i] = a[i] + len(s);           // indexing, element stores, len() of a string or array
    if (s != "x") { ... } else { ... }
    while (i < len(a)) { ... }
    print a;                        // a=[3,1,4,0,0]   s="hi\n"   x=7

Static type checking (`int`, `string`, `int[]`) rejects mixed arithmetic, whole-array
assignment, writes into strings, non-int indices and comparisons across types.
At run time, out-of-bounds indexing traps cleanly instead of crashing.

New TAC opcodes: `t = "lit"`, `t = a ++ b` (concat), `t = len x`, `a = newarr N`,
`t = a[i]` (load), `a[i] = v` (store - a partial update, so it reads `a` and never kills it
in liveness / reaching definitions).

## mutation operators
| id | operator | property violated |
|----|----------|-------------------|
| M1 | dead-store elimination of a live store | liveness |
| M2 | `(x/c)*c  ->  x` | integer algebra |
| M3 | copy propagation into a use the copy never reaches | reaching definitions |
| M4 | `<` <-> `<=`, `>` <-> `>=` in a branch test | branch boundary |
| M1 | delete a store into an array that is read later | liveness (arrays) |
| M5 | swap operands of `-`, `/`, `%`, string `++` | commutativity |
| M6 | forward `a[i] = v` into a later load `a[j]` | memory dependence (aliasing) |

## quick start
    bash setup.sh            # once: deps + ANTLR codegen (needs Java 11+)
    cp .env.example .env
    python validator.py      # mypy --strict + pytest (37 tests); all checks must pass before the demo
    python driver.py tests/data/collatz.gc
    python driver.py tests/data/strings.gc     # also: arrays.gc, bubble.gc
    open out/report.html     # interactive report: CFG, dataflow tables, playable puzzles

## driver options
    python driver.py FILE [--out DIR] [--max-mutants N] [--no-report]
    python driver.py FILE --bench 20     # per-stage mean/min time + peak heap (Review 3 metrics)
    python driver.py --batch tests/data  # summary table over every .gc file

## artifacts (in --out)
`original.tac`, `mutant_*.tac`, `bugcards.json`, `metrics.json`, `report.html` (self-contained, works offline),
`cfg.dot` (render with `dot -Tpng cfg.dot -o cfg.png`), `batch_summary.json` (batch mode).

## documentation
- `docs/GREMLIN_Review3.pptx` - Review 3 presentation
- `DEMO.md` - live demo run sheet
- `CHANGELOG.md` - development log by phase
- Final report: 11-chapter project report (exported separately as .docx / PDF)

## project info
BCSE307P Compiler Design Laboratory, FALLSEM 2026-27 - individual project by Akshith M (24BAI0017), VIT.
Guide: Ranjithkumar S.
