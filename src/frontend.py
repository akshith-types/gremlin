from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

from .ast_nodes import (T_INT, T_STRING, ArrayDecl, Assign, BinOp, Cond, Decl, Expr, If, Index,
                        IntLit, Len, Print, Program, Stmt, Store, StrLit, UnaryNeg, Var, While)

_GEN_DIR = Path(__file__).resolve().parent / "gen"
if not (_GEN_DIR / "GremlinCLexer.py").exists() or not (_GEN_DIR / "GremlinCParser.py").exists():
    sys.stderr.write(
        "error: generated ANTLR parser not found in src/gen.\n"
        "       run './setup.sh' first (requires a Java runtime).\n"
    )
    raise SystemExit(2)
if str(_GEN_DIR) not in sys.path:
    sys.path.insert(0, str(_GEN_DIR))

from antlr4 import CommonTokenStream, InputStream  # noqa: E402
from antlr4.error.ErrorListener import ErrorListener  # noqa: E402
from GremlinCLexer import GremlinCLexer  # noqa: E402
from GremlinCParser import GremlinCParser  # noqa: E402
from GremlinCVisitor import GremlinCVisitor  # noqa: E402


class FrontendError(Exception):
    def __init__(self, message: str, line: int) -> None:
        self.line = line
        super().__init__(f"line {line}: {message}")


class _Collect(ErrorListener):  # type: ignore[misc]
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []

    def syntaxError(self, recognizer: Any, offendingSymbol: Any, line: int,
                    column: int, msg: str, e: Any) -> None:
        self.messages.append((line, msg))


_ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}


def _unescape(token: str) -> str:
    """Turn the source text of a STRING token (quotes included) into its value."""
    body = token[1:-1]
    out: list[str] = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            out.append(_ESCAPES.get(body[i + 1], body[i + 1]))
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


class _AstBuilder(GremlinCVisitor):  # type: ignore[misc]
    def visitProgram(self, ctx: Any) -> Program:
        stmts = tuple(cast(Stmt, s.accept(self)) for s in ctx.statement())
        if not stmts:
            raise FrontendError("input contains no statements", 1)
        return Program(body=stmts)

    def visitDeclStmt(self, ctx: Any) -> Decl:
        init = cast(Expr, ctx.expr().accept(self)) if ctx.expr() is not None else None
        ty = T_STRING if ctx.typeName().STRING_KW() is not None else T_INT
        return Decl(line=ctx.start.line, name=ctx.ID().getText(), init=init, ty=ty)

    def visitArrDeclStmt(self, ctx: Any) -> ArrayDecl:
        init = tuple(cast(Expr, e.accept(self)) for e in ctx.expr())
        return ArrayDecl(line=ctx.start.line, name=ctx.ID().getText(),
                         size=int(ctx.INT().getText()), init=init)

    def visitStoreStmt(self, ctx: Any) -> Store:
        return Store(line=ctx.start.line, name=ctx.ID().getText(),
                     index=cast(Expr, ctx.expr(0).accept(self)),
                     value=cast(Expr, ctx.expr(1).accept(self)))

    def visitAssignStmt(self, ctx: Any) -> Assign:
        return Assign(line=ctx.start.line, name=ctx.ID().getText(),
                      value=cast(Expr, ctx.expr().accept(self)))

    def visitPrintStmt(self, ctx: Any) -> Print:
        var_name = ctx.ID().getText()
        return Print(name=var_name, line=ctx.start.line)

    def visitIfStmt(self, ctx: Any) -> If:
        blocks = ctx.block()
        then_body = tuple(cast(Stmt, s.accept(self)) for s in blocks[0].statement())
        else_body: tuple[Stmt, ...] | None = None
        if len(blocks) > 1:
            else_body = tuple(cast(Stmt, s.accept(self)) for s in blocks[1].statement())
        cond = cast(Cond, ctx.cond().accept(self))
        return If(line=ctx.start.line, cond=cond, then_body=then_body, else_body=else_body)

    def visitWhileStmt(self, ctx: Any) -> While:
        body = tuple(cast(Stmt, s.accept(self)) for s in ctx.block().statement())
        cond = cast(Cond, ctx.cond().accept(self))
        return While(cond=cond, body=body, line=ctx.start.line)
    def visitCond(self, ctx: Any) -> Cond:
        return Cond(line=ctx.start.line, op=ctx.relop().getText(),
                    left=cast(Expr, ctx.expr(0).accept(self)),
                    right=cast(Expr, ctx.expr(1).accept(self)))

    def visitExpr(self, ctx: Any) -> Expr:
        terms = ctx.term()
        node = cast(Expr, terms[0].accept(self))
        for op_ctx, term_ctx in zip(ctx.addOp(), terms[1:]):
            node = BinOp(line=op_ctx.start.line, op=op_ctx.getText(), left=node,
                         right=cast(Expr, term_ctx.accept(self)))
        return node

    def visitTerm(self, ctx: Any) -> Expr:
        factors = ctx.factor()
        node = cast(Expr, factors[0].accept(self))
        for op_ctx, factor_ctx in zip(ctx.mulOp(), factors[1:]):
            node = BinOp(line=op_ctx.start.line, op=op_ctx.getText(), left=node,
                         right=cast(Expr, factor_ctx.accept(self)))
        return node

    def visitFactor(self, ctx: Any) -> Expr:
        if ctx.INT() is not None:
            return IntLit(line=ctx.start.line, value=int(ctx.INT().getText()))
        if ctx.STRING() is not None:
            return StrLit(line=ctx.start.line, value=_unescape(ctx.STRING().getText()))
        if ctx.LEN_KW() is not None:
            return Len(line=ctx.start.line, operand=cast(Expr, ctx.expr().accept(self)))
        if ctx.ID() is not None and ctx.LBRACK() is not None:
            return Index(line=ctx.start.line, name=ctx.ID().getText(),
                         index=cast(Expr, ctx.expr().accept(self)))
        if ctx.ID() is not None:
            return Var(line=ctx.start.line, name=ctx.ID().getText())
        if ctx.expr() is not None:
            return cast(Expr, ctx.expr().accept(self))
        return UnaryNeg(line=ctx.start.line,
                        operand=cast(Expr, ctx.factor().accept(self)))


def parse_source(source: str) -> Program:
    collector = _Collect()
    lexer = GremlinCLexer(InputStream(source))
    lexer.removeErrorListeners()
    lexer.addErrorListener(collector)
    parser = GremlinCParser(CommonTokenStream(lexer))
    parser.removeErrorListeners()
    parser.addErrorListener(collector)
    tree = parser.program()
    if collector.messages:
        line, msg = collector.messages[0]
        raise FrontendError(f"syntax error: {msg}", line)
    return cast(Program, tree.accept(_AstBuilder()))