
class Node:
    """所有 AST 节点的基类。
    每个节点至少带一个 `token` 字段, 表示该节点在源码中的起始位置,
    用于运行时错误定位。
    """
    pass


class Program(Node):
    def __init__(self, statements, token=None):
        self.statements = statements
        self.token = token


class NumberLiteral(Node):
    def __init__(self, value, token):
        self.value = value
        self.token = token


class StringLiteral(Node):
    def __init__(self, value, token):
        self.value = value
        self.token = token


class BooleanLiteral(Node):
    def __init__(self, value, token):
        self.value = value
        self.token = token


class NilLiteral(Node):
    def __init__(self, token):
        self.token = token


class Identifier(Node):
    def __init__(self, name, token):
        self.name = name
        self.token = token


class Assignment(Node):
    """赋值表达式。target 可以是 Identifier 或 Subscript。"""
    def __init__(self, target, value, token):
        self.target = target      # Identifier | Subscript
        self.value = value
        self.token = token


class VariableDeclaration(Node):
    def __init__(self, name, initializer, token):
        self.name = name
        self.initializer = initializer
        self.token = token


class FunctionDeclaration(Node):
    def __init__(self, name, params, body, token):
        self.name = name
        self.params = params
        self.body = body
        self.token = token


class Lambda(Node):
    def __init__(self, params, body, token):
        self.params = params
        self.body = body
        self.token = token


class Call(Node):
    def __init__(self, callee, arguments, token):
        self.callee = callee
        self.arguments = arguments
        self.token = token


class Block(Node):
    def __init__(self, statements, token):
        self.statements = statements
        self.token = token


class IfStatement(Node):
    def __init__(self, condition, then_branch, else_branch, token):
        self.condition = condition
        self.then_branch = then_branch
        self.else_branch = else_branch
        self.token = token


class WhileStatement(Node):
    def __init__(self, condition, body, token):
        self.condition = condition
        self.body = body
        self.token = token


class ForStatement(Node):
    def __init__(self, init, condition, update, body, token):
        self.init = init
        self.condition = condition
        self.update = update
        self.body = body
        self.token = token


class ReturnStatement(Node):
    def __init__(self, value, token):
        self.value = value
        self.token = token


class PrintStatement(Node):
    def __init__(self, value, token):
        self.value = value
        self.token = token


class BinaryOp(Node):
    def __init__(self, op, left, right, token):
        self.op = op
        self.left = left
        self.right = right
        self.token = token


class UnaryOp(Node):
    def __init__(self, op, operand, token):
        self.op = op
        self.operand = operand
        self.token = token


class LogicalOp(Node):
    def __init__(self, op, left, right, token):
        self.op = op
        self.left = left
        self.right = right
        self.token = token


class ExpressionStatement(Node):
    def __init__(self, expression, token):
        self.expression = expression
        self.token = token


class ArrayLiteral(Node):
    """数组字面量: [expr, expr, ...]"""
    def __init__(self, elements, token):
        self.elements = elements
        self.token = token


class DictLiteral(Node):
    """字典字面量: {key: value, key: value, ...}"""
    def __init__(self, entries, token):
        self.entries = entries   # list[tuple[expr, expr]]
        self.token = token


class Subscript(Node):
    """下标读取/写入: obj[index]"""
    def __init__(self, obj, index, token):
        self.obj = obj
        self.index = index
        self.token = token


class ImportStatement(Node):
    """模块导入: import "path/to/file.scl" """
    def __init__(self, path, token):
        self.path = path    # 字符串
        self.token = token
