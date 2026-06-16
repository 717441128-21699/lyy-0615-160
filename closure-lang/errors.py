
class ScriptError(Exception):
    """
    脚本语言统一错误基类。
    所有面向用户的错误都应该抛出此类或其子类, 保证:
      - 有清晰的中文/英文描述
      - 有行号、列号
      - 可附带源文件路径
    主入口捕获后按统一格式输出, 不会暴露 Python 堆栈。
    """

    def __init__(self, message: str, line: int, column: int, kind: str = "错误"):
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column
        self.kind = kind
        self.source_path = None   # 主入口可回填文件名

    def format_error(self) -> str:
        """生成一行或多行人类可读的错误信息。"""
        where = ""
        if self.source_path:
            where = f"{self.source_path}:"
        where += f"{self.line}:{self.column}"
        return f"{where}: {self.kind}: {self.message}"

    def __str__(self):
        return self.format_error()


class LexerError(ScriptError):
    def __init__(self, message: str, line: int, column: int):
        super().__init__(message, line, column, kind="词法错误")


class ParseError(ScriptError):
    def __init__(self, message: str, line: int, column: int):
        super().__init__(message, line, column, kind="语法错误")

    @classmethod
    def from_token(cls, message: str, token):
        return cls(message, token.line, token.column)


class RuntimeError(ScriptError):
    def __init__(self, message: str, line: int = 0, column: int = 0):
        super().__init__(message, line, column, kind="运行时错误")

    @classmethod
    def from_node(cls, message: str, node) -> 'RuntimeError':
        """从 AST 节点构造错误。节点如果带 token 属性就取位置, 否则 0:0。"""
        tok = getattr(node, 'token', None)
        if tok is not None:
            return cls(message, tok.line, tok.column)
        return cls(message, 0, 0)
