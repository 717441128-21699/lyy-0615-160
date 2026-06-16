from token_types import Token, TokenType, KEYWORDS
from errors import LexerError


class Lexer:
    def __init__(self, source: str, source_path=None):
        self.source = source
        self.source_path = source_path
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens = []

    def peek(self, offset: int = 0) -> str:
        idx = self.pos + offset
        if idx >= len(self.source):
            return '\0'
        return self.source[idx]

    def advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def match(self, expected: str) -> bool:
        if self.peek() != expected:
            return False
        self.advance()
        return True

    def skip_whitespace_and_comments(self):
        while True:
            ch = self.peek()
            if ch in ' \t\r\n':
                self.advance()
            elif ch == '/' and self.peek(1) == '/':
                while self.peek() != '\n' and self.peek() != '\0':
                    self.advance()
            elif ch == '/' and self.peek(1) == '*':
                self.advance()
                self.advance()
                while True:
                    if self.peek() == '*' and self.peek(1) == '/':
                        self.advance()
                        self.advance()
                        break
                    if self.peek() == '\0':
                        raise LexerError("未闭合的块注释", self.line, self.column)
                    self.advance()
            else:
                break

    def read_number(self) -> Token:
        start_col = self.column
        start_pos = self.pos
        while self.peek().isdigit():
            self.advance()
        is_float = False
        if self.peek() == '.' and self.peek(1).isdigit():
            is_float = True
            self.advance()
            while self.peek().isdigit():
                self.advance()
        raw = self.source[start_pos:self.pos]
        value = float(raw) if is_float else int(raw)
        return Token(TokenType.NUMBER, value, self.line, start_col)

    def read_string(self) -> Token:
        quote = self.peek()
        start_col = self.column
        self.advance()
        chars = []
        while self.peek() != quote:
            ch = self.peek()
            if ch == '\0' or ch == '\n':
                raise LexerError("未闭合的字符串字面量", self.line, start_col)
            if ch == '\\':
                self.advance()
                esc = self.peek()
                if esc == 'n':
                    chars.append('\n')
                elif esc == 't':
                    chars.append('\t')
                elif esc == 'r':
                    chars.append('\r')
                elif esc == '\\':
                    chars.append('\\')
                elif esc == '"' or esc == "'":
                    chars.append(esc)
                elif esc == '0':
                    chars.append('\0')
                else:
                    raise LexerError(f"未知的转义序列: \\{esc}", self.line, self.column)
                self.advance()
            else:
                chars.append(ch)
                self.advance()
        self.advance()
        return Token(TokenType.STRING, ''.join(chars), self.line, start_col)

    def read_identifier(self) -> Token:
        start_col = self.column
        start_pos = self.pos
        while self.peek().isalnum() or self.peek() == '_':
            self.advance()
        raw = self.source[start_pos:self.pos]
        tt = KEYWORDS.get(raw, TokenType.IDENTIFIER)
        return Token(tt, raw, self.line, start_col)

    def add_token(self, type: TokenType, value=None, column=None):
        col = column if column is not None else self.column
        self.tokens.append(Token(type, value, self.line, col))

    def tokenize(self) -> list:
        try:
            while self.pos < len(self.source):
                self.skip_whitespace_and_comments()
                if self.pos >= len(self.source):
                    break

                start_col = self.column
                ch = self.peek()

                if ch.isdigit():
                    self.tokens.append(self.read_number())
                    continue
                if ch == '"' or ch == "'":
                    self.tokens.append(self.read_string())
                    continue
                if ch.isalpha() or ch == '_':
                    self.tokens.append(self.read_identifier())
                    continue

                # 单/双字符符号
                if ch == '(':
                    self.advance(); self.add_token(TokenType.LEFT_PAREN, column=start_col)
                elif ch == ')':
                    self.advance(); self.add_token(TokenType.RIGHT_PAREN, column=start_col)
                elif ch == '{':
                    self.advance(); self.add_token(TokenType.LEFT_BRACE, column=start_col)
                elif ch == '}':
                    self.advance(); self.add_token(TokenType.RIGHT_BRACE, column=start_col)
                elif ch == '[':
                    self.advance(); self.add_token(TokenType.LEFT_BRACKET, column=start_col)
                elif ch == ']':
                    self.advance(); self.add_token(TokenType.RIGHT_BRACKET, column=start_col)
                elif ch == ',':
                    self.advance(); self.add_token(TokenType.COMMA, column=start_col)
                elif ch == '.':
                    self.advance(); self.add_token(TokenType.DOT, column=start_col)
                elif ch == ';':
                    self.advance(); self.add_token(TokenType.SEMICOLON, column=start_col)
                elif ch == ':':
                    self.advance(); self.add_token(TokenType.COLON, column=start_col)
                elif ch == '+':
                    self.advance(); self.add_token(TokenType.PLUS, column=start_col)
                elif ch == '-':
                    self.advance(); self.add_token(TokenType.MINUS, column=start_col)
                elif ch == '*':
                    self.advance(); self.add_token(TokenType.STAR, column=start_col)
                elif ch == '/':
                    self.advance(); self.add_token(TokenType.SLASH, column=start_col)
                elif ch == '%':
                    self.advance(); self.add_token(TokenType.PERCENT, column=start_col)
                elif ch == '=':
                    self.advance()
                    if self.match('='):
                        self.add_token(TokenType.EQUAL, column=start_col)
                    else:
                        self.add_token(TokenType.ASSIGN, column=start_col)
                elif ch == '!':
                    self.advance()
                    if self.match('='):
                        self.add_token(TokenType.NOT_EQUAL, column=start_col)
                    else:
                        self.add_token(TokenType.NOT, column=start_col)
                elif ch == '<':
                    self.advance()
                    if self.match('='):
                        self.add_token(TokenType.LESS_EQUAL, column=start_col)
                    else:
                        self.add_token(TokenType.LESS, column=start_col)
                elif ch == '>':
                    self.advance()
                    if self.match('='):
                        self.add_token(TokenType.GREATER_EQUAL, column=start_col)
                    else:
                        self.add_token(TokenType.GREATER, column=start_col)
                else:
                    raise LexerError(f"未知字符: {ch!r}", self.line, start_col)

            self.tokens.append(Token(TokenType.EOF, None, self.line, self.column))
            return self.tokens
        except LexerError as e:
            e.source_path = self.source_path
            raise
