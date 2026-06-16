from token_types import Token, TokenType
from errors import ParseError
from ast_nodes import (
    Program, NumberLiteral, StringLiteral, BooleanLiteral, NilLiteral,
    Identifier, Assignment, VariableDeclaration, FunctionDeclaration,
    Lambda, Call, Block, IfStatement, WhileStatement, ForStatement,
    ReturnStatement, PrintStatement, BinaryOp, UnaryOp, LogicalOp,
    ExpressionStatement, ArrayLiteral, DictLiteral, Subscript,
    ImportStatement,
)


# Pratt 解析器: 运算符优先级表 (binding power)
PRECEDENCE = {
    'OR': 10,
    'AND': 20,
    'EQUALITY': 30,
    'COMPARISON': 40,
    'TERM': 50,
    'FACTOR': 60,
    'UNARY': 70,
    'CALL': 80,
    'PRIMARY': 90,
}


class Parser:
    def __init__(self, tokens: list, source_path=None):
        self.tokens = tokens
        self.pos = 0
        self.source_path = source_path

    # ---------- 辅助方法 ----------
    def peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]

    def check(self, *types) -> bool:
        return self.peek().type in types

    def advance(self) -> Token:
        tok = self.peek()
        self.pos += 1
        return tok

    def consume(self, type: TokenType, message: str) -> Token:
        if self.check(type):
            return self.advance()
        raise ParseError.from_token(message, self.peek())

    def expect_semicolon(self):
        if self.check(TokenType.SEMICOLON):
            self.advance()

    def match(self, type: TokenType) -> bool:
        if self.check(type):
            self.advance()
            return True
        return False

    # ---------- 入口 ----------
    def parse(self) -> Program:
        try:
            stmts = []
            first_token = self.peek()
            while not self.check(TokenType.EOF):
                stmt = self.parse_declaration()
                if stmt is not None:
                    stmts.append(stmt)
            return Program(stmts, token=first_token)
        except ParseError as e:
            e.source_path = self.source_path
            raise

    # ---------- 声明 (最高层级) ----------
    def parse_declaration(self):
        # 前瞻: 'fn' 可能是具名函数声明, 也可能是匿名函数表达式 (IIFE)
        # 如果 FN 之后是 IDENTIFIER → 函数声明；否则 → 表达式语句
        if self.check(TokenType.IMPORT):
            return self.parse_import_statement()
        if self.check(TokenType.FN) and self.peek(1).type == TokenType.IDENTIFIER:
            return self.parse_function_declaration()
        if self.check(TokenType.LET):
            return self.parse_variable_declaration()
        return self.parse_statement()

    def parse_variable_declaration(self):
        start = self.consume(TokenType.LET, "期望 'let' 关键字")
        name = self.consume(TokenType.IDENTIFIER, "期望变量名").value
        initializer = None
        if self.match(TokenType.ASSIGN):
            initializer = self.parse_expression()
        self.expect_semicolon()
        return VariableDeclaration(name, initializer, token=start)

    def parse_function_declaration(self):
        start = self.consume(TokenType.FN, "期望 'fn' 关键字")
        name = self.consume(TokenType.IDENTIFIER, "期望函数名").value
        self.consume(TokenType.LEFT_PAREN, "期望 '(' 位于函数名之后")
        params = []
        if not self.check(TokenType.RIGHT_PAREN):
            params.append(self.consume(TokenType.IDENTIFIER, "期望参数名").value)
            while self.match(TokenType.COMMA):
                if len(params) >= 255:
                    raise ParseError.from_token("参数数量不能超过 255 个", self.peek())
                params.append(self.consume(TokenType.IDENTIFIER, "期望参数名").value)
        self.consume(TokenType.RIGHT_PAREN, "期望 ')' 位于参数列表之后")
        body = self.parse_block_statement()
        return FunctionDeclaration(name, params, body, token=start)

    # ---------- 语句 ----------
    def parse_statement(self):
        if self.check(TokenType.IF):
            return self.parse_if_statement()
        if self.check(TokenType.WHILE):
            return self.parse_while_statement()
        if self.check(TokenType.FOR):
            return self.parse_for_statement()
        if self.check(TokenType.RETURN):
            return self.parse_return_statement()
        if self.check(TokenType.PRINT):
            return self.parse_print_statement()
        if self.check(TokenType.LEFT_BRACE):
            return self.parse_block_statement()
        return self.parse_expression_statement()

    def parse_if_statement(self):
        start = self.consume(TokenType.IF, "期望 'if' 关键字")
        self.consume(TokenType.LEFT_PAREN, "期望 '(' 位于 'if' 之后")
        condition = self.parse_expression()
        self.consume(TokenType.RIGHT_PAREN, "期望 ')' 位于条件表达式之后")
        then_branch = self.parse_statement()
        else_branch = None
        if self.match(TokenType.ELSE):
            else_branch = self.parse_statement()
        return IfStatement(condition, then_branch, else_branch, token=start)

    def parse_while_statement(self):
        start = self.consume(TokenType.WHILE, "期望 'while' 关键字")
        self.consume(TokenType.LEFT_PAREN, "期望 '(' 位于 'while' 之后")
        condition = self.parse_expression()
        self.consume(TokenType.RIGHT_PAREN, "期望 ')' 位于条件表达式之后")
        body = self.parse_statement()
        return WhileStatement(condition, body, token=start)

    def parse_for_statement(self):
        start = self.consume(TokenType.FOR, "期望 'for' 关键字")
        self.consume(TokenType.LEFT_PAREN, "期望 '(' 位于 'for' 之后")

        init = None
        if self.match(TokenType.SEMICOLON):
            pass
        elif self.check(TokenType.LET):
            init = self.parse_variable_declaration()
        else:
            init = self.parse_expression_statement()

        condition = None
        if not self.check(TokenType.SEMICOLON):
            condition = self.parse_expression()
        self.consume(TokenType.SEMICOLON, "期望 ';' 位于循环条件之后")

        update = None
        if not self.check(TokenType.RIGHT_PAREN):
            update = self.parse_expression()
        self.consume(TokenType.RIGHT_PAREN, "期望 ')' 位于 for 子句之后")

        body = self.parse_statement()
        return ForStatement(init, condition, update, body, token=start)

    def parse_return_statement(self):
        start = self.consume(TokenType.RETURN, "期望 'return' 关键字")
        value = None
        if not self.check(TokenType.SEMICOLON) and not self.check(TokenType.EOF) \
                and not self.check(TokenType.RIGHT_BRACE):
            value = self.parse_expression()
        self.expect_semicolon()
        return ReturnStatement(value, token=start)

    def parse_print_statement(self):
        start = self.consume(TokenType.PRINT, "期望 'print' 关键字")
        value = self.parse_expression()
        self.expect_semicolon()
        return PrintStatement(value, token=start)

    def parse_import_statement(self):
        start = self.consume(TokenType.IMPORT, "期望 'import' 关键字")
        path_tok = self.consume(TokenType.STRING, "期望模块路径字符串")
        self.expect_semicolon()
        return ImportStatement(path_tok.value, token=start)

    def parse_block_statement(self):
        start = self.consume(TokenType.LEFT_BRACE, "期望 '{'")
        stmts = []
        while not self.check(TokenType.RIGHT_BRACE) and not self.check(TokenType.EOF):
            d = self.parse_declaration()
            if d is not None:
                stmts.append(d)
        self.consume(TokenType.RIGHT_BRACE, "期望 '}' 结束块")
        return Block(stmts, token=start)

    def parse_expression_statement(self):
        start = self.peek()
        expr = self.parse_expression()
        self.expect_semicolon()
        return ExpressionStatement(expr, token=start)

    # ---------- Pratt 表达式解析 ----------
    def parse_expression(self):
        return self.parse_assignment()

    def parse_assignment(self):
        # 先按优先级解析出左边 (可能是 Identifier 或 Subscript)
        expr = self.parse_or()

        if self.match(TokenType.ASSIGN):
            start = self.peek()  # 等号位置稍微偏后, 但不影响错误定位
            value = self.parse_assignment()
            if isinstance(expr, (Identifier, Subscript)):
                return Assignment(expr, value, token=start)
            raise ParseError.from_token("赋值的左值必须是变量或下标表达式", self.peek())
        return expr

    def parse_or(self):
        left = self.parse_and()
        while self.match(TokenType.OR):
            start = self.peek()
            right = self.parse_and()
            left = LogicalOp('or', left, right, token=start)
        return left

    def parse_and(self):
        left = self.parse_equality()
        while self.match(TokenType.AND):
            start = self.peek()
            right = self.parse_equality()
            left = LogicalOp('and', left, right, token=start)
        return left

    def parse_equality(self):
        left = self.parse_comparison()
        while self.check(TokenType.EQUAL, TokenType.NOT_EQUAL):
            tok = self.advance()
            op = '==' if tok.type == TokenType.EQUAL else '!='
            right = self.parse_comparison()
            left = BinaryOp(op, left, right, token=tok)
        return left

    def parse_comparison(self):
        left = self.parse_term()
        while self.check(TokenType.LESS, TokenType.LESS_EQUAL, TokenType.GREATER, TokenType.GREATER_EQUAL):
            tok = self.advance()
            op = {
                TokenType.LESS: '<',
                TokenType.LESS_EQUAL: '<=',
                TokenType.GREATER: '>',
                TokenType.GREATER_EQUAL: '>=',
            }[tok.type]
            right = self.parse_term()
            left = BinaryOp(op, left, right, token=tok)
        return left

    def parse_term(self):
        left = self.parse_factor()
        while self.check(TokenType.PLUS, TokenType.MINUS):
            tok = self.advance()
            op = '+' if tok.type == TokenType.PLUS else '-'
            right = self.parse_factor()
            left = BinaryOp(op, left, right, token=tok)
        return left

    def parse_factor(self):
        left = self.parse_unary()
        while self.check(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            tok = self.advance()
            op = {TokenType.STAR: '*', TokenType.SLASH: '/', TokenType.PERCENT: '%'}[tok.type]
            right = self.parse_unary()
            left = BinaryOp(op, left, right, token=tok)
        return left

    def parse_unary(self):
        if self.check(TokenType.MINUS, TokenType.NOT):
            tok = self.advance()
            op = '-' if tok.type == TokenType.MINUS else '!'
            operand = self.parse_unary()
            return UnaryOp(op, operand, token=tok)
        return self.parse_call()

    def parse_call(self):
        expr = self.parse_primary()
        while True:
            if self.match(TokenType.LEFT_PAREN):
                expr = self.finish_call(expr)
            elif self.match(TokenType.LEFT_BRACKET):
                # 下标读取: obj[index]
                start = self.peek()
                index = self.parse_expression()
                self.consume(TokenType.RIGHT_BRACKET, "期望 ']' 位于下标之后")
                expr = Subscript(expr, index, token=start)
            else:
                break
        return expr

    def finish_call(self, callee):
        start = self.peek()
        args = []
        if not self.check(TokenType.RIGHT_PAREN):
            args.append(self.parse_expression())
            while self.match(TokenType.COMMA):
                if len(args) >= 255:
                    raise ParseError.from_token("参数数量不能超过 255 个", self.peek())
                args.append(self.parse_expression())
        self.consume(TokenType.RIGHT_PAREN, "期望 ')' 位于参数列表之后")
        return Call(callee, args, token=start)

    def parse_primary(self):
        tok = self.peek()

        if self.match(TokenType.NUMBER):
            return NumberLiteral(tok.value, token=tok)
        if self.match(TokenType.STRING):
            return StringLiteral(tok.value, token=tok)
        if self.match(TokenType.TRUE):
            return BooleanLiteral(True, token=tok)
        if self.match(TokenType.FALSE):
            return BooleanLiteral(False, token=tok)
        if self.match(TokenType.NIL):
            return NilLiteral(token=tok)

        if self.check(TokenType.LEFT_BRACKET):
            return self.parse_array_literal()

        # 解析歧义: '{' 可能是 block 语句, 也可能是 dict 字面量。
        # 在 parse_primary 中遇到 '{' → 一定是 dict 字面量 (语句级 '{' 已在 parse_statement 中处理)。
        # 进一步判断: 如果下一个 token 是 STRING/IDENTIFIER/NUMBER/NIL/TRUE/FALSE/'}'/LEFT_BRACKET/LEFT_BRACE/LEFT_PAREN → 是字典
        if self.check(TokenType.LEFT_BRACE):
            return self.parse_dict_literal()

        if self.match(TokenType.FN):
            # 匿名函数字面量 (lambda)
            start = tok
            self.consume(TokenType.LEFT_PAREN, "期望 '(' 位于 'fn' 之后")
            params = []
            if not self.check(TokenType.RIGHT_PAREN):
                params.append(self.consume(TokenType.IDENTIFIER, "期望参数名").value)
                while self.match(TokenType.COMMA):
                    params.append(self.consume(TokenType.IDENTIFIER, "期望参数名").value)
            self.consume(TokenType.RIGHT_PAREN, "期望 ')' 位于参数列表之后")
            body = self.parse_block_statement()
            return Lambda(params, body, token=start)

        if self.match(TokenType.LEFT_PAREN):
            expr = self.parse_expression()
            self.consume(TokenType.RIGHT_PAREN, "期望 ')'")
            return expr

        if self.match(TokenType.IDENTIFIER):
            return Identifier(tok.value, token=tok)

        raise ParseError.from_token(f"意外的 token: {tok.type.name}", tok)

    def parse_array_literal(self):
        start = self.consume(TokenType.LEFT_BRACKET, "期望 '['")
        elements = []
        if not self.check(TokenType.RIGHT_BRACKET):
            elements.append(self.parse_expression())
            while self.match(TokenType.COMMA):
                if self.check(TokenType.RIGHT_BRACKET):
                    break  # 允许尾随逗号
                elements.append(self.parse_expression())
        self.consume(TokenType.RIGHT_BRACKET, "期望 ']' 位于数组字面量末尾")
        return ArrayLiteral(elements, token=start)

    def parse_dict_literal(self):
        start = self.consume(TokenType.LEFT_BRACE, "期望 '{'")
        entries = []
        if not self.check(TokenType.RIGHT_BRACE):
            key = self.parse_expression()
            self.consume(TokenType.COLON, "期望 ':' 位于字典键之后")
            value = self.parse_expression()
            entries.append((key, value))
            while self.match(TokenType.COMMA):
                if self.check(TokenType.RIGHT_BRACE):
                    break  # 允许尾随逗号
                key = self.parse_expression()
                self.consume(TokenType.COLON, "期望 ':' 位于字典键之后")
                value = self.parse_expression()
                entries.append((key, value))
        self.consume(TokenType.RIGHT_BRACE, "期望 '}' 位于字典字面量末尾")
        return DictLiteral(entries, token=start)
