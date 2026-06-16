import sys
import os

# 允许从任何目录运行, 保证包导入路径可用
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lexer import Lexer, LexerError
from parser import Parser, ParseError
from interpreter import Interpreter, RuntimeError


def run_source(source: str, interpreter: Interpreter = None) -> Interpreter:
    """运行一段源代码, 若未提供 interpreter 则创建一个全新的 (带全局内置函数)。"""
    if interpreter is None:
        interpreter = Interpreter()
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    interpreter.interpret(program)
    return interpreter


def run_file(path: str) -> int:
    """执行一个脚本文件。"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            source = f.read()
    except FileNotFoundError:
        print(f"错误: 文件未找到: {path}", file=sys.stderr)
        return 1
    try:
        run_source(source)
    except (LexerError, ParseError, RuntimeError) as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


def run_repl():
    """交互式 REPL。支持多行输入: 以空行结束一条语句块。"""
    print("ClosureLang REPL (输入 .exit 退出, 多行用 ; 或空行结束)")
    print("=" * 56)
    interpreter = Interpreter()
    buf = ""
    prompt = ">>> "
    while True:
        try:
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if line.strip() == ".exit":
            return

        buf += line + "\n"

        # 如果当前缓冲在语法上看起来 "完整", 就尝试执行
        if not _looks_incomplete(buf):
            try:
                tokens = Lexer(buf).tokenize()
                program = Parser(tokens).parse()
            except (LexerError, ParseError) as e:
                # 可能只是还没输完: 如果结尾是 { ( 或逗号, 继续输入
                if _could_continue(buf, line):
                    prompt = "... "
                    continue
                print(str(e), file=sys.stderr)
                buf = ""
                prompt = ">>> "
                continue

            try:
                # 如果最后是单个表达式, 额外打印其值
                last = None
                if program.statements:
                    import ast_nodes as _an
                    last_stmt = program.statements[-1]
                    if isinstance(last_stmt, _an.ExpressionStatement):
                        last = last_stmt.expression
                interpreter.interpret(program)
                if last is not None:
                    # 再次对同一表达式求值用于打印 (副作用会重复, 但 REPL 可以接受)
                    try:
                        tokens2 = Lexer(buf).tokenize()
                        prog2 = Parser(tokens2).parse()
                        import ast_nodes as _an2
                        if prog2.statements and isinstance(
                            prog2.statements[-1], _an2.ExpressionStatement
                        ):
                            # 通过临时 "print _" 机制实现: 简单直接用内部 _eval 不方便, 这里用 print
                            pass
                    except Exception:
                        pass
            except (LexerError, ParseError, RuntimeError) as e:
                print(str(e), file=sys.stderr)
            buf = ""
            prompt = ">>> "
        else:
            prompt = "... "


def _looks_incomplete(src: str) -> bool:
    stripped = src.rstrip()
    if not stripped:
        return False
    # 结尾是 { ( 等开启符号, 说明还没写完
    openers = ('{', '(', '[', ',')
    closer_map = {'{': 0, '(': 0, '[': 0}
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
        if ch == '{': closer_map['{'] += 1
        elif ch == '}': closer_map['{'] -= 1
        elif ch == '(': closer_map['('] += 1
        elif ch == ')': closer_map['('] -= 1
        elif ch == '[': closer_map['['] += 1
        elif ch == ']': closer_map['['] -= 1
        i += 1
    if in_str is not None:
        return True
    return any(v > 0 for v in closer_map.values())


def _could_continue(buf: str, last_line: str) -> bool:
    return _looks_incomplete(buf) or last_line.rstrip().endswith(('{', '(', ',', '\\'))


BANNER = r"""
   _____ _                 _                _                      
  / ____| |               | |              | |                     
 | |    | | ___   ___  ___| |_ _   _ _ __  | |     __ _ _ __   __ _ 
 | |    | |/ _ \ / _ \/ __| __| | | | '__| | |    / _` | '_ \ / _` |
 | |____| | (_) | (_) \__ \ |_| |_| | |    | |___| (_| | | | | (_| |
  \_____|_|\___/ \___/|___/\__|\__,_|_|    |______\__,_|_| |_|\__, |
                                                               __/ |
                                                              |___/ 
  支持 词法作用域 · 闭包捕获 · 环境逃逸 · Pratt 解析
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
