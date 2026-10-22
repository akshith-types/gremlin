# Generated from grammar/GremlinC.g4 by ANTLR 4.13.1
from antlr4 import *
if "." in __name__:
    from .GremlinCParser import GremlinCParser
else:
    from GremlinCParser import GremlinCParser

# This class defines a complete generic visitor for a parse tree produced by GremlinCParser.

class GremlinCVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by GremlinCParser#program.
    def visitProgram(self, ctx:GremlinCParser.ProgramContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GremlinCParser#statement.
    def visitStatement(self, ctx:GremlinCParser.StatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GremlinCParser#declStmt.
    def visitDeclStmt(self, ctx:GremlinCParser.DeclStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GremlinCParser#arrDeclStmt.
    def visitArrDeclStmt(self, ctx:GremlinCParser.ArrDeclStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GremlinCParser#typeName.
    def visitTypeName(self, ctx:GremlinCParser.TypeNameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GremlinCParser#assignStmt.
    def visitAssignStmt(self, ctx:GremlinCParser.AssignStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GremlinCParser#storeStmt.
    def visitStoreStmt(self, ctx:GremlinCParser.StoreStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GremlinCParser#ifStmt.
    def visitIfStmt(self, ctx:GremlinCParser.IfStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GremlinCParser#whileStmt.
    def visitWhileStmt(self, ctx:GremlinCParser.WhileStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GremlinCParser#printStmt.
    def visitPrintStmt(self, ctx:GremlinCParser.PrintStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GremlinCParser#block.
    def visitBlock(self, ctx:GremlinCParser.BlockContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GremlinCParser#cond.
    def visitCond(self, ctx:GremlinCParser.CondContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GremlinCParser#relop.
    def visitRelop(self, ctx:GremlinCParser.RelopContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GremlinCParser#expr.
    def visitExpr(self, ctx:GremlinCParser.ExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GremlinCParser#term.
    def visitTerm(self, ctx:GremlinCParser.TermContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GremlinCParser#factor.
    def visitFactor(self, ctx:GremlinCParser.FactorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GremlinCParser#addOp.
    def visitAddOp(self, ctx:GremlinCParser.AddOpContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by GremlinCParser#mulOp.
    def visitMulOp(self, ctx:GremlinCParser.MulOpContext):
        return self.visitChildren(ctx)



del GremlinCParser