from enum import Enum, auto


class TokenType(Enum):
    # 字面量
    NUMBER = auto()
    STRING = auto()
    IDENTIFIER = auto()

    # 关键字
    LET = auto()
    FN = auto()
    IF = auto()
    ELSE = auto()
    WHILE = auto()
    FOR = auto()
    RETURN = auto()
    TRUE = auto()
    FALSE = auto()
    NIL = auto()
    PRINT = auto()

    # 单字符符号
    LEFT_PAREN = auto()
    RIGHT_PAREN = auto()
    LEFT_BRACE = auto()
    RIGHT_BRACE = auto()
    COMMA = auto()
    DOT = auto()
    SEMICOLON = auto()
    COLON = auto()

    # 运算符
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    ASSIGN = auto()
    EQUAL = auto()
    NOT_EQUAL = auto()
    LESS = auto()
    LESS_EQUAL = auto()
    GREATER = auto()
    GREATER_EQUAL = auto()
    AND = auto()
    OR = auto()
    NOT = auto()

    # 特殊
    EOF = auto()


class Token:
    __slots__ = ['type', 'value', 'line', 'column']

    def __init__(self, type: TokenType, value, line: int, column: int):
        self.type = type
        self.value = value
        self.line = line
        self.column = column

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, line={self.line}, col={self.column})"


KEYWORDS = {
    'let': TokenType.LET,
    'fn': TokenType.FN,
    'if': TokenType.IF,
    'else': TokenType.ELSE,
    'while': TokenType.WHILE,
    'for': TokenType.FOR,
    'return': TokenType.RETURN,
    'true': TokenType.TRUE,
    'false': TokenType.FALSE,
    'nil': TokenType.NIL,
    'print': TokenType.PRINT,
    'and': TokenType.AND,
    'or': TokenType.OR,
}
