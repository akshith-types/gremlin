from __future__ import annotations

from dataclasses import dataclass

from .cfg import CFG
from .tac import CONCAT, STR_CONST, Instr, Op, is_const, reads, writes

OP_ALGEBRA = "M2_UNSOUND_ALGEBRA"
OP_COPY_PROP = "M3_UNSOUND_COPY_PROP"
OP_DEAD_STORE = "M1_DEAD_STORE"
OP_OFF_BY_ONE = "M4_OFF_BY_ONE_BRANCH"
OP_COMMUTE = "M5_UNSOUND_COMMUTATIVITY"
OP_ALIAS = "M6_UNSOUND_STORE_FORWARDING"

# Boundary-shifting relational rewrites: 'a < b' and 'a <= b' differ exactly when a == b.
_RELOP_SHIFT: dict[str, str] = {"<": "<=", "<=": "<", ">": ">=", ">=": ">"}
# Operators for which swapping operands is NOT an identity.
_NON_COMMUTATIVE: frozenset[str] = frozenset({"-", "/", "%", CONCAT})


@dataclass(frozen=True)
class Mutant:
    ident: str
    operator: str
    violated: str
    description: str
    instrs: tuple[Instr, ...]
    location: str


def _replace_at(tac: tuple[Instr, ...], index: int, new: Instr) -> tuple[Instr, ...]:
    return tuple(new if ins.index == index else ins for ins in tac)


def _origin_index(producer: dict[str, int], by_index: dict[int, Instr], name: str) -> int | None:
    """Follow a copy chain back to the instruction that produced `name`'s value."""
    cur = name
    for _ in range(64):
        idx = producer.get(cur)
        if idx is None:
            return None
        ins = by_index[idx]
        if ins.op == Op.COPY and ins.arg1 is not None and not is_const(ins.arg1):
            cur = ins.arg1
            continue
        return idx
    return None


def _get_const_int(producer: dict[str, int], by_index: dict[int, Instr], arg: str | None) -> int | None:
    """Resolve an argument (literal or temporary constant) to an integer value if possible."""
    if arg is None:
        return None
    if is_const(arg):
        return int(arg)
    idx = producer.get(arg)
    if idx is not None:
        ins = by_index[idx]
        if ins.op == Op.CONST and ins.extra != STR_CONST and ins.arg1 is not None \
                and is_const(ins.arg1):
            return int(ins.arg1)
        if ins.op == Op.COPY and ins.arg1 is not None:
            return _get_const_int(producer, by_index, ins.arg1)
    return None


def _rd_at_instruction(rd_in: dict[int, frozenset[int]], block_instrs: tuple[Instr, ...],
                       def_var: dict[int, str], upto_index: int,
                       block_index: int) -> set[int]:
    """Reaching definition indices at the point just before `upto_index`,
    accounting for kills/defs earlier inside the same block."""
    reaching: set[int] = set(rd_in.get(block_index, frozenset()))
    for ins in block_instrs:
        if ins.index == upto_index:
            return reaching
        w = writes(ins)
        if w is not None:
            reaching = {r for r in reaching if def_var.get(r) != w}
            reaching.add(ins.index)
    return reaching


def find_mutants(tac: tuple[Instr, ...], cfg: CFG,
                 live_out: dict[int, frozenset[str]],
                 rd_in: dict[int, frozenset[int]],
                 declared: tuple[str, ...],
                 max_mutants: int) -> tuple[Mutant, ...]:
    declared_set = set(declared)
    by_index = {ins.index: ins for ins in tac}
    def_var: dict[int, str] = {}
    for ins in tac:
        w = writes(ins)
        if w is not None:
            def_var[ins.index] = w

    m1: list[Mutant] = []
    m2: list[Mutant] = []
    m3: list[Mutant] = []

    # ---- M2: unsound algebraic identity (x / c) * c  ==>  x  (wrong when x % c != 0)
    for blk in cfg.blocks:
        producer: dict[str, int] = {}
        divs: list[tuple[int, str, str, int]] = []  # (idx, dest, arg1, c_val)
        for ins in blk.instrs:
            if ins.op == Op.BINOP and ins.dest is not None \
                    and ins.arg1 is not None and ins.arg2 is not None:
                c2 = _get_const_int(producer, by_index, ins.arg2)
                if ins.extra == "/" and c2 is not None and c2 != 0:
                    c1 = _get_const_int(producer, by_index, ins.arg1)
                    trivially_equal = (c1 is not None and c1 % c2 == 0)
                    if not trivially_equal:
                        divs.append((ins.index, ins.dest, ins.arg1, c2))
                elif ins.extra == "*":
                    org1 = _origin_index(producer, by_index, ins.arg1)
                    org2 = _origin_index(producer, by_index, ins.arg2)
                    for di, _ddest, darg1, c_div in divs:
                        c_mul = c2 if org1 == di else _get_const_int(producer, by_index, ins.arg1)
                        if (org1 == di or org2 == di) and (c_mul is None or c_mul == c_div):
                            new = Instr(index=ins.index, op=Op.COPY, dest=ins.dest, arg1=darg1, arg2=None)
                            m2.append(Mutant(
                                ident=f"m2_{ins.index}",
                                operator=OP_ALGEBRA,
                                violated="algebraic identity: (x/c)*c == x is FALSE when x % c != 0",
                                description=(
                                    f"replaced '({darg1}/{c_div})*{c_div}' with the unsound "
                                    f"identity '{ins.dest} = {darg1}' at instruction {ins.index}"
                                ),
                                instrs=_replace_at(tac, ins.index, new),
                                location=f"instruction {ins.index}",
                            ))
                            break
            w = writes(ins)
            if w is not None:
                producer[w] = ins.index

    # ---- M3: copy propagation where the copy does NOT reach the use
    for ins in tac:
        if ins.op != Op.COPY or ins.dest is None or ins.arg1 is None:
            continue
        a, src = ins.dest, ins.arg1
        if a not in declared_set or src not in declared_set or is_const(src):
            continue
        found = False
        for blk in cfg.blocks:
            if found:
                break
            if blk.index == cfg.block_of[ins.index]:
                continue
            for use_ins in blk.instrs:
                if a not in reads(use_ins):
                    continue
                rd_set = _rd_at_instruction(rd_in, blk.instrs, def_var,
                                            use_ins.index, blk.index)
                relevant = {r for r in rd_set if def_var.get(r) == a}
                if ins.index in relevant or not relevant:
                    continue
                n1 = src if use_ins.arg1 == a else use_ins.arg1
                n2 = src if use_ins.arg2 == a else use_ins.arg2
                new = Instr(index=use_ins.index, op=use_ins.op, dest=use_ins.dest,
                            arg1=n1, arg2=n2, extra=use_ins.extra)
                m3.append(Mutant(
                    ident=f"m3_{ins.index}_{use_ins.index}",
                    operator=OP_COPY_PROP,
                    violated="reaching definitions: value propagated from a copy that never reaches the use",
                    description=(
                        f"propagated copy '{a} = {src}' into instruction {use_ins.index}, "
                        f"where '{a}' is defined by another statement"
                    ),
                    instrs=_replace_at(tac, use_ins.index, new),
                    location=f"copy at {ins.index}, use at {use_ins.index}",
                ))
                found = True
                break

    # ---- M1: dead-store elimination of a DEFINITELY-LIVE store (liveness violation)
    for ins in tac:
        w = writes(ins)
        if w is None or w not in declared_set:
            continue
        blk_id = cfg.block_of[ins.index]
        if w not in live_out.get(blk_id, frozenset()):
            continue
        m1.append(Mutant(
            ident=f"m1_{ins.index}",
            operator=OP_DEAD_STORE,
            violated="liveness: a definitely-live definition was deleted",
            description=f"deleted the definition of live variable '{w}' at instruction {ins.index}",
            instrs=tuple(i for i in tac if i.index != ins.index),
            location=f"instruction {ins.index}",
        ))

    # ---- M1 (arrays): delete a store into an array that is read afterwards
    for blk in cfg.blocks:
        for pos, ins in enumerate(blk.instrs):
            if ins.op != Op.STORE or ins.dest is None:
                continue
            arr = ins.dest
            read_later = any(arr in reads(nxt) for nxt in blk.instrs[pos + 1:])
            if not read_later and arr not in live_out.get(blk.index, frozenset()):
                continue
            m1.append(Mutant(
                ident=f"m1_{ins.index}",
                operator=OP_DEAD_STORE,
                violated="liveness: a store into an array that is read later was deleted",
                description=(f"deleted the store '{arr}[{ins.arg1}] = {ins.arg2}' "
                             f"at instruction {ins.index}"),
                instrs=tuple(i for i in tac if i.index != ins.index),
                location=f"instruction {ins.index}",
            ))
    m1.sort(key=lambda m: int(m.ident.split("_")[1]))

    # ---- M6: store-to-load forwarding that assumes two different indices alias
    m6: list[Mutant] = []
    for blk in cfg.blocks:
        last_store: dict[str, Instr] = {}
        for ins in blk.instrs:
            if ins.op == Op.STORE and ins.dest is not None:
                last_store[ins.dest] = ins
                continue
            if ins.op != Op.LOAD or ins.arg1 not in last_store or ins.dest is None:
                continue
            st = last_store[ins.arg1]
            if st.arg1 == ins.arg2 or st.arg2 is None:
                continue
            new = Instr(index=ins.index, op=Op.COPY, dest=ins.dest, arg1=st.arg2, arg2=None)
            m6.append(Mutant(
                ident=f"m6_{ins.index}",
                operator=OP_ALIAS,
                violated=(f"memory dependence: '{ins.arg1}[{st.arg1}]' and '{ins.arg1}[{ins.arg2}]' "
                          f"are the same cell only when the indices are equal"),
                description=(f"forwarded the value stored by '{ins.arg1}[{st.arg1}] = {st.arg2}' "
                             f"(instruction {st.index}) into the load '{ins.dest} = "
                             f"{ins.arg1}[{ins.arg2}]' at instruction {ins.index}"),
                instrs=_replace_at(tac, ins.index, new),
                location=f"store at {st.index}, load at {ins.index}",
            ))

    # ---- M4: off-by-one branch boundary ('<' <-> '<=', '>' <-> '>=')
    m4: list[Mutant] = []
    for ins in tac:
        if ins.op != Op.IF_FALSE or ins.extra not in _RELOP_SHIFT:
            continue
        shifted = _RELOP_SHIFT[ins.extra]
        new = Instr(index=ins.index, op=ins.op, dest=ins.dest,
                    arg1=ins.arg1, arg2=ins.arg2, extra=shifted)
        m4.append(Mutant(
            ident=f"m4_{ins.index}",
            operator=OP_OFF_BY_ONE,
            violated=f"branch boundary: '{ins.extra}' and '{shifted}' disagree when the operands are equal",
            description=(f"changed the branch test '{ins.arg1} {ins.extra} {ins.arg2}' "
                         f"to '{ins.arg1} {shifted} {ins.arg2}' at instruction {ins.index}"),
            instrs=_replace_at(tac, ins.index, new),
            location=f"instruction {ins.index}",
        ))

    # ---- M5: unsound commutativity ('a - b' ==> 'b - a', also '/' and '%')
    m5: list[Mutant] = []
    for ins in tac:
        if ins.op != Op.BINOP or ins.extra not in _NON_COMMUTATIVE \
                or ins.dest is None or ins.arg1 is None or ins.arg2 is None:
            continue
        if ins.arg1 == ins.arg2:
            continue
        new = Instr(index=ins.index, op=ins.op, dest=ins.dest,
                    arg1=ins.arg2, arg2=ins.arg1, extra=ins.extra)
        what = "string concatenation" if ins.extra == CONCAT else f"'{ins.extra}'"
        m5.append(Mutant(
            ident=f"m5_{ins.index}",
            operator=OP_COMMUTE,
            violated=f"commutativity: {what} is not commutative ('a {ins.extra} b' != 'b {ins.extra} a')",
            description=(f"swapped the operands of '{ins.extra}' at instruction {ins.index}: "
                         f"'{ins.arg1} {ins.extra} {ins.arg2}' became '{ins.arg2} {ins.extra} {ins.arg1}'"),
            instrs=_replace_at(tac, ins.index, new),
            location=f"instruction {ins.index}",
        ))

    # Round-robin interleave so each operator is represented before any repeat.
    groups = [m2, m3, m1, m4, m5, m6]
    chosen: list[Mutant] = []
    limit = max(0, max_mutants)
    while len(chosen) < limit and any(groups):
        for g in groups:
            if g and len(chosen) < limit:
                chosen.append(g.pop(0))
    return tuple(chosen)