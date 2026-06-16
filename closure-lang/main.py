import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lexer import Lexer
from parser import Parser
from interpreter import Interpreter
from errors import ScriptError, LexerError, ParseError, RuntimeError
from ast_nodes import ExpressionStatement


def run_source(source: str, interpreter: Interpreter = None, source_path: str = None) -> Interpreter:
    """运行一段源代码。所有 ScriptError 异常会带上 source_path 后抛出。"""
    if interpreter is None:
        interpreter = Interpreter()
    try:
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        interpreter.interpret(program)
    except ScriptError as e:
        if source_path and e.source_path is None:
            e.source_path = source_path
        raise
    return interpreter


def _print_error(err: ScriptError):
    """统一格式化输出错误信息 (不含 Python 堆栈)。"""
    print(err.format_error(), file=sys.stderr)


def run_file(path: str) -> int:
    """执行一个脚本文件，发生错误只打印脚本错误信息，返回非零退出码。"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            source = f.read()
    except FileNotFoundError:
        print(f"错误: 文件未找到: {path}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"错误: 无法读取文件: {e}", file=sys.stderr)
        return 1
    try:
        run_source(source, source_path=path)
        return 0
    except ScriptError as e:
        _print_error(e)
        return 1


def run_repl():
    """
    交互式 REPL:
      - 单行表达式自动回显结果值
      - 多行结构 (fn / if / while / for / { ... }) 会持续收集输入
        直到语法结构完整、括号配对后才执行
      - 所有错误只显示脚本错误格式, 不影响下一条输入
    """
    print("ClosureLang REPL (输入 .exit 退出)")
    print("=" * 56)
    interpreter = Interpreter()
    buf = ""

    while True:
        try:
            prompt = ">>> " if not buf else "... "
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            return

        stripped = line.strip()
        if stripped == ".exit":
            return
        if not stripped and not buf:
            continue

        buf += line + "\n"

        # 如果缓冲语法上完整 (括号配对), 就尝试解析执行
        if _is_complete(buf):
            try:
                tokens = Lexer(buf).tokenize()
                program = Parser(tokens).parse()
            except ScriptError as e:
                # 可能只是还没输完: 如果缓冲明显不完整, 继续收集
                if _looks_definitely_incomplete(buf):
                    continue
                _print_error(e)
                buf = ""
                continue

            try:
                # 判断最后一条语句是否是表达式语句 → 自动回显值
                last_expr_val = None
                last_is_expr = False
                if program.statements:
                    last_stmt = program.statements[-1]
                    if isinstance(last_stmt, ExpressionStatement):
                        last_is_expr = True

                interpreter.interpret(program)

                if last_is_expr:
                    # 单独对最后一个表达式求值以回显 (副作用会再次执行, 可接受)
                    try:
                        tokens2 = Lexer(buf).tokenize()
                        prog2 = Parser(tokens2).parse()
                        if prog2.statements:
                            ls = prog2.statements[-1]
                            if isinstance(ls, ExpressionStatement):
                                val = interpreter._evaluate(ls.expression)
                                print(interpreter._stringify(val))
                    except Exception:
                        pass
            except ScriptError as e:
                _print_error(e)
            buf = ""


def _is_complete(src: str) -> bool:
    """简单的括号配对检测, 判断输入是否完整。"""
    open_map = {'(': ')', '[': ']', '{': '}'}
    close_map = {v: k for k, v in open_map.items()}
    stack = []
    in_str = None
    i = 0
    while i < len(src):
        ch = src[i]
        if in_str:
            if ch == '\\' and i + 1 < len(src):
                i += 2
                continue
            if ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in ('"', "'"):
            in_str = ch
            i += 1
            continue
        if ch in open_map:
            stack.append(ch)
        elif ch in close_map:
            if not stack or stack[-1] != close_map[ch]:
                # 不匹配就认为无效, 返回 True 让解析器报错
                return True
            stack.pop()
        i += 1
    if in_str is not None:
        return False
    return len(stack) == 0


def _looks_definitely_incomplete(src: str) -> bool:
    """启发式: 如果结尾是开启符号/逗号/反斜杠, 就继续收集。"""
    stripped = src.rstrip()
    if not stripped:
        return False
    ends = stripped[-1]
    return ends in ('{', '(', '[', ',', '\\') or ends in ('+', '-', '*', '/', '%', '=', '<', '>', '!')


BANNER = r"""
   _____ _                 _                _                      
  / ____| |               | |              | |                     
 | |    | | ___   ___  ___| |_ _   _ _ __  | |     __ _ _ __   __ _ 
 | |    | |/ _ \ / _ \/ __| __| | | | '__| | |    / _` | '_ \ / _` |
 | |____| | (_) | (_) \__ \ |_| |_| | |    | |___| (_| | | | | (_| |
  \_____|_|\___/ \___/|___/\__|\__,_|_|    |______\__,_|_| |_|\__, |
                                                               __/ |
                                                              |___/ 
  支持 词法作用域 · 闭包捕获 · 环境逃逸 · Pratt 解析 · 数组 · 字典
  用法: python main.py <script.scl>      # 执行脚本
        python main.py                   # 进入 REPL
"""


def main():
    if len(sys.argv) > 2:
        print("用法: python main.py [script.scl]")
        sys.exit(64)
    if len(sys.argv) == 2:
        path = sys.argv[1]
        if path == "--help" or path == "-h":
            print(BANNER)
            sys.exit(0)
        code = run_file(path)
        sys.exit(code)
    else:
        print(BANNER)
        run_repl()


if __name__ == "__main__":
    main()
