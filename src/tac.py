from __future__ import annotations

import json
from dataclasses import dataclass

from .ast_nodes import (T_INT, T_INT_ARRAY, T_STRING, ArrayDecl, Assign, BinOp, Cond, Decl, Expr,
                        If, Index, IntLit, Len, Print, Program, Stmt, Store, StrLit, UnaryNeg, Var,
                        While)


class Op:
    CONST = "const"        # dest = literal            (extra == "str" for a string literal)
    COPY = "copy"          # dest = arg1
    BINOP = "binop"        # dest = arg1 <extra> arg2  ('++' is string concatenation)
    NEG = "neg"            # dest = -arg1
    LEN = "len"            # dest = len arg1
    NEWARR = "newarr"      # dest = newarr arg1        (zero-filled int array)
    LOAD = "load"          # dest = arg1[arg2]
    STORE = "store"        # dest[arg1] = arg2         (partial update: NOT a kill of dest)
    IF_FALSE = "if_false"
    GOTO = "goto"
    LABEL = "label"
    PRINT = "print"
    HALT = "halt"


STR_CONST = "str"
CONCAT = "++"

_DEFINING: frozenset[str] = frozenset({Op.CONST, Op.COPY, Op.BINOP, Op.NEG, Op.LEN,
                                       Op.NEWARR, Op.LOAD})


@dataclass(frozen=True)
class Instr:
    index: int
    op: str
    dest: str | None
    arg1: str | None
    arg2: str | None
    extra: str = ""


def is_const(name: str) -> bool:
    return name.lstrip("-").isdigit()


def reads(ins: Instr) -> tuple[str, ...]:
    if ins.op in (Op.BINOP, Op.IF_FALSE, Op.LOAD):
        raw: tuple[str | None, ...] = (ins.arg1, ins.arg2)
    elif ins.op in (Op.NEG, Op.PRINT, Op.COPY, Op.LEN):
        raw = (ins.arg1,)
    elif ins.op == Op.STORE:
        raw = (ins.dest, ins.arg1, ins.arg2)  # the array itself is read (and partially updated)
    else:
        raw = ()
    return tuple(a for a in raw if a is not None and not is_const(a))


def writes(ins: Instr) -> str | None:
    if ins.op in _DEFINING:
        return ins.dest
    return None


class _Generator:
    def __init__(self, types: dict[str, str]) -> None:
        self._instrs: list[Instr] = []
        self._temps = 0
        self._labels = 0
        self._types = types

    def _emit(self, op: str, dest: str | None = None, arg1: str | None = None,
              arg2: str | None = None, extra: str = "") -> None:
        self._instrs.append(Instr(index=len(self._instrs), op=op, dest=dest,
                                  arg1=arg1, arg2=arg2, extra=extra))

    def _temp(self) -> str:
        self._temps += 1
        return f"t{self._temps}"

    def _label(self) -> str:
        self._labels += 1
        return f"L{self._labels}"

    def type_of(self, e: Expr) -> str:
        """Expression type; the semantic pass has already proved the program well-typed."""
        if isinstance(e, StrLit):
            return T_STRING
        if isinstance(e, Var):
            return self._types.get(e.name, T_INT)
        if isinstance(e, Index):
            return T_STRING if self._types.get(e.name) == T_STRING else T_INT
        if isinstance(e, BinOp) and e.op == "+":
            return self.type_of(e.left)
        return T_INT

    def gen_expr(self, e: Expr) -> str:
        if isinstance(e, IntLit):
            t = self._temp()
            self._emit(Op.CONST, dest=t, arg1=str(e.value))
            return t
        if isinstance(e, StrLit):
            t = self._temp()
            self._emit(Op.CONST, dest=t, arg1=e.value, extra=STR_CONST)
            return t
        if isinstance(e, Var):
            t = self._temp()
            self._emit(Op.COPY, dest=t, arg1=e.name)
            return t
        if isinstance(e, Index):
            i = self.gen_expr(e.index)
            t = self._temp()
            self._emit(Op.LOAD, dest=t, arg1=e.name, arg2=i)
            return t
        if isinstance(e, Len):
            a = self.gen_expr(e.operand)
            t = self._temp()
            self._emit(Op.LEN, dest=t, arg1=a)
            return t
        if isinstance(e, BinOp):
            op = CONCAT if (e.op == "+" and self.type_of(e) == T_STRING) else e.op
            a = self.gen_expr(e.left)
            b = self.gen_expr(e.right)
            t = self._temp()
            self._emit(Op.BINOP, dest=t, arg1=a, arg2=b, extra=op)
            return t
        if isinstance(e, UnaryNeg):
            a = self.gen_expr(e.operand)
            t = self._temp()
            self._emit(Op.NEG, dest=t, arg1=a)
            return t
        raise TypeError(f"unknown expression node: {type(e).__name__}")

    def gen_cond(self, c_cond: Cond, false_target: str) -> None:
        left = self.gen_expr(c_cond.left)
        right = self.gen_expr(c_cond.right)
        self._emit(Op.IF_FALSE, dest=false_target, arg1=left, arg2=right, extra=c_cond.op)

    def gen_stmt(self, s: Stmt) -> None:
        if isinstance(s, Decl):
            if s.init is not None:
                v = self.gen_expr(s.init)
                self._emit(Op.COPY, dest=s.name, arg1=v)
        elif isinstance(s, ArrayDecl):
            self._emit(Op.NEWARR, dest=s.name, arg1=str(s.size))
            for k, e in enumerate(s.init):
                i = self._temp()
                self._emit(Op.CONST, dest=i, arg1=str(k))
                v = self.gen_expr(e)
                self._emit(Op.STORE, dest=s.name, arg1=i, arg2=v)
        elif isinstance(s, Assign):
            if isinstance(s.value, Var):
                self._emit(Op.COPY, dest=s.name, arg1=s.value.name)
            else:
                v = self.gen_expr(s.value)
                self._emit(Op.COPY, dest=s.name, arg1=v)
        elif isinstance(s, Store):
            i = self.gen_expr(s.index)
            v = self.gen_expr(s.value)
            self._emit(Op.STORE, dest=s.name, arg1=i, arg2=v)
        elif isinstance(s, Print):
            self._emit(Op.PRINT, arg1=s.name)
        elif isinstance(s, If):
            l_else = self._label()
            l_end = self._label()
            self.gen_cond(s.cond, l_else)
            for st in s.then_body:
                self.gen_stmt(st)
            self._emit(Op.GOTO, arg1=l_end)
            self._emit(Op.LABEL, arg1=l_else)
            if s.else_body is not None:
                for st in s.else_body:
                    self.gen_stmt(st)
            self._emit(Op.LABEL, arg1=l_end)
        elif isinstance(s, While):
            l_start = self._label()
            l_end = self._label()
            self._emit(Op.LABEL, arg1=l_start)
            self.gen_cond(s.cond, l_end)
            for st in s.body:
                self.gen_stmt(st)
            self._emit(Op.GOTO, arg1=l_start)
            self._emit(Op.LABEL, arg1=l_end)
        else:
            raise TypeError(f"unknown statement node: {type(s).__name__}")


def _collect_types(stmts: tuple[Stmt, ...], into: dict[str, str]) -> None:
    for s in stmts:
        if isinstance(s, Decl):
            into[s.name] = s.ty
        elif isinstance(s, ArrayDecl):
            into[s.name] = T_INT_ARRAY
        elif isinstance(s, If):
            _collect_types(s.then_body, into)
            if s.else_body is not None:
                _collect_types(s.else_body, into)
        elif isinstance(s, While):
            _collect_types(s.body, into)


def generate(program: Program) -> tuple[Instr, ...]:
    types: dict[str, str] = {}
    _collect_types(program.body, types)
    gen = _Generator(types)
    for stmt in program.body:
        gen.gen_stmt(stmt)
    gen._emit(Op.HALT)
    return tuple(gen._instrs)


def format_instr(ins: Instr) -> str:
    if ins.op == Op.LABEL:
        return f"{ins.arg1}:"
    if ins.op == Op.GOTO:
        return f"goto {ins.arg1}"
    if ins.op == Op.IF_FALSE:
        return f"if_false {ins.arg1} {ins.extra} {ins.arg2} goto {ins.dest}"
    if ins.op == Op.PRINT:
        return f"print {ins.arg1}"
    if ins.op == Op.HALT:
        return "halt"
    if ins.op == Op.CONST:
        lit = json.dumps(ins.arg1, ensure_ascii=False) if ins.extra == STR_CONST else ins.arg1
        return f"{ins.dest} = {lit}"
    if ins.op == Op.NEG:
        return f"{ins.dest} = -{ins.arg1}"
    if ins.op == Op.COPY:
        return f"{ins.dest} = {ins.arg1}"
    if ins.op == Op.LEN:
        return f"{ins.dest} = len {ins.arg1}"
    if ins.op == Op.NEWARR:
        return f"{ins.dest} = newarr {ins.arg1}"
    if ins.op == Op.LOAD:
        return f"{ins.dest} = {ins.arg1}[{ins.arg2}]"
    if ins.op == Op.STORE:
        return f"{ins.dest}[{ins.arg1}] = {ins.arg2}"
    return f"{ins.dest} = {ins.arg1} {ins.extra} {ins.arg2}"


def format_tac(tac: tuple[Instr, ...]) -> str:
    return "".join(f"{ins.index:4d}: {format_instr(ins)}\n" for ins in tac)
