grammar GremlinC;

// ---------------------------------------------------------------- parser
program     : statement* EOF ;

statement   : declStmt | arrDeclStmt | assignStmt | storeStmt
            | ifStmt | whileStmt | printStmt ;

declStmt    : typeName ID (ASSIGN expr)? SEMI ;               // int x = 1;  string s = "hi";
arrDeclStmt : INT_KW ID LBRACK INT RBRACK
              (ASSIGN LBRACE expr (COMMA expr)* RBRACE)? SEMI ; // int a[4] = {1, 2, 3};
typeName    : INT_KW | STRING_KW ;
assignStmt  : ID ASSIGN expr SEMI ;
storeStmt   : ID LBRACK expr RBRACK ASSIGN expr SEMI ;      // a[i] = e;
ifStmt      : IF_KW LPAREN cond RPAREN block (ELSE_KW block)? ;
whileStmt   : WHILE_KW LPAREN cond RPAREN block ;
printStmt   : PRINT_KW (LPAREN ID RPAREN | ID) SEMI ;
block       : LBRACE statement* RBRACE ;

cond        : expr relop expr ;
relop       : LT | LE | GT | GE | EQ | NE ;

expr        : term (addOp term)* ;
term        : factor (mulOp factor)* ;
factor      : INT
            | STRING
            | LEN_KW LPAREN expr RPAREN
            | ID LBRACK expr RBRACK
            | ID
            | LPAREN expr RPAREN
            | MINUS factor ;
addOp       : PLUS | MINUS ;
mulOp       : STAR | SLASH | PERCENT ;

// ---------------------------------------------------------------- lexer
INT_KW      : 'int' ;
STRING_KW   : 'string' ;
IF_KW       : 'if' ;
ELSE_KW     : 'else' ;
WHILE_KW    : 'while' ;
PRINT_KW    : 'print' ;
LEN_KW      : 'len' ;

ASSIGN      : '=' ;
SEMI        : ';' ;
COMMA       : ',' ;
LPAREN      : '(' ;
RPAREN      : ')' ;
LBRACE      : '{' ;
RBRACE      : '}' ;
LBRACK      : '[' ;
RBRACK      : ']' ;

LE          : '<=' ;
GE          : '>=' ;
EQ          : '==' ;
NE          : '!=' ;
LT          : '<' ;
GT          : '>' ;

PLUS        : '+' ;
MINUS       : '-' ;
STAR        : '*' ;
SLASH       : '/' ;
PERCENT     : '%' ;

INT         : [0-9]+ ;
STRING      : '"' ( '\\' [\\"nt] | ~["\\\r\n] )* '"' ;
ID          : [a-zA-Z_][a-zA-Z_0-9]* ;

WS           : [ \t\r\n]+ -> skip ;
LINE_COMMENT : '//' ~[\r\n]* -> skip ;
