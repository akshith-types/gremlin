"""Self-contained HTML report: source, CFG diagram, dataflow tables and playable puzzles.

No external assets or scripts - the file opens offline and can be attached to a
project submission as-is. All dynamic text goes through html.escape.
"""
from __future__ import annotations

import re
from html import escape

from .explain import blocks_in_loops
from .pipeline import PipelineResult, Puzzle
from .tac import Op, format_tac, writes

# ---- CFG layout constants ------------------------------------------------
_BOX_W = 440
_HEAD_H = 26
_LINE_H = 18
_PAD = 10
_GAP = 46
_LANE = 14
_MARGIN = 20


def _natural(items: frozenset[str]) -> list[str]:
    return sorted(items, key=lambda s: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)])


def _fmt_set(items: list[str]) -> str:
    return "{ " + ", ".join(items) + " }" if items else "&empty;"


def _edge_kinds(result: PipelineResult) -> dict[tuple[int, int], str]:
    """Label the two exits of a conditional block: jump taken => 'false', fall-through => 'true'."""
    cfg = result.cfg
    label_block: dict[str, int] = {}
    for blk in cfg.blocks:
        for ins in blk.instrs:
            if ins.op == Op.LABEL and ins.arg1 is not None:
                label_block[ins.arg1] = blk.index
    kinds: dict[tuple[int, int], str] = {}
    for blk in cfg.blocks:
        last = blk.instrs[-1]
        if last.op == Op.IF_FALSE and last.dest in label_block:
            jump = label_block[last.dest]
            for s in cfg.successors[blk.index]:
                kinds[(blk.index, s)] = "false" if s == jump else "true"
    return kinds


def _cfg_svg(result: PipelineResult) -> str:
    cfg = result.cfg
    loops = blocks_in_loops(cfg)
    kinds = _edge_kinds(result)

    # vertical placement
    tops: dict[int, int] = {}
    heights: dict[int, int] = {}
    y = _MARGIN
    for blk in cfg.blocks:
        h = _HEAD_H + _LINE_H * len(blk.instrs) + _PAD
        tops[blk.index] = y
        heights[blk.index] = h
        y += h + _GAP
    total_h = y - _GAP + _MARGIN

    # lane allocation for non-adjacent edges
    right_edges: list[tuple[int, int]] = []
    left_edges: list[tuple[int, int]] = []
    for blk in cfg.blocks:
        for s in sorted(cfg.successors[blk.index]):
            if s == blk.index + 1:
                continue
            (right_edges if s > blk.index else left_edges).append((blk.index, s))
    left_w = _MARGIN + _LANE * (len(left_edges) + 1) + 24
    right_w = _MARGIN + _LANE * (len(right_edges) + 1) + 24
    x0 = left_w
    x1 = x0 + _BOX_W
    total_w = x1 + right_w
    cx = x0 + _BOX_W // 2

    out: list[str] = [
        f'<svg class="cfg" viewBox="0 0 {total_w} {total_h}" role="img" '
        f'aria-label="Control flow graph with {len(cfg.blocks)} basic blocks">',
        '<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="arrow"/>'
        '</marker></defs>',
    ]

    # edges first so boxes paint over line ends
    for blk in cfg.blocks:
        i = blk.index
        for s in sorted(cfg.successors[i]):
            kind = kinds.get((i, s), "")
            cls = f"edge {kind}".strip()
            if s == i + 1:
                ya, yb = tops[i] + heights[i], tops[s]
                out.append(f'<path class="{cls}" d="M{cx},{ya} L{cx},{yb}" marker-end="url(#arr)"/>')
                if kind:
                    out.append(f'<text class="elabel {kind}" x="{cx + 8}" y="{ya + 16}">{kind}</text>')
            elif s > i:
                lane = right_edges.index((i, s))
                xg = x1 + 22 + _LANE * lane
                ya = tops[i] + heights[i] - 12
                yb = tops[s] + 14
                out.append(f'<path class="{cls}" d="M{x1},{ya} L{xg},{ya} L{xg},{yb} L{x1 + 1},{yb}" '
                           f'marker-end="url(#arr)"/>')
                if kind:
                    out.append(f'<text class="elabel {kind}" x="{x1 + 6}" y="{ya - 4}">{kind}</text>')
            else:
                lane = left_edges.index((i, s))
                xg = x0 - 22 - _LANE * lane
                ya = tops[i] + heights[i] - 12
                yb = tops[s] + 14
                out.append(f'<path class="{cls} back" d="M{x0},{ya} L{xg},{ya} L{xg},{yb} L{x0 - 1},{yb}" '
                           f'marker-end="url(#arr)"/>')
                if kind:
                    out.append(f'<text class="elabel {kind}" x="{x0 - 6}" y="{ya - 4}" '
                               f'text-anchor="end">{kind}</text>')

    for blk in cfg.blocks:
        i = blk.index
        t, h = tops[i], heights[i]
        out.append(f'<g class="blk{" loop" if i in loops else ""}">')
        out.append(f'<rect class="box" x="{x0}" y="{t}" width="{_BOX_W}" height="{h}" rx="8"/>')
        out.append(f'<text class="bhead" x="{x0 + 12}" y="{t + 18}">B{i}</text>')
        if i in loops:
            out.append(f'<text class="btag" x="{x1 - 12}" y="{t + 18}" text-anchor="end">loop</text>')
        for k, ins in enumerate(blk.instrs):
            ty = t + _HEAD_H + _LINE_H * k
            line = escape(format_tac((ins,)).rstrip("\n"))
            out.append(f'<g id="g{ins.index}" class="ins"><rect class="insbg" x="{x0 + 4}" y="{ty}" '
                       f'width="{_BOX_W - 8}" height="{_LINE_H}" rx="3"/>'
                       f'<text x="{x0 + 12}" y="{ty + 13}" xml:space="preserve">{line}</text></g>')
        out.append("</g>")
    out.append("</svg>")
    return "\n".join(out)


def _dataflow_table(result: PipelineResult) -> str:
    cfg = result.cfg
    declared = set(result.declared)
    def_var: dict[int, str] = {}
    for blk in cfg.blocks:
        for ins in blk.instrs:
            w = writes(ins)
            if w is not None:
                def_var[ins.index] = w
    rows: list[str] = []
    for blk in cfg.blocks:
        i = blk.index
        lin = _natural(frozenset(v for v in result.live_in[i] if v in declared))
        lout = _natural(frozenset(v for v in result.live_out[i] if v in declared))
        rd = sorted((d for d in result.rd_in[i] if def_var.get(d) in declared))
        rd_txt = [f"{def_var[d]}@{d}" for d in rd]
        succ = ", ".join(f"B{s}" for s in sorted(cfg.successors[i])) or "exit"
        rows.append(
            f"<tr><th scope='row'>B{i}</th><td>{escape(succ)}</td>"
            f"<td>{_fmt_set([escape(v) for v in lin])}</td>"
            f"<td>{_fmt_set([escape(v) for v in lout])}</td>"
            f"<td>{_fmt_set([escape(v) for v in rd_txt])}</td></tr>"
        )
    return (
        "<div class='scroll'><table class='df'><thead><tr><th>Block</th><th>Successors</th>"
        "<th>Live-in</th><th>Live-out</th><th>Reaching defs (in)</th></tr></thead><tbody>"
        + "".join(rows) + "</tbody></table></div>"
    )


def _out_columns(p: Puzzle) -> str:
    n = max(len(p.original_output), len(p.mutant_output))
    left: list[str] = []
    right: list[str] = []
    for k in range(n):
        a = p.original_output[k] if k < len(p.original_output) else ""
        b = p.mutant_output[k] if k < len(p.mutant_output) else ""
        cls = " class='neq'" if a != b else ""
        left.append(f"<div{cls}>{escape(a) or '&nbsp;'}</div>")
        right.append(f"<div{cls}>{escape(b) or '&nbsp;'}</div>")
    return (
        "<div class='cols'><div><h5>Original prints</h5><pre class='out'>" + "".join(left) + "</pre></div>"
        "<div><h5>Mutant prints</h5><pre class='out'>" + "".join(right) + "</pre></div></div>"
    )


def _diff_html(diff: str) -> str:
    lines: list[str] = []
    for raw in diff.splitlines():
        cls = "ctx"
        if raw.startswith("+++") or raw.startswith("---"):
            cls = "dh"
        elif raw.startswith("@@"):
            cls = "dh"
        elif raw.startswith("+"):
            cls = "add"
        elif raw.startswith("-"):
            cls = "del"
        lines.append(f"<span class='{cls}'>{escape(raw)}</span>")
    return "<pre class='diff'>" + "".join(lines) + "</pre>"


def _puzzle_card(n: int, p: Puzzle) -> str:
    e = p.explanation
    ids = ",".join(str(i) for i in e.changed)
    hint_html = "".join(
        f"<details class='hint'><summary>Hint {k}</summary><p>{escape(h)}</p></details>"
        for k, h in enumerate(e.hints, start=1)
    )
    loop_pill = "<span class='pill loopy'>in loop</span>" if e.in_loop else ""
    return (
        f"<article class='card' id='puz-{escape(p.mutant.ident)}'>"
        f"<header><span class='num'>#{n}</span><h3>{escape(p.mutant.ident)}</h3>"
        f"<span class='pill op'>{escape(p.mutant.operator)}</span>"
        f"<span class='pill d-{e.difficulty.lower()}'>{e.difficulty}</span>"
        f"{loop_pill}"
        f"<button type='button' class='locate' data-ids='{ids}'>Locate in CFG</button></header>"
        f"<p class='ev'>{escape(p.evidence)}</p>"
        f"{_out_columns(p)}"
        f"<h5>TAC diff</h5>{_diff_html(e.diff)}"
        f"<h5>Debugging ladder</h5>{hint_html}"
        f"<details class='hint sol'><summary>Reveal solution</summary>"
        f"<p><b>Property violated:</b> {escape(p.mutant.violated)}</p>"
        f"<p>{escape(p.mutant.description)}</p></details>"
        f"</article>"
    )


def _timing_bars(result: PipelineResult) -> str:
    total = sum(t for _s, t in result.timings) or 1e-9
    peak = max((t for _s, t in result.timings), default=1e-9) or 1e-9
    rows = []
    for name, t in result.timings:
        w = max(1.0, 100.0 * t / peak)
        rows.append(
            f"<div class='bar'><span>{escape(name)}</span>"
            f"<div class='track'><i style='width:{w:.1f}%'></i></div>"
            f"<em>{t * 1000:.3f} ms <small>({100 * t / total:.0f}%)</small></em></div>"
        )
    return "".join(rows)


def _source_listing(src: str) -> str:
    lines = src.splitlines() or [""]
    return "<pre class='src'>" + "\n".join(
        f"<span class='ln'>{i:>3}</span> {escape(line)}" for i, line in enumerate(lines, start=1)
    ) + "</pre>"


def render_html(result: PipelineResult, title: str) -> str:
    total_ms = sum(t for _s, t in result.timings) * 1000
    cards = "".join(_puzzle_card(n, p) for n, p in enumerate(result.puzzles, start=1)) or \
        "<p class='muted'>No confirmed puzzles for this input. Try more arithmetic, branches or loops.</p>"
    stats = [
        ("TAC instructions", str(result.steps_original)),
        ("Basic blocks", str(result.num_blocks)),
        ("Liveness passes", str(result.live_iterations)),
        ("Reaching-def passes", str(result.rd_iterations)),
        ("Mutants tried", str(result.candidates)),
        ("Confirmed bugs", str(len(result.puzzles))),
        ("Pipeline time", f"{total_ms:.2f} ms"),
    ]
    stat_html = "".join(f"<div class='stat'><b>{escape(v)}</b><span>{escape(k)}</span></div>" for k, v in stats)
    skipped = ", ".join(result.discarded) or "none"
    return _TEMPLATE.format(
        title=escape(title),
        stats=stat_html,
        source=_source_listing(result.source),
        expected=escape(" | ".join(result.original_output) or "(no output)"),
        cfg=_cfg_svg(result),
        dataflow=_dataflow_table(result),
        timings=_timing_bars(result),
        puzzles=cards,
        skipped=escape(skipped),
    )


_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GREMLIN report - {title}</title>
<style>
:root{{--bg:#f6f7f9;--panel:#ffffff;--ink:#1b2430;--muted:#5d6b7b;--line:#d9dee5;--accent:#c2410c;
--accent-soft:#ffedd5;--ok:#15803d;--bad:#b91c1c;--bad-soft:#fee2e2;--ok-soft:#dcfce7;--code:#f1f3f6;
--edge:#5d6b7b;--hit:#fde68a;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;--sans:system-ui,-apple-system,"Segoe UI",sans-serif}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#0e131a;--panel:#161d27;--ink:#e6ebf2;--muted:#93a1b3;--line:#2a3544;
--accent:#fb923c;--accent-soft:#3a2412;--ok:#4ade80;--bad:#f87171;--bad-soft:#3b1a1c;--ok-soft:#14301f;--code:#0f1620;--edge:#93a1b3;--hit:#5b4a0f}}}}
:root[data-theme="dark"]{{--bg:#0e131a;--panel:#161d27;--ink:#e6ebf2;--muted:#93a1b3;--line:#2a3544;
--accent:#fb923c;--accent-soft:#3a2412;--ok:#4ade80;--bad:#f87171;--bad-soft:#3b1a1c;--ok-soft:#14301f;--code:#0f1620;--edge:#93a1b3;--hit:#5b4a0f}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 var(--sans)}}
main{{max-width:1080px;margin:0 auto;padding:28px 16px 64px}}
h1{{font-size:28px;margin:0 0 4px;letter-spacing:-.01em}}
h1 span{{color:var(--accent)}}
h2{{font-size:18px;margin:36px 0 12px;padding-bottom:6px;border-bottom:1px solid var(--line)}}
h3{{margin:0;font-size:16px;font-family:var(--mono)}}
h5{{margin:14px 0 6px;font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}}
.sub{{color:var(--muted);margin:0 0 20px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px}}
.stat{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 12px}}
.stat b{{display:block;font-size:20px;font-variant-numeric:tabular-nums}}
.stat span{{color:var(--muted);font-size:12px}}
pre{{margin:0;font:13px/1.5 var(--mono);background:var(--code);border:1px solid var(--line);border-radius:8px;padding:10px 12px;overflow:auto}}
.ln{{color:var(--muted);user-select:none}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
@media (max-width:760px){{.two{{grid-template-columns:1fr}}}}
.panel{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}}
.scroll{{overflow-x:auto}}
.cfgwrap{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px;overflow:auto}}
svg.cfg{{width:100%;min-width:520px;height:auto;display:block}}
svg .box{{fill:var(--code);stroke:var(--line);stroke-width:1.2}}
svg .loop .box{{stroke:var(--accent);stroke-dasharray:5 3}}
svg .bhead{{font:700 13px var(--mono);fill:var(--ink)}}
svg .btag{{font:600 10px var(--sans);fill:var(--accent);text-transform:uppercase;letter-spacing:.08em}}
svg .ins text{{font:12px var(--mono);fill:var(--ink);white-space:pre}}
svg .insbg{{fill:transparent}}
svg .ins.hit .insbg{{fill:var(--hit)}}
svg .edge{{fill:none;stroke:var(--edge);stroke-width:1.4}}
svg .edge.true{{stroke:var(--ok)}} svg .edge.false{{stroke:var(--bad)}}
svg .arrow{{fill:var(--edge)}}
svg .elabel{{font:600 10px var(--sans);fill:var(--muted)}}
svg .elabel.true{{fill:var(--ok)}} svg .elabel.false{{fill:var(--bad)}}
table.df{{width:100%;border-collapse:collapse;font:13px var(--mono);background:var(--panel);border:1px solid var(--line);border-radius:10px}}
table.df th,table.df td{{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
table.df thead th{{font:600 11px var(--sans);text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}}
.bar{{display:grid;grid-template-columns:110px 1fr 120px;gap:10px;align-items:center;margin:5px 0;font-size:13px}}
.bar span{{font-family:var(--mono)}}
.track{{background:var(--code);border-radius:99px;height:8px;overflow:hidden}}
.track i{{display:block;height:100%;background:var(--accent);border-radius:99px}}
.bar em{{font-style:normal;color:var(--muted);text-align:right;font-variant-numeric:tabular-nums}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:16px 0}}
.card header{{display:flex;flex-wrap:wrap;gap:8px;align-items:center}}
.num{{color:var(--muted);font-family:var(--mono)}}
.pill{{font:600 11px var(--sans);padding:2px 9px;border-radius:99px;border:1px solid var(--line);color:var(--muted)}}
.pill.op{{color:var(--accent);background:var(--accent-soft);border-color:transparent;font-family:var(--mono)}}
.pill.d-easy{{color:var(--ok);background:var(--ok-soft);border-color:transparent}}
.pill.d-medium{{color:#a16207;background:#fef3c7;border-color:transparent}}
.pill.d-hard{{color:var(--bad);background:var(--bad-soft);border-color:transparent}}
.locate{{margin-left:auto;font:600 12px var(--sans);padding:5px 12px;border-radius:8px;border:1px solid var(--accent);
background:transparent;color:var(--accent);cursor:pointer}}
.locate:hover,.locate:focus-visible{{background:var(--accent);color:var(--bg)}}
.ev{{margin:10px 0 0;color:var(--muted)}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
@media (max-width:640px){{.cols{{grid-template-columns:1fr}}}}
pre.out div.neq{{background:var(--bad-soft);color:var(--bad);margin:0 -12px;padding:0 12px}}
pre.diff .add{{display:block;background:var(--ok-soft);color:var(--ok)}}
pre.diff .del{{display:block;background:var(--bad-soft);color:var(--bad)}}
pre.diff .dh,pre.diff .ctx{{display:block;color:var(--muted)}}
pre.diff .ctx{{color:var(--ink)}}
details.hint{{border:1px solid var(--line);border-radius:8px;padding:6px 12px;margin:6px 0;background:var(--code)}}
details.hint summary{{cursor:pointer;font-weight:600}}
details.hint p{{margin:8px 0 4px}}
details.sol{{border-color:var(--accent)}}
.muted{{color:var(--muted)}}
footer{{margin-top:40px;color:var(--muted);font-size:13px}}
</style>
</head>
<body>
<main>
<h1><span>GREMLIN</span> debugging report</h1>
<p class="sub">{title} &middot; every bug below was injected by an unsound optimisation and <em>proved</em> by differential execution.</p>

<section class="stats" aria-label="Summary">{stats}</section>

<h2>Program</h2>
<div class="two">
  <div><h5>Source</h5>{source}</div>
  <div class="panel"><h5>Expected output (original program)</h5><p style="font-family:var(--mono);margin:6px 0">{expected}</p>
  <h5>Mutants rejected (behaved identically)</h5><p class="muted" style="margin:6px 0;font-family:var(--mono)">{skipped}</p></div>
</div>

<h2>Control-flow graph</h2>
<p class="muted">Green edges: condition true (fall through). Red edges: condition false (jump). Dashed border: block sits inside a loop.
Use <b>Locate in CFG</b> on a puzzle to highlight its broken instruction.</p>
<div class="cfgwrap" id="cfgwrap">{cfg}</div>

<h2>Dataflow facts</h2>
{dataflow}
<p class="muted">Only user variables are shown; compiler temporaries are block-local and omitted. <code>x@4</code> = the definition of x at instruction 4.</p>

<h2>Puzzles</h2>
{puzzles}

<h2>Pipeline timing</h2>
<div class="panel">{timings}</div>

<footer>Generated by GREMLIN. Deterministic: the same source always yields the same puzzles.</footer>
</main>
<script>
(function(){{
  var hit=[];
  function clear(){{hit.forEach(function(n){{n.classList.remove('hit');}});hit=[];}}
  document.querySelectorAll('button.locate').forEach(function(btn){{
    btn.addEventListener('click',function(){{
      clear();
      var ids=(btn.getAttribute('data-ids')||'').split(',').filter(Boolean);
      ids.forEach(function(i){{var n=document.getElementById('g'+i);if(n){{n.classList.add('hit');hit.push(n);}}}});
      if(hit.length){{hit[0].scrollIntoView({{block:'center',behavior:'smooth'}});}}
    }});
  }});
}})();
</script>
</body>
</html>
"""


def render_dot(result: PipelineResult) -> str:
    """Graphviz source for the CFG (render with: dot -Tpng cfg.dot -o cfg.png)."""
    kinds = _edge_kinds(result)
    lines = ["digraph CFG {", '  node [shape=box, fontname="Menlo", fontsize=10];']
    for blk in result.cfg.blocks:
        body = "\\l".join(format_tac((ins,)).rstrip("\n").replace('"', '\\"') for ins in blk.instrs)
        lines.append(f'  B{blk.index} [label="B{blk.index}\\l{body}\\l"];')
    for blk in result.cfg.blocks:
        for s in sorted(result.cfg.successors[blk.index]):
            kind = kinds.get((blk.index, s), "")
            attr = f' [label="{kind}"]' if kind else ""
            lines.append(f"  B{blk.index} -> B{s}{attr};")
    lines.append("}")
    return "\n".join(lines) + "\n"
