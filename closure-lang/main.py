import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lexer import Lexer
from parser import Parser
from interpreter import Interpreter
from errors import ScriptError, LexerError, ParseError, RuntimeError
from ast_nodes import ExpressionStatement


def run_source(source: str, interpreter: Interpreter = None,
               source_path: str = None, current_dir: str = None,
               script_args=None):
    """
    运行一段源代码，所有 ScriptError 异常会带上 source_path 后抛出。
    返回 (interpreter, last_value, had_value) 三元组。
    """
    if interpreter is None:
        interpreter = Interpreter(script_args=script_args,
                                  current_dir=current_dir)
    if current_dir is not None:
        interpreter.current_dir = current_dir
    try:
        tokens = Lexer(source, source_path=source_path).tokenize()
        program = Parser(tokens, source_path=source_path).parse()
        last_value, had_value = interpreter.interpret(program)
    except ScriptError as e:
        if source_path and e.source_path is None:
            e.source_path = source_path
        raise
    return interpreter, last_value, had_value


def _print_error(err: ScriptError):
    """统一格式化输出错误信息 (不含 Python 堆栈)。"""
    print(err.format_error(), file=sys.stderr)


def run_file(path: str, script_args=None) -> int:
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
    abs_path = os.path.abspath(path)
    current_dir = os.path.dirname(abs_path)
    try:
        run_source(source,
                   source_path=abs_path,
                   current_dir=current_dir,
                   script_args=script_args)
        return 0
    except ScriptError as e:
        _print_error(e)
        return 1


def run_repl():
    """
    交互式 REPL:
      - 单行表达式自动回显结果值（只执行一次，不重复执行有副作用的操作）
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
                # interpret() 执行所有语句, 返回最后一条表达式语句的值
                last_value, had_value = interpreter.interpret(program)
                if had_value:
                    print(interpreter._stringify(last_value))
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
                return True
            stack.pop()
        i += 1
    if in_str is not None:
        return False
    return len(stack) == 0


def _looks_definitely_incomplete(src: str) -> bool:
    """启发式: 如果结尾是开启符号/逗号/反斜杠/运算符, 就继续收集。"""
    stripped = src.rstrip()
    if not stripped:
        return False
    ends = stripped[-1]
    return ends in ('{', '(', '[', ',', '\\') \
        or ends in ('+', '-', '*', '/', '%', '=', '<', '>', '!')


BANNER = r"""
   _____ _                 _                _                      
  / ____| |               | |              | |                     
 | |    | | ___   ___  ___| |_ _   _ _ __  | |     __ _ _ __   __ _ 
 | |    | |/ _ \ / _ \/ __| __| | | | '__| | |    / _` | '_ \ / _` |
 | |____| | (_) | (_) \__ \ |_| |_| | |    | |___| (_| | | | | (_| |
  \_____|_|\___/ \___/|___/\__|\__,_|_|    |______\__,_|_| |_|\__, |
                                                               __/ |
                                                              |___/ 
  支持 词法作用域 · 闭包捕获 · 环境逃逸 · Pratt 解析 · 数组 · 字典 · 模块
  用法: python main.py <script.scl> [args...]    # 执行脚本(可跟参数)
        python main.py                           # 进入 REPL
        python main.py --help                    # 查看帮助
  脚本参数通过全局变量 ARGS (数组) 访问。
"""


def main():
    argv = sys.argv[1:]
    if not argv:
        print(BANNER)
        run_repl()
        return

    if argv[0] in ("--help", "-h"):
        print(BANNER)
        sys.exit(0)

    # python main.py script.scl arg1 arg2 ...
    script_path = argv[0]
    script_args = argv[1:]
    code = run_file(script_path, script_args=script_args)
    sys.exit(code)


if __name__ == "__main__":
    main()
