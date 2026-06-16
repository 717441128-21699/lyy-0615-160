
class Node:
    pass


class Program(Node):
    def __init__(self, statements):
        self.statements = statements


class NumberLiteral(Node):
    def __init__(self, value):
        self.value = value


class StringLiteral(Node):
    def __init__(self, value):
        self.value = value


class BooleanLiteral(Node):
    def __init__(self, value):
        self.value = value


class NilLiteral(Node):
    pass


class Identifier(Node):
    def __init__(self, name):
        self.name = name


class Assignment(Node):
    def __init__(self, name, value):
        self.name = name
        self.value = value


class VariableDeclaration(Node):
    def __init__(self, name, initializer=None):
        self.name = name
        self.initializer = initializer


class FunctionDeclaration(Node):
    def __init__(self, name, params, body):
        self.name = name
        self.params = params
        self.body = body


class Lambda(Node):
    def __init__(self, params, body):
        self.params = params
        self.body = body


class Call(Node):
    def __init__(self, callee, arguments):
        self.callee = callee
        self.arguments = arguments


class Block(Node):
    def __init__(self, statements):
        self.statements = statements


class IfStatement(Node):
    def __init__(self, condition, then_branch, else_branch=None):
        self.condition = condition
        self.then_branch = then_branch
        self.else_branch = else_branch


class WhileStatement(Node):
    def __init__(self, condition, body):
        self.condition = condition
        self.body = body


class ForStatement(Node):
    def __init__(self, init, condition, update, body):
        self.init = init
        self.condition = condition
        self.update = update
        self.body = body


class ReturnStatement(Node):
    def __init__(self, value=None):
        self.value = value


class PrintStatement(Node):
    def __init__(self, value):
        self.value = value


class BinaryOp(Node):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right


class UnaryOp(Node):
    def __init__(self, op, operand):
        self.op = op
        self.operand = operand


class LogicalOp(Node):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right


class ExpressionStatement(Node):
    def __init__(self, expression):
        self.expression = expression
