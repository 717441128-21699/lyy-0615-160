import sys
from ast_nodes import (
    Program, NumberLiteral, StringLiteral, BooleanLiteral, NilLiteral,
    Identifier, Assignment, VariableDeclaration, FunctionDeclaration,
    Lambda, Call, Block, IfStatement, WhileStatement, ForStatement,
    ReturnStatement, PrintStatement, BinaryOp, UnaryOp, LogicalOp,
    ExpressionStatement, ArrayLiteral, DictLiteral, Subscript,
)
from environment import Environment, ReturnException, UNDEFINED
from errors import RuntimeError


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
        self.name = name
        self.params = params
        self.body = body
        self.closure_env = closure_env
        self.is_lambda = is_lambda

    def __repr__(self):
        args = ", ".join(self.params)
        if self.is_lambda:
            return f"<fn ({args}) ... >"
        return f"<fn {self.name}({args})>"


class NativeFunction:
    """内置函数。"""

    def __init__(self, name, arity, impl):
        self.name = name
        self.arity = arity
        self._impl = impl

    def call(self, interpreter, args, node=None):
        if self.arity is not None and len(args) != self.arity:
            msg = f"函数 '{self.name}' 需要 {self.arity} 个参数, 得到 {len(args)}"
            if node is not None:
                raise RuntimeError.from_node(msg, node)
            raise RuntimeError(msg)
        return self._impl(*args)

    def __repr__(self):
        return f"<native fn {self.name}>"


# ------------------------------------------------------------
# 解释器主体
# ------------------------------------------------------------
class Interpreter:
    def __init__(self, output=None):
        self.output = output if output is not None else sys.stdout
        self.globals = Environment(name="<global>")
        self._install_natives()
        self.environment = self.globals

    # ---------- 内置函数 ----------
    def _install_natives(self):
        def _len(x):
            if isinstance(x, str):
                return len(x)
            if isinstance(x, list):
                return len(x)
            if isinstance(x, dict):
                return len(x)
            raise RuntimeError(f"len() 只接受字符串/数组/字典, 不接受 {type(x).__name__}")

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
            if isinstance(x, list):
                return "array"
            if isinstance(x, dict):
                return "dict"
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

        def _push(arr, val):
            if not isinstance(arr, list):
                raise RuntimeError("push() 第一个参数必须是数组")
            arr.append(val)
            return val

        def _pop(arr):
            if not isinstance(arr, list):
                raise RuntimeError("pop() 必须接受数组")
            if len(arr) == 0:
                raise RuntimeError("pop() 不能作用于空数组")
            return arr.pop()

        def _keys(d):
            if not isinstance(d, dict):
                raise RuntimeError("keys() 必须接受字典")
            return list(d.keys())

        def _has(d, key):
            if not isinstance(d, dict):
                raise RuntimeError("has() 第一个参数必须是字典")
            return key in d

        def _del_key(d, key):
            if not isinstance(d, dict):
                raise RuntimeError("del_key() 第一个参数必须是字典")
            if key in d:
                val = d[key]
                del d[key]
                return val
            return None

        def _insert(arr, idx, val):
            if not isinstance(arr, list):
                raise RuntimeError("insert() 第一个参数必须是数组")
            if not isinstance(idx, int):
                raise RuntimeError("insert() 第二个参数必须是整数下标")
            if idx < 0:
                idx += len(arr) + 1  # 允许负索引, 和 Python 行为一致
            arr.insert(idx, val)
            return val

        self.globals.define("len", NativeFunction("len", 1, _len))
        self.globals.define("type", NativeFunction("type", 1, _type))
        self.globals.define("to_str", NativeFunction("to_str", 1, _to_str))
        self.globals.define("parse_int", NativeFunction("parse_int", 1, _parse_int))
        self.globals.define("push", NativeFunction("push", 2, _push))
        self.globals.define("pop", NativeFunction("pop", 1, _pop))
        self.globals.define("insert", NativeFunction("insert", 3, _insert))
        self.globals.define("keys", NativeFunction("keys", 1, _keys))
        self.globals.define("has", NativeFunction("has", 2, _has))
        self.globals.define("del_key", NativeFunction("del_key", 2, _del_key))

    # ---------- 入口 ----------
    def interpret(self, program: Program):
        try:
            for stmt in program.statements:
                self._execute(stmt)
        except ReturnException as e:
            # 顶层 return 视为非法
            raise RuntimeError.from_node("顶层不能使用 return", program) from None
        except RuntimeError:
            raise
        except Exception as e:
            # 把任何其他 Python 异常包成运行时错误 (0:0 位置)
            raise RuntimeError(str(e)) from None

    # ---------- 执行语句 ----------
    def _execute(self, stmt):
        method_name = f"_exec_{type(stmt).__name__}"
        method = getattr(self, method_name, None)
        if method is None:
            raise RuntimeError.from_node(f"未知语句类型: {type(stmt).__name__}", stmt)
        return method(stmt)

    def _exec_ExpressionStatement(self, stmt):
        val = self._evaluate(stmt.expression)
        return val

    def _exec_VariableDeclaration(self, stmt):
        value = UNDEFINED
        if stmt.initializer is not None:
            value = self._evaluate(stmt.initializer)
        self.environment.define(stmt.name, value)

    def _exec_FunctionDeclaration(self, stmt):
        closure = Closure(
            name=stmt.name,
            params=stmt.params,
            body=stmt.body,
            closure_env=self.environment,
            is_lambda=False,
        )
        self.environment.define(stmt.name, closure)

    def _exec_Block(self, stmt):
        previous = self.environment
        self.environment = self.environment.child(name="<block>")
        try:
            for s in stmt.statements:
                self._execute(s)
        finally:
            self.environment = previous

    def _exec_IfStatement(self, stmt):
        cond = self._evaluate(stmt.condition)
        if self._is_truthy(cond):
            self._execute(stmt.then_branch)
        elif stmt.else_branch is not None:
            self._execute(stmt.else_branch)

    def _exec_WhileStatement(self, stmt):
        while self._is_truthy(self._evaluate(stmt.condition)):
            self._execute(stmt.body)

    def _exec_ForStatement(self, stmt):
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
            raise RuntimeError.from_node(f"未知表达式类型: {type(expr).__name__}", expr)
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
        try:
            val = self.environment.lookup(expr.name)
        except Exception as e:
            raise RuntimeError.from_node(str(e), expr) from None
        if val is UNDEFINED:
            raise RuntimeError.from_node(f"变量 '{expr.name}' 在读取前未初始化", expr)
        return val

    def _eval_Assignment(self, expr):
        value = self._evaluate(expr.value)
        target = expr.target

        if isinstance(target, Identifier):
            # 变量赋值: 沿作用域链查找并更新
            try:
                self.environment.assign(target.name, value)
            except Exception as e:
                raise RuntimeError.from_node(str(e), expr) from None
            return value

        if isinstance(target, Subscript):
            # 下标赋值: obj[index] = value
            obj = self._evaluate(target.obj)
            idx = self._evaluate(target.index)

            if isinstance(obj, list):
                if not isinstance(idx, int):
                    raise RuntimeError.from_node("数组下标必须是整数", target)
                if idx < 0:
                    idx += len(obj)
                if idx < 0 or idx >= len(obj):
                    raise RuntimeError.from_node(f"数组下标 {idx} 越界 (长度 {len(obj)})", target)
                obj[idx] = value
                return value

            if isinstance(obj, dict):
                if not isinstance(idx, (str, int, float, bool, type(None))):
                    raise RuntimeError.from_node("字典键必须是可哈希的标量类型", target)
                obj[idx] = value
                return value

            raise RuntimeError.from_node(
                f"下标赋值不能作用于 {type(obj).__name__} 类型", target)

        raise RuntimeError.from_node("无效的赋值左值", expr)

    def _eval_Lambda(self, expr):
        return Closure(
            name="<lambda>",
            params=expr.params,
            body=expr.body,
            closure_env=self.environment,
            is_lambda=True,
        )

    def _eval_ArrayLiteral(self, expr):
        return [self._evaluate(e) for e in expr.elements]

    def _eval_DictLiteral(self, expr):
        result = {}
        for k_expr, v_expr in expr.entries:
            k = self._evaluate(k_expr)
            if not isinstance(k, (str, int, float, bool, type(None))):
                raise RuntimeError.from_node(
                    f"字典键不能是 {type(k).__name__} 类型", k_expr)
            v = self._evaluate(v_expr)
            result[k] = v
        return result

    def _eval_Subscript(self, expr):
        """下标读取: obj[index]"""
        obj = self._evaluate(expr.obj)
        idx = self._evaluate(expr.index)

        if isinstance(obj, list):
            if not isinstance(idx, int):
                raise RuntimeError.from_node("数组下标必须是整数", expr)
            real_idx = idx
            if real_idx < 0:
                real_idx += len(obj)
            if real_idx < 0 or real_idx >= len(obj):
                raise RuntimeError.from_node(
                    f"数组下标 {idx} 越界 (长度 {len(obj)})", expr)
            return obj[real_idx]

        if isinstance(obj, dict):
            if idx in obj:
                return obj[idx]
            return None

        if isinstance(obj, str):
            if not isinstance(idx, int):
                raise RuntimeError.from_node("字符串下标必须是整数", expr)
            real_idx = idx
            if real_idx < 0:
                real_idx += len(obj)
            if real_idx < 0 or real_idx >= len(obj):
                raise RuntimeError.from_node(
                    f"字符串下标 {idx} 越界 (长度 {len(obj)})", expr)
            return obj[real_idx]

        raise RuntimeError.from_node(
            f"不能对 {type(obj).__name__} 类型使用下标访问", expr)

    def _eval_BinaryOp(self, expr):
        left = self._evaluate(expr.left)
        right = self._evaluate(expr.right)
        op = expr.op

        if op == '+':
            # 数字加法 / 字符串拼接 / 数组合并 / 字典合并
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return self._num_result(left + right)
            if isinstance(left, str) or isinstance(right, str):
                return self._stringify(left) + self._stringify(right)
            if isinstance(left, list) and isinstance(right, list):
                return left + right
            if isinstance(left, dict) and isinstance(right, dict):
                merged = dict(left)
                merged.update(right)
                return merged
            raise RuntimeError.from_node(
                f"操作符 '+' 不能用于 {type(left).__name__} 和 {type(right).__name__}", expr)

        if op in ('-', '*', '/', '%'):
            self._assert_nums(left, right, op, expr)
            if op == '-':
                return self._num_result(left - right)
            if op == '*':
                return self._num_result(left * right)
            if op == '/':
                if right == 0:
                    raise RuntimeError.from_node("除零错误", expr)
                return self._num_result(left / right)
            if op == '%':
                if right == 0:
                    raise RuntimeError.from_node("模零错误", expr)
                return self._num_result(left % right)

        if op in ('<', '<=', '>', '>=', '==', '!='):
            cmp = self._compare(left, right, op)
            if cmp is NotImplemented:
                if op == '==':
                    return self._eq(left, right)
                if op == '!=':
                    return not self._eq(left, right)
                raise RuntimeError.from_node(
                    f"操作符 '{op}' 不能用于 {type(left).__name__} 和 {type(right).__name__}", expr)
            return cmp

        raise RuntimeError.from_node(f"未知二元运算符: {op}", expr)

    def _eval_UnaryOp(self, expr):
        operand = self._evaluate(expr.operand)
        if expr.op == '-':
            if not isinstance(operand, (int, float)):
                raise RuntimeError.from_node("一元 '-' 要求数字操作数", expr)
            return -operand
        if expr.op == '!':
            return not self._is_truthy(operand)
        raise RuntimeError.from_node(f"未知一元运算符: {expr.op}", expr)

    def _eval_LogicalOp(self, expr):
        left = self._evaluate(expr.left)
        if expr.op == 'or':
            if self._is_truthy(left):
                return left
        else:
            if not self._is_truthy(left):
                return left
        return self._evaluate(expr.right)

    def _eval_Call(self, expr):
        callee = self._evaluate(expr.callee)
        args = [self._evaluate(a) for a in expr.arguments]

        if isinstance(callee, NativeFunction):
            try:
                return callee.call(self, args, node=expr)
            except RuntimeError:
                raise
            except Exception as e:
                raise RuntimeError.from_node(str(e), expr) from None

        if isinstance(callee, Closure):
            if len(args) != len(callee.params):
                fname = callee.name if callee.name else '<lambda>'
                raise RuntimeError.from_node(
                    f"函数 '{fname}' 需要 {len(callee.params)} 个参数, 得到 {len(args)}", expr)

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

        raise RuntimeError.from_node(
            f"不能调用非函数对象: {self._stringify(callee)}", expr)

    # ---------- 辅助 ----------
    @staticmethod
    def _is_truthy(value) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, (str, list, dict)):
            return len(value) > 0
        return True

    @staticmethod
    def _num_result(v):
        return v

    @staticmethod
    def _assert_nums(a, b, op, node):
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            raise RuntimeError.from_node(
                f"操作符 '{op}' 要求数字操作数", node)

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
        if a is None and b is None:
            return True
        if type(a) is type(b) and isinstance(a, (bool, int, float, str)):
            return a == b
        if isinstance(a, list) and isinstance(b, list):
            return a == b
        if isinstance(a, dict) and isinstance(b, dict):
            return a == b
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
        if isinstance(value, list):
            items = ", ".join(self._stringify(v) for v in value)
            return f"[{items}]"
        if isinstance(value, dict):
            items = []
            for k, v in value.items():
                k_str = self._stringify(k) if isinstance(k, str) else repr(k)
                items.append(f"{k_str}: {self._stringify(v)}")
            return "{" + ", ".join(items) + "}"
        if isinstance(value, Closure):
            return repr(value)
        if isinstance(value, NativeFunction):
            return repr(value)
        return str(value)
