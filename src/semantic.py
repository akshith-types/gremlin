from __future__ import annotations

from .ast_nodes import (T_INT, T_INT_ARRAY, T_STRING, ArrayDecl, Assign, BinOp, Cond, Decl, Expr,
                        If, Index, IntLit, Len, Print, Program, Stmt, Store, StrLit, UnaryNeg, Var,
                        While)
from .tac import Instr, reads, writes


class SemanticError(Exception):
    def __init__(self, message: str, line: int | None = None) -> None:
        self.line = line
        prefix = f"line {line}: " if line is not None else ""
        super().__init__(f"{prefix}{message}")


class _TypeFail(Exception):
    """Raised inside expression typing; converted into one recorded error."""

    def __init__(self, line: int, message: str) -> None:
        super().__init__(message)
        self.line = line
        self.message = message


def check(program: Program) -> dict[str, str]:
    """Single-scope symbol table + static type checking.

    Types: 'int', 'string', 'int[]'. Returns {name: type}. Raises SemanticError
    on the first problem in source order."""
    symbols: dict[str, str] = {}
    errors: list[tuple[int, str]] = []

    def declare(name: str, ty: str, line: int) -> None:
        if name in symbols:
            errors.append((line, f"variable '{name}' redeclared"))
        else:
            symbols[name] = ty

    def lookup(name: str, line: int) -> str:
        if name not in symbols:
            raise _TypeFail(line, f"use of undeclared variable '{name}'")
        return symbols[name]

    def type_of(e: Expr) -> str:
        if isinstance(e, IntLit):
            return T_INT
        if isinstance(e, StrLit):
            return T_STRING
        if isinstance(e, Var):
            return lookup(e.name, e.line)
        if isinstance(e, Index):
            base = lookup(e.name, e.line)
            if type_of(e.index) != T_INT:
                raise _TypeFail(e.line, f"index into '{e.name}' must be an int")
            if base == T_INT_ARRAY:
                return T_INT
            if base == T_STRING:
                return T_STRING
            raise _TypeFail(e.line, f"'{e.name}' is an {base}, it cannot be indexed")
        if isinstance(e, Len):
            t = type_of(e.operand)
            if t not in (T_STRING, T_INT_ARRAY):
                raise _TypeFail(e.line, f"len() needs a string or an array, got {t}")
            return T_INT
        if isinstance(e, UnaryNeg):
            if type_of(e.operand) != T_INT:
                raise _TypeFail(e.line, "unary '-' needs an int operand")
            return T_INT
        if isinstance(e, BinOp):
            lt, rt = type_of(e.left), type_of(e.right)
            if e.op == "+" and lt == rt == T_STRING:
                return T_STRING
            if lt == rt == T_INT:
                return T_INT
            raise _TypeFail(e.line, f"operator '{e.op}' cannot combine {lt} and {rt}")
        raise TypeError(f"unknown expression node: {type(e).__name__}")

    def expect(e: Expr, want: str, what: str) -> None:
        got = type_of(e)
        if got != want:
            raise _TypeFail(e.line, f"{what}: expected {want}, got {got}")

    def walk_cond(c: Cond) -> None:
        lt, rt = type_of(c.left), type_of(c.right)
        if lt != rt or lt == T_INT_ARRAY:
            raise _TypeFail(c.line, f"cannot compare {lt} with {rt}")

    def walk_stmt(s: Stmt) -> None:
        try:
            if isinstance(s, Decl):
                if s.init is not None:
                    expect(s.init, s.ty, f"initializer of '{s.name}'")
                declare(s.name, s.ty, s.line)
            elif isinstance(s, ArrayDecl):
                if s.size <= 0:
                    raise _TypeFail(s.line, f"array '{s.name}' must have a positive size")
                if len(s.init) > s.size:
                    raise _TypeFail(s.line, f"too many initializers for '{s.name}[{s.size}]'")
                for e in s.init:
                    expect(e, T_INT, f"element of '{s.name}'")
                declare(s.name, T_INT_ARRAY, s.line)
            elif isinstance(s, Assign):
                target = lookup(s.name, s.line)
                if target == T_INT_ARRAY:
                    raise _TypeFail(s.line, f"cannot assign to array '{s.name}' as a whole")
                expect(s.value, target, f"assignment to '{s.name}'")
            elif isinstance(s, Store):
                target = lookup(s.name, s.line)
                if target == T_STRING:
                    raise _TypeFail(s.line, f"strings are immutable: cannot assign to '{s.name}[...]'")
                if target != T_INT_ARRAY:
                    raise _TypeFail(s.line, f"'{s.name}' is not an array")
                expect(s.index, T_INT, f"index into '{s.name}'")
                expect(s.value, T_INT, f"element of '{s.name}'")
            elif isinstance(s, Print):
                lookup(s.name, s.line)
            elif isinstance(s, If):
                walk_cond(s.cond)
                for st in s.then_body:
                    walk_stmt(st)
                if s.else_body is not None:
                    for st in s.else_body:
                        walk_stmt(st)
            elif isinstance(s, While):
                walk_cond(s.cond)
                for st in s.body:
                    walk_stmt(st)
            else:
                raise TypeError(f"unknown statement node: {type(s).__name__}")
        except _TypeFail as exc:
            errors.append((exc.line, exc.message))

    for stmt in program.body:
        walk_stmt(stmt)

    if errors:
        line, msg = errors[0]
        raise SemanticError(msg, line)
    return symbols


def analyze(program: Program) -> tuple[str, ...]:
    """Backwards-compatible entry point: declared variable names, sorted."""
    return tuple(sorted(check(program)))


def check_initialized(tac: tuple[Instr, ...]) -> None:
    """Conservative linear-scan rule: a name may be read only after a linearly
    preceding definition. Guarantees the interpreter can never hit an
    uninitialized read on the ORIGINAL program (mutants may trap - by design)."""
    assigned: set[str] = set()
    for ins in tac:
        for r in reads(ins):
            if r not in assigned:
                raise SemanticError(
                    f"instruction {ins.index}: '{r}' may be used before initialization"
                )
        w = writes(ins)
        if w is not None:
            assigned.add(w)
