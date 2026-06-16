class _Undefined:
    def __repr__(self):
        return "<undefined>"


UNDEFINED = _Undefined()


class Environment:
    """
    链式作用域环境。
    每个环境持有一个字典 {变量名: 值} 和一个指向父环境的引用 parent。
    变量查找从当前环境开始, 沿 parent 链逐级向上回溯, 直到全局作用域。

    闭包的关键: 当函数字面量被求值时, 它捕获当前 Environment 引用作为 "闭包环境"。
    因为 Python 中对象按引用计数管理, 即使外层函数已返回, 只要闭包对象还存活,
    整个被捕获的 Environment 链就不会被 GC 回收 —— 即 "环境逃逸"。
    """

    __slots__ = ['values', 'parent', '_name']

    def __init__(self, parent=None, name="<scope>"):
        self.values = {}     # name -> value
        self.parent = parent  # 向上的作用域链
        self._name = name

    # ---------- 定义 / 赋值 / 查找 ----------
    def define(self, name: str, value):
        """在当前作用域定义 (或覆盖) 一个变量 (let 绑定)。"""
        self.values[name] = value

    def assign(self, name: str, value):
        """
        为变量赋值 (走作用域链查找)。
        如果当前作用域没有, 就到父作用域找; 沿途找到后就地更新。
        找不到则抛出 RuntimeError。
        """
        if name in self.values:
            self.values[name] = value
            return
        if self.parent is not None:
            self.parent.assign(name, value)
            return
        raise RuntimeError(f"未定义的变量: '{name}'")

    def lookup(self, name: str):
        """
        沿作用域链查找变量值。
        这是 "词法作用域 / 静态作用域" 的关键 —— 查找路径完全由
        代码结构 (函数在哪里定义) 决定, 而非调用位置。
        """
        if name in self.values:
            return self.values[name]
        if self.parent is not None:
            return self.parent.lookup(name)
        raise RuntimeError(f"未定义的变量: '{name}'")

    def has(self, name: str) -> bool:
        """在整个作用域链上检查变量是否存在。"""
        if name in self.values:
            return True
        if self.parent is not None:
            return self.parent.has(name)
        return False

    def assign_at(self, distance: int, name: str, value):
        """沿作用域链向上跳 distance 步, 在对应环境中赋值 (供解析器静态分析预留)。"""
        env = self._ancestor(distance)
        env.values[name] = value

    def lookup_at(self, distance: int, name: str):
        """沿作用域链向上跳 distance 步取值。"""
        return self._ancestor(distance).values[name]

    def _ancestor(self, distance: int) -> 'Environment':
        env = self
        for _ in range(distance):
            env = env.parent
        return env

    def child(self, name="<scope>") -> 'Environment':
        """创建一个子作用域, parent 指向自身。"""
        return Environment(parent=self, name=name)

    def __repr__(self):
        chain = []
        e = self
        while e is not None:
            chain.append(f"{e._name}{{ {', '.join(e.values.keys())} }}")
            e = e.parent
        return " -> ".join(chain)


class CallFrame:
    """用于解释器控制流: return 时通过异常抛出值。"""
    __slots__ = ['value']

    def __init__(self, value):
        self.value = value


class ReturnException(Exception):
    """
    用异常机制从深层函数体中跳出并携带返回值。
    由 Call 表达式捕获。
    """

    def __init__(self, value):
        super().__init__()
        self.value = value
