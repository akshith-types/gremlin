# Generated from grammar/GremlinC.g4 by ANTLR 4.13.1
from antlr4 import *
if "." in __name__:
    from .GremlinCParser import GremlinCParser
else:
    from GremlinCParser import GremlinCParser

# This class defines a complete listener for a parse tree produced by GremlinCParser.
class GremlinCListener(ParseTreeListener):

    # Enter a parse tree produced by GremlinCParser#program.
    def enterProgram(self, ctx:GremlinCParser.ProgramContext):
        pass

    # Exit a parse tree produced by GremlinCParser#program.
    def exitProgram(self, ctx:GremlinCParser.ProgramContext):
        pass


    # Enter a parse tree produced by GremlinCParser#statement.
    def enterStatement(self, ctx:GremlinCParser.StatementContext):
        pass

    # Exit a parse tree produced by GremlinCParser#statement.
    def exitStatement(self, ctx:GremlinCParser.StatementContext):
        pass


    # Enter a parse tree produced by GremlinCParser#declStmt.
    def enterDeclStmt(self, ctx:GremlinCParser.DeclStmtContext):
        pass

    # Exit a parse tree produced by GremlinCParser#declStmt.
    def exitDeclStmt(self, ctx:GremlinCParser.DeclStmtContext):
        pass


    # Enter a parse tree produced by GremlinCParser#arrDeclStmt.
    def enterArrDeclStmt(self, ctx:GremlinCParser.ArrDeclStmtContext):
        pass

    # Exit a parse tree produced by GremlinCParser#arrDeclStmt.
    def exitArrDeclStmt(self, ctx:GremlinCParser.ArrDeclStmtContext):
        pass


    # Enter a parse tree produced by GremlinCParser#typeName.
    def enterTypeName(self, ctx:GremlinCParser.TypeNameContext):
        pass

    # Exit a parse tree produced by GremlinCParser#typeName.
    def exitTypeName(self, ctx:GremlinCParser.TypeNameContext):
        pass


    # Enter a parse tree produced by GremlinCParser#assignStmt.
    def enterAssignStmt(self, ctx:GremlinCParser.AssignStmtContext):
        pass

    # Exit a parse tree produced by GremlinCParser#assignStmt.
    def exitAssignStmt(self, ctx:GremlinCParser.AssignStmtContext):
        pass


    # Enter a parse tree produced by GremlinCParser#storeStmt.
    def enterStoreStmt(self, ctx:GremlinCParser.StoreStmtContext):
        pass

    # Exit a parse tree produced by GremlinCParser#storeStmt.
    def exitStoreStmt(self, ctx:GremlinCParser.StoreStmtContext):
        pass


    # Enter a parse tree produced by GremlinCParser#ifStmt.
    def enterIfStmt(self, ctx:GremlinCParser.IfStmtContext):
        pass

    # Exit a parse tree produced by GremlinCParser#ifStmt.
    def exitIfStmt(self, ctx:GremlinCParser.IfStmtContext):
        pass


    # Enter a parse tree produced by GremlinCParser#whileStmt.
    def enterWhileStmt(self, ctx:GremlinCParser.WhileStmtContext):
        pass

    # Exit a parse tree produced by GremlinCParser#whileStmt.
    def exitWhileStmt(self, ctx:GremlinCParser.WhileStmtContext):
        pass


    # Enter a parse tree produced by GremlinCParser#printStmt.
    def enterPrintStmt(self, ctx:GremlinCParser.PrintStmtContext):
        pass

    # Exit a parse tree produced by GremlinCParser#printStmt.
    def exitPrintStmt(self, ctx:GremlinCParser.PrintStmtContext):
        pass


    # Enter a parse tree produced by GremlinCParser#block.
    def enterBlock(self, ctx:GremlinCParser.BlockContext):
        pass

    # Exit a parse tree produced by GremlinCParser#block.
    def exitBlock(self, ctx:GremlinCParser.BlockContext):
        pass


    # Enter a parse tree produced by GremlinCParser#cond.
    def enterCond(self, ctx:GremlinCParser.CondContext):
        pass

    # Exit a parse tree produced by GremlinCParser#cond.
    def exitCond(self, ctx:GremlinCParser.CondContext):
        pass


    # Enter a parse tree produced by GremlinCParser#relop.
    def enterRelop(self, ctx:GremlinCParser.RelopContext):
        pass

    # Exit a parse tree produced by GremlinCParser#relop.
    def exitRelop(self, ctx:GremlinCParser.RelopContext):
        pass


    # Enter a parse tree produced by GremlinCParser#expr.
    def enterExpr(self, ctx:GremlinCParser.ExprContext):
        pass

    # Exit a parse tree produced by GremlinCParser#expr.
    def exitExpr(self, ctx:GremlinCParser.ExprContext):
        pass


    # Enter a parse tree produced by GremlinCParser#term.
    def enterTerm(self, ctx:GremlinCParser.TermContext):
        pass

    # Exit a parse tree produced by GremlinCParser#term.
    def exitTerm(self, ctx:GremlinCParser.TermContext):
        pass


    # Enter a parse tree produced by GremlinCParser#factor.
    def enterFactor(self, ctx:GremlinCParser.FactorContext):
        pass

    # Exit a parse tree produced by GremlinCParser#factor.
    def exitFactor(self, ctx:GremlinCParser.FactorContext):
        pass


    # Enter a parse tree produced by GremlinCParser#addOp.
    def enterAddOp(self, ctx:GremlinCParser.AddOpContext):
        pass

    # Exit a parse tree produced by GremlinCParser#addOp.
    def exitAddOp(self, ctx:GremlinCParser.AddOpContext):
        pass


    # Enter a parse tree produced by GremlinCParser#mulOp.
    def enterMulOp(self, ctx:GremlinCParser.MulOpContext):
        pass

    # Exit a parse tree produced by GremlinCParser#mulOp.
    def exitMulOp(self, ctx:GremlinCParser.MulOpContext):
        pass



del GremlinCParser