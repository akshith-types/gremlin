# GREMLIN - demo run sheet (Review 3)

Run from the project folder. Each step: command -> what to point at.

## 0. Health check (30 s)
    python3 validator.py
-> mypy --strict clean, 37 tests pass. "Everything below is type-checked and tested."

## 1. Core idea on the simplest program
    cat tests/data/valid1.gc
    python3 driver.py tests/data/valid1.gc --out demo/01_basic
    cat demo/01_basic/original.tac
    open demo/01_basic/report.html
-> (a/2)*2 != a for odd a: M2 rewrites it, interpreter PROVES c=13 vs c=14.
-> Report: open a puzzle, walk Hint 1 -> 2 -> 3 -> Reveal solution.

## 2. Control flow + CFG fix (loops, branches)
    cat tests/data/collatz.gc
    python3 driver.py tests/data/collatz.gc --out demo/02_loops
    open demo/02_loops/report.html
-> CFG: back edge B5->B1, if/else diamond, true/false edges, dashed loop blocks.
-> Dataflow table: n, steps live around the loop (needed the goto back-edge fix).
-> Click "Locate in CFG" on m1_16 (Medium, in loop): instruction highlights.

## 3. Copy propagation across blocks (reaching definitions)
    python3 driver.py tests/data/branchy2.gc --out demo/02b_copyprop
-> M3_UNSOUND_COPY_PROP: copy propagated into a use it never reaches.

## 4. NEW: strings
    cat tests/data/strings.gc
    python3 driver.py tests/data/strings.gc --out demo/03_strings --max-mutants 8
    cat demo/03_strings/original.tac      # t = "gremlin", t = a ++ b, t = len x, t = word[i]
-> M5 on string ++ : rev="gremlin" instead of "nilmerg" (concat is not commutative).
-> M4 off-by-one: rev="nilmer" (loop stops one char early).

## 5. NEW: arrays
    cat tests/data/arrays.gc
    python3 driver.py tests/data/arrays.gc --out demo/04_arrays --max-mutants 8
    open demo/04_arrays/report.html
-> TAC: a = newarr 6, a[t] = v (store), t = a[t] (load).
-> M6 store forwarding (aliasing): first=42 instead of 4.
-> M4 on the loop bound: index 6 out of bounds -> clean runtime trap, no crash.
-> M1 on an array store: a deleted element store shows up as a 0 in the array.

## 6. NEW: type checker + error handling
    python3 driver.py tests/data/type_err.gc       # string + int  -> semantic error, line 3
    python3 driver.py tests/data/syntax_err.gc     # syntax error with expected tokens
    python3 driver.py tests/data/semantic_err.gc   # undeclared variable
-> Three error layers: lexer/parser, scope, types.

## 7. Performance metrics
    python3 driver.py tests/data/bubble.gc --out demo/05_bench --bench 20
-> Per-stage mean/min ms + peak heap. Parse and execution dominate; dataflow is < 0.3 ms.

## 8. Whole test corpus
    python3 driver.py --batch tests/data --out demo
-> 10 valid programs all produce proven puzzles; 4 bad programs rejected cleanly.
-> demo/batch_summary.json = results table for the report.

## 9. Machine-readable output (if asked)
    cat demo/04_arrays/bugcards.json | head -40
    cat demo/04_arrays/metrics.json
    dot -Tpng demo/02_loops/cfg.dot -o demo/02_loops/cfg.png   # only if Graphviz is installed
