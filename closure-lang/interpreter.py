import sys
from ast_nodes import (
    Program, NumberLiteral, StringLiteral, BooleanLiteral, NilLiteral,
    Identifier, Assignment, VariableDeclaration, FunctionDeclaration,
    Lambda, Call, Block, IfStatement, WhileStatement, ForStatement,
    ReturnStatement, PrintStatement, BinaryOp, UnaryOp, LogicalOp,
    ExpressionStatement,
)
from environment import Environment, ReturnException, UNDEFINED


class Closure:
    """
    闭包值。

    闭包 = 函数代码(参数+体) + 定义时的环境引用(closure_env)。

    关键机制:
      - 当求值器遇到 `fn name(...) { ... }` 或 `fn(...) { ... }` 时,
        它把 **当前 Environment 引用** 存入 closure_env。
      - 由于 Python 对象是按引用计数的, 即使外层函数已返回并弹出调用栈,
        只要闭包对象仍可达, 整个被捕获的环境链 (closure_env 及其所有祖先)
        都会继续存活 —— 这就是 "环境逃逸" (environment escapes)。
      - 后续调用此闭包时, 新创建的局部作用域的 parent 指向 closure_env,
        而非调用点的当前环境, 从而实现 **词法作用域** (静态作用域)。
    """

    __slots__ = ['name', 'params', 'body', 'closure_env', 'is_lambda']

    def __init__(self, name, params, body, closure_env, is_lambda=False):
        self.name = name              # 调试用, lambda 为 "<lambda>"
        self.params = params          # 参数名列表
        self.body = body              # Block AST
        self.closure_env = closure_env  # 捕获的定义时环境 (核心!)
        self.is_lambda = is_lambda

    def __repr__(self):
        args = ", ".join(self.params)
        if self.is_lambda:
            return f"<fn ({args}) ... >"
        return f"<fn {self.name}({args})>"


class NativeFunction:
    """内置函数 (如 print 的底层已集成到 print 语句, 这里提供 len 等)。"""

    def __init__(self, name, arity, impl):
        self.name = name
        self.arity = arity
        self._impl = impl

    def call(self, interpreter, args):
        if self.arity is not None and len(args) != self.arity:
            raise RuntimeError(
                f"函数 '{self.name}' 需要 {self.arity} 个参数, 得到 {len(args)}")
        return self._impl(*args)

    def __repr__(self):
        return f"<native fn {self.name}>"


class RuntimeError(Exception):
    pass


class Interpreter:
    def __init__(self, output=None):
        self.output = output if output is not None else sys.stdout
        self.globals = Environment(name="<global>")
        self._install_natives()
        self.environment = self.globals

    def _install_natives(self):
        def _len(x):
            if isinstance(x, str):
                return len(x)
            raise RuntimeError("len() 只接受字符串参数")

        def _type(x):
            if x is None:
                return "nil"
            if isinstance(x, bool):
                return "bool"
            if isinstance(x, int):
                return "int"
            if isinstance(x, float):
                return "float"
            if isinstance(x, str):
                return "string"
            if isinstance(x, Closure):
                return "function"
            if isinstance(x, NativeFunction):
                return "native"
            return "<unknown>"

        def _to_str(x):
            return self._stringify(x)

        def _parse_int(s):
            if not isinstance(s, str):
                raise RuntimeError("parse_int() 只接受字符串")
            try:
                return int(s)
            except ValueError:
                return None

        self.globals.define("len", NativeFunction("len", 1, _len))
        self.globals.define("type", NativeFunction("type", 1, _type))
        self.globals.define("to_str", NativeFunction("to_str", 1, _to_str))
        self.globals.define("parse_int", NativeFunction("parse_int", 1, _parse_int))

    # ---------- 入口 ----------
    def interpret(self, program: Program):
        try:
            for stmt in program.statements:
                self._execute(stmt)
        except ReturnException as e:
            # 顶层 return 视为非法
            raise RuntimeError("顶层不能使用 return") from e
        except RuntimeError as e:
            raise

    # ---------- 执行语句 ----------
    def _execute(self, stmt):
        method_name = f"_exec_{type(stmt).__name__}"
        method = getattr(self, method_name, None)
        if method is None:
            raise RuntimeError(f"未知语句类型: {type(stmt).__name__}")
        return method(stmt)

    def _exec_ExpressionStatement(self, stmt):
        self._evaluate(stmt.expression)

    def _exec_VariableDeclaration(self, stmt):
        value = UNDEFINED
        if stmt.initializer is not None:
            value = self._evaluate(stmt.initializer)
        self.environment.define(stmt.name, value)

    def _exec_FunctionDeclaration(self, stmt):
        """
        具名函数声明:
          1. 构造闭包, 其 closure_env 指向 **当前作用域** (定义时环境)。
          2. 将闭包绑定到当前作用域的 stmt.name。
        这里 **捕获的是当前 Environment 的引用**, 所以即使外层函数返回,
        只要闭包还活着, 整个环境链就保持存活。
        """
        closure = Closure(
            name=stmt.name,
            params=stmt.params,
            body=stmt.body,
            closure_env=self.environment,  # 关键: 引用而非拷贝
            is_lambda=False,
        )
        self.environment.define(stmt.name, closure)

    def _exec_Block(self, stmt):
        """
        块语句: 创建子作用域并依次执行其中的声明/语句。
        子作用域的 parent 是进入块之前的 environment, 形成链。
        """
        previous = self.environment
        self.environment = self.environment.child(name="<block>")
        try:
            for s in stmt.statements:
                self._execute(s)
        finally:
            self.environment = previous  # 恢复外层环境

    def _exec_IfStatement(self, stmt):
        cond = self._evaluate(stmt.condition)
        if self._is_truthy(cond):
            self._execute(stmt.then_branch)
        elif stmt.else_branch is not None:
            self._execute(stmt.else_branch)

    def _exec_WhileStatement(self, stmt):
        """
        注意: 这里我们 **不为每次循环体执行创建新作用域**。
        因此如果循环体里用 `let` 声明并创建闭包, 这些闭包会共享同一个
        循环作用域中的变量 —— 即经典 "循环闭包陷阱" 会被如实暴露。
        """
        while self._is_truthy(self._evaluate(stmt.condition)):
            self._execute(stmt.body)

    def _exec_ForStatement(self, stmt):
        """
        同样不做 "每次迭代一个新作用域" 的处理, 以如实暴露经典闭包陷阱。
        如需规避, 用户可在循环体内部显式再包一层块并 let 绑定。
        """
        previous = self.environment
        self.environment = self.environment.child(name="<for>")
        try:
            if stmt.init is not None:
                self._execute(stmt.init)
            while True:
                if stmt.condition is not None:
                    if not self._is_truthy(self._evaluate(stmt.condition)):
                        break
                self._execute(stmt.body)
                if stmt.update is not None:
                    self._evaluate(stmt.update)
        finally:
            self.environment = previous

    def _exec_ReturnStatement(self, stmt):
        value = None
        if stmt.value is not None:
            value = self._evaluate(stmt.value)
        raise ReturnException(value)

    def _exec_PrintStatement(self, stmt):
        value = self._evaluate(stmt.value)
        self.output.write(self._stringify(value) + "\n")
        self.output.flush()

    # ---------- 表达式求值 ----------
    def _evaluate(self, expr):
        method_name = f"_eval_{type(expr).__name__}"
        method = getattr(self, method_name, None)
        if method is None:
            raise RuntimeError(f"未知表达式类型: {type(expr).__name__}")
        return method(expr)

    def _eval_NumberLiteral(self, expr):
        return expr.value

    def _eval_StringLiteral(self, expr):
        return expr.value

    def _eval_BooleanLiteral(self, expr):
        return expr.value

    def _eval_NilLiteral(self, expr):
        return None

    def _eval_Identifier(self, expr):
        """
        变量查找: 沿作用域链向上。
        由 Environment.lookup 递归访问 parent, 实现词法作用域查找。
        """
        val = self.environment.lookup(expr.name)
        if val is UNDEFINED:
            raise RuntimeError(f"变量 '{expr.name}' 在读取前未初始化")
        return val

    def _eval_Assignment(self, expr):
        value = self._evaluate(expr.value)
        # assign 也沿作用域链查找, 找到后就地更新 (支持闭包捕获变量后赋值)
        self.environment.assign(expr.name, value)
        return value

    def _eval_Lambda(self, expr):
        """匿名函数: 捕获当前环境引用作为闭包环境。"""
        return Closure(
            name="<lambda>",
            params=expr.params,
            body=expr.body,
            closure_env=self.environment,  # 关键: 引用而非拷贝
            is_lambda=True,
        )

    def _eval_BinaryOp(self, expr):
        left = self._evaluate(expr.left)
        right = self._evaluate(expr.right)
        op = expr.op

        if op == '+':
            # 数字加法 或 字符串拼接
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return self._num_result(left + right)
            if isinstance(left, str) or isinstance(right, str):
                return self._stringify(left) + self._stringify(right)
            raise RuntimeError(f"操作符 '+' 不能用于 {type(left).__name__} 和 {type(right).__name__}")

        if op in ('-', '*', '/', '%'):
            self._assert_nums(left, right, op)
            if op == '-':
                return self._num_result(left - right)
            if op == '*':
                return self._num_result(left * right)
            if op == '/':
                if right == 0:
                    raise RuntimeError("除零错误")
                return self._num_result(left / right)
            if op == '%':
                if right == 0:
                    raise RuntimeError("模零错误")
                return self._num_result(left % right)

        if op in ('<', '<=', '>', '>=', '==', '!='):
            cmp = self._compare(left, right, op)
            if cmp is NotImplemented:
                # == 和 != 对任意类型都可用 (引用相等/值相等混合)
                if op == '==':
                    return self._eq(left, right)
                if op == '!=':
                    return not self._eq(left, right)
                raise RuntimeError(
                    f"操作符 '{op}' 不能用于 {type(left).__name__} 和 {type(right).__name__}")
            return cmp

        raise RuntimeError(f"未知二元运算符: {op}")

    def _eval_UnaryOp(self, expr):
        operand = self._evaluate(expr.operand)
        if expr.op == '-':
            if not isinstance(operand, (int, float)):
                raise RuntimeError("一元 '-' 要求数字操作数")
            return -operand
        if expr.op == '!':
            return not self._is_truthy(operand)
        raise RuntimeError(f"未知一元运算符: {expr.op}")

    def _eval_LogicalOp(self, expr):
        left = self._evaluate(expr.left)
        if expr.op == 'or':
            if self._is_truthy(left):
                return left
        else:  # and
            if not self._is_truthy(left):
                return left
        return self._evaluate(expr.right)

    def _eval_Call(self, expr):
        """
        函数调用。

        关键点 (闭包调用):
          1. 先对 callee 求值得到闭包 (或原生函数)。
          2. 对闭包来说: 创建新的局部作用域, **其 parent 不是调用点当前环境,
             而是闭包捕获的 closure_env** —— 这正是词法作用域的本质!
          3. 所有参数在调用点环境中求值, 然后绑定到新作用域中。
        """
        callee = self._evaluate(expr.callee)
        args = [self._evaluate(a) for a in expr.arguments]

        if isinstance(callee, NativeFunction):
            return callee.call(self, args)

        if isinstance(callee, Closure):
            if len(args) != len(callee.params):
                raise RuntimeError(
                    f"函数 '{callee.name if callee.name else '<lambda>'}' "
                    f"需要 {len(callee.params)} 个参数, 得到 {len(args)}")

            # 创建局部作用域, parent = 闭包定义时的环境 (而不是调用点环境!)
            # 这保证了: 即使外层函数早已返回 (即调用栈上的环境已销毁),
            # 只要 closure_env 被闭包持有, 查找链依然完整 —— 环境逃逸。
            previous = self.environment
            self.environment = Environment(
                parent=callee.closure_env,
                name=f"<fn:{callee.name}>",
            )
            try:
                for name, value in zip(callee.params, args):
                    self.environment.define(name, value)
                self._execute(callee.body)
                return None
            except ReturnException as ret:
                return ret.value
            finally:
                self.environment = previous

        raise RuntimeError(f"不能调用非函数对象: {self._stringify(callee)}")

    # ---------- 辅助 ----------
    @staticmethod
    def _is_truthy(value) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return len(value) > 0
        return True

    @staticmethod
    def _num_result(v):
        if isinstance(v, float) and v.is_integer():
            # 保留 Python 的 int/float 区分, 但避免 3.0 这种无意义的 float
            pass
        return v

    @staticmethod
    def _assert_nums(a, b, op):
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            raise RuntimeError(f"操作符 '{op}' 要求数字操作数")

    @staticmethod
    def _compare(a, b, op):
        # 数字比较
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            if op == '<':  return a < b
            if op == '<=': return a <= b
            if op == '>':  return a > b
            if op == '>=': return a >= b
            if op == '==': return a == b
            if op == '!=': return a != b
        # 字符串比较 (字典序)
        if isinstance(a, str) and isinstance(b, str):
            if op == '<':  return a < b
            if op == '<=': return a <= b
            if op == '>':  return a > b
            if op == '>=': return a >= b
            if op == '==': return a == b
            if op == '!=': return a != b
        return NotImplemented

    @staticmethod
    def _eq(a, b) -> bool:
        # nil 与 nil 相等
        if a is None and b is None:
            return True
        # bool / number / string 按值比较
        if type(a) is type(b) and isinstance(a, (bool, int, float, str)):
            return a == b
        # 函数比较按引用 (闭包 / 原生函数)
        return a is b

    def _stringify(self, value) -> str:
        if value is None:
            return "nil"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, float):
            if value.is_integer():
                return str(int(value))
            return repr(value)
        if isinstance(value, str):
            return value
        if isinstance(value, Closure):
            return repr(value)
        if isinstance(value, NativeFunction):
            return repr(value)
        return str(value)
