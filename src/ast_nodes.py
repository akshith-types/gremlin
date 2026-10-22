from __future__ import annotations

from dataclasses import dataclass

# Static types of the GremlinC language.
T_INT = "int"
T_STRING = "string"
T_INT_ARRAY = "int[]"


@dataclass(frozen=True)
class Expr:
    line: int


@dataclass(frozen=True)
class IntLit(Expr):
    value: int


@dataclass(frozen=True)
class StrLit(Expr):
    value: str


@dataclass(frozen=True)
class Var(Expr):
    name: str


@dataclass(frozen=True)
class Index(Expr):
    """a[i] for an int array, or s[i] (a one-character string) for a string."""
    name: str
    index: Expr


@dataclass(frozen=True)
class Len(Expr):
    operand: Expr


@dataclass(frozen=True)
class BinOp(Expr):
    op: str
    left: Expr
    right: Expr


@dataclass(frozen=True)
class UnaryNeg(Expr):
    operand: Expr


@dataclass(frozen=True)
class Cond:
    op: str
    left: Expr
    right: Expr
    line: int


@dataclass(frozen=True)
class Stmt:
    line: int


@dataclass(frozen=True)
class Decl(Stmt):
    name: str
    init: Expr | None
    ty: str = T_INT


@dataclass(frozen=True)
class ArrayDecl(Stmt):
    name: str
    size: int
    init: tuple[Expr, ...] = ()


@dataclass(frozen=True)
class Assign(Stmt):
    name: str
    value: Expr


@dataclass(frozen=True)
class Store(Stmt):
    name: str
    index: Expr
    value: Expr


@dataclass(frozen=True)
class If(Stmt):
    cond: Cond
    then_body: tuple[Stmt, ...]
    else_body: tuple[Stmt, ...] | None


@dataclass(frozen=True)
class While(Stmt):
    cond: Cond
    body: tuple[Stmt, ...]


@dataclass(frozen=True)
class Print(Stmt):
    name: str


@dataclass(frozen=True)
class Program:
    body: tuple[Stmt, ...]
