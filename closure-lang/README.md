# ClosureLang —— 解释器设计文档

本项目用 ~1300 行 Python 实现了一门小型脚本语言 ClosureLang，重点演示：
- **词法作用域**：变量查找完全由代码结构决定
- **闭包捕获**：闭包按**引用**捕获定义时的环境（非拷贝）
- **环境逃逸**：外层函数返回后，被闭包持有的环境仍存活
- **Pratt 解析**：运算符优先级由 Pratt 解析器优雅处理
- **循环闭包陷阱**：**如实暴露**经典共享引用问题，并演示规避方法

---

## 目录结构

```
closure-lang/
├── __init__.py
├── token_types.py      # Token 类型 + 关键字表
├── lexer.py            # 词法分析器 (扫描字符 → Token 流)
├── ast_nodes.py        # 抽象语法树节点定义
├── parser.py           # Pratt 解析器 (Token 流 → AST)
├── environment.py      # 链式作用域 Environment (闭包的核心数据结构)
├── interpreter.py      # 树遍历求值器 (AST → 值)
├── main.py             # 入口: REPL + 执行脚本
└── examples/
    ├── 01_basics.scl           # 变量/算术/字符串/内置函数
    ├── 02_control_flow.scl     # if / while / for
    ├── 03_functions.scl        # 函数/递归/匿名函数/高阶函数
    ├── 04_closures.scl         # 闭包基础 + 环境逃逸演示
    ├── 05_closure_trap.scl     # 循环闭包陷阱 (暴露问题)
    ├── 06_closure_trap_fixed.scl  # 陷阱规避方案 (IIFE)
    └── 07_scope_chain.scl      # 作用域链/遮蔽/闭包修改外层
```

---

## 1. 词法分析器 ([lexer.py](file:///d:/trae-bz/TraeProjects/160/closure-lang/lexer.py))

职责：把源代码字符串扫描成 `Token` 序列。

- **字面量**：整数/浮点数 (自动识别是否含小数点)、双/单引号字符串（支持 `\n` `\t` `\\` `\"` `\'` `\0` 转义）
- **标识符**：字母/数字/下划线，和关键字表 `KEYWORDS` 匹配出 `let/fn/if/else/while/for/return/true/false/nil/print/and/or`
- **符号**：单字符和双字符运算符（`== != <= >= // /* */` 注释跳过）
- **错误定位**：每个 Token 携带 `line` 和 `column`，错误信息能精确定位

---

## 2. Pratt 解析器 ([parser.py](file:///d:/trae-bz/TraeProjects/160/closure-lang/parser.py))

Pratt 解析的核心思想是**给每个运算符赋予绑定优先级（binding power）**，递归下降时按优先级自动"吸收"右操作数。本实现采用经典的分层递归下降写法（等效于 Pratt）：

```
parse_expression
  └─ parse_assignment (右结合 =)
      └─ parse_or (左结合)                     优先级 10
          └─ parse_and (左结合)                 优先级 20
              └─ parse_equality (== !=)         优先级 30
                  └─ parse_comparison (< <= > >=)  优先级 40
                      └─ parse_term (+ -)       优先级 50
                          └─ parse_factor (* / %)  优先级 60
                              └─ parse_unary (- !)  优先级 70
                                  └─ parse_call (函数调用)  优先级 80
                                      └─ parse_primary (字面量/分组/标识符/lambda)
```

每一层在消费完左操作数后，循环检查"下一个运算符是否优先级 ≥ 当前层"：如果是就继续吸收右操作数，否则回退给上层处理。

### 主要语法（以 BNF 说明）

```
program       = declaration*
declaration   = fnDecl | letDecl | statement
fnDecl        = "fn" IDENTIFIER "(" params? ")" block
letDecl       = "let" IDENTIFIER ("=" expression)? ";"?
statement     = ifStmt | whileStmt | forStmt | returnStmt
              | printStmt | block | exprStmt
ifStmt        = "if" "(" expression ")" statement ("else" statement)?
whileStmt     = "while" "(" expression ")" statement
forStmt       = "for" "(" (letDecl | exprStmt)? ";" expression? ";" expression? ")" statement
block         = "{" declaration* "}"
expression    = assignment | logic | binary | unary | call | primary
```

---

## 3. 链式作用域与闭包（核心）

### 3.1 Environment 数据结构 ([environment.py](file:///d:/trae-bz/TraeProjects/160/closure-lang/environment.py))

```python
class Environment:
    __slots__ = ['values', 'parent', '_name']

    def __init__(self, parent=None, name="<scope>"):
        self.values = {}     # dict[str, value] — 当前作用域的变量表
        self.parent = parent # 指向外层作用域的引用 (None 表示全局)
```

**作用域链就是通过 `parent` 指针串起来的单链表**。变量查找/赋值都从当前环境开始，沿链而上：

```python
def lookup(self, name):
    if name in self.values:
        return self.values[name]
    if self.parent is not None:
        return self.parent.lookup(name)  # <-- 递归向上
    raise RuntimeError(f"未定义的变量: '{name}'")
```

### 3.2 作用域创建时机

| 代码结构 | 何时新建 Environment | 说明 |
|---|---|---|
| 程序启动 | 1 个全局环境 `Environment(name="<global>")` | 内置函数安装在这里 |
| 进入块 `{ ... }` | `env.child(name="<block>")` | 恢复时 `self.environment = previous` |
| 进入 `for (init; cond; upd) { body }` | 包一层 `<for>` 作用域，`init` 声明在里面 | 循环体每次迭代**不**新建作用域（故意暴露陷阱） |
| 调用闭包 | `Environment(parent=callee.closure_env, name="<fn:...>")` | **关键：parent 指向闭包捕获的环境，而不是调用点环境！** |

### 3.3 闭包如何捕获环境并正确存活？

这是整个语言最核心的设计。请参考 [interpreter.py](file:///d:/trae-bz/TraeProjects/160/closure-lang/interpreter.py) 中的 `Closure` 类与两处创建闭包的代码。

#### 第一步：函数定义 → 捕获当前环境引用

遇到 `fn name(params) { body }` 或匿名 `fn(params) { body }` 时：

```python
# _exec_FunctionDeclaration / _eval_Lambda
closure = Closure(
    name=stmt.name,
    params=stmt.params,
    body=stmt.body,
    closure_env=self.environment,  # ← 注意！是 self.environment 的引用
    is_lambda=...
)
```

- **不做值拷贝**，只把当前 `self.environment`（一个 `Environment` 对象引用）塞进 `Closure`
- Python 中对象按引用计数管理。只要闭包对象还活着，`closure_env` 引用的环境以及它的所有祖先环境（通过 `parent` 链）都**不会被垃圾回收** → 这就是 **环境逃逸 (Environment Escape)**。

#### 第二步：闭包被调用 → 用 closure_env 作为父作用域

```python
# _eval_Call  —— 调用 Closure 时
previous = self.environment
self.environment = Environment(
    parent=callee.closure_env,    # ← 不是 self.environment！而是闭包捕获的环境！
    name=f"<fn:{callee.name}>"
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
```

**这一行 `parent=callee.closure_env` 是词法作用域的本质**：
- 函数在哪里**定义**，就从哪里开始往上找变量
- 而不是从函数在哪里**调用**往上找
- 因此即使外层函数早已返回（调用栈上的帧已销毁），只要 `closure_env` 被闭包持有，查找链依然完整

### 3.4 图示：环境逃逸

```
执行 let c = make_counter() 时的环境变化：

  全局 env                     (parent=None, values={make_counter, c, ...})
    ↑
  make_counter 的 env          (parent=全局, values={count=0})  ← 闭包捕获的就是这个！
    ↑ (c.closure_env 引用它)
  闭包 c 对象

→ make_counter() 返回, 调用帧从解释器栈上弹出
→ 但 make_counter 的 env 仍被 c.closure_env 引用 → 不被 GC → count=0 保留

后续每次 c() 调用:
  新的局部 env (parent=make_counter 的 env) → 查找 count 时命中, 读写都走同一个 cell
→ 闭包 c 把 "私有状态" count 牢牢关在自己的环境里, 外部无法直接访问
```

---

## 4. 循环闭包陷阱 ([05_closure_trap.scl](file:///d:/trae-bz/TraeProjects/160/closure-lang/examples/05_closure_trap.scl))

### 4.1 陷阱代码

```js
let f0 = nil; let f1 = nil; let f2 = nil;

for (let i = 0; i < 3; i = i + 1) {
    let current = fn() { return i; };   // 引用捕获
    if (i == 0) f0 = current;
    if (i == 1) f1 = current;
    if (i == 2) f2 = current;
}

// f0(), f1(), f2() 全部返回 3！而不是 0, 1, 2！
```

### 4.2 为什么？引用捕获 + 不按迭代建新作用域

本语言（有意）不做 ES6 `let` in `for` 那样的 "每次迭代一个新绑定" 语义，因此：

1. `<for>` 作用域里**只有一个 `i` cell**
2. 每次迭代创建的闭包都**共享同一个 `i` 引用**（都指向同一份 `Environment.values["i"]`）
3. 循环结束 `i` 的最终值是 3
4. 之后调用任何一个 `fX()`，读到的都是同一个 `i == 3`

示意图：

```
<for> env (parent=全局)
  └─ values: { i = 3 }         ← 只有一份！
          ↑  ↑  ↑
         /   |   \
        f0   f1   f2            ← 三个闭包的 closure_env 都指向这同一个 <for> env
```

这**不是 bug**，是**如实暴露闭包的引用捕获语义**。JavaScript（`var` 时代）、Python、Lua 等大量语言都有这个经典坑。理解它才能真正理解闭包。

### 4.3 规避方案：IIFE 按值包装 ([06_closure_trap_fixed.scl](file:///d:/trae-bz/TraeProjects/160/closure-lang/examples/06_closure_trap_fixed.scl))

```js
for (let i = 0; i < 3; i = i + 1) {
    let wrapped = fn(captured) {     // ← IIFE 立即调用
        return fn() { return captured; };
    }(i);                            // ← 传入 i 的当前值
    // 把 wrapped 存起来
}
```

原理：
- 每次迭代 **立刻调用** 一次 `fn(captured){...}`，产生一个**全新的 Environment**（函数调用总是新建 env）
- 新环境的 `captured` 被绑定到 `i` 的**当前值**（整数是不可变值，相当于按值拷贝）
- 返回的内部闭包捕获的是这个 IIFE 环境（每轮都不同），而不是外层 `<for>` 环境

效果：
```
迭代 0: IIFE_env_0 { captured=0 }  ← f0.closure_env → 独立的 i 副本
迭代 1: IIFE_env_1 { captured=1 }  ← f1.closure_env → 独立的 i 副本
迭代 2: IIFE_env_2 { captured=2 }  ← f2.closure_env → 独立的 i 副本
```
→ 现在 f0()=0, f1()=1, f2()=2，完全符合预期。

---

## 5. 控制流与返回值

由于解释器是递归下降的树遍历，函数体深层 `return` 需要跳出多层递归。我们使用 **异常机制** 实现非局部退出：

```python
class ReturnException(Exception):
    def __init__(self, value):
        super().__init__()
        self.value = value
```

- `_exec_ReturnStatement` 抛出 `ReturnException(value)`
- `_eval_Call` 在 try/except 中捕获，作为调用结果返回
- 顶层抛出则视为语法错误

---

## 6. 运行方式

```bash
cd closure-lang

# 1) 运行单个示例脚本
python main.py examples/01_basics.scl
python main.py examples/02_control_flow.scl
python main.py examples/03_functions.scl
python main.py examples/04_closures.scl        # 重点：闭包 & 环境逃逸
python main.py examples/05_closure_trap.scl   # 重点：循环闭包陷阱
python main.py examples/06_closure_trap_fixed.scl  # 重点：IIFE 规避方案
python main.py examples/07_scope_chain.scl

# 2) 进入 REPL (交互式)
python main.py

# 3) 作为库调用
from main import run_source
interp = run_source('let x = 42; print x;')
```

---

## 7. 语法快速参考

```
// 单行注释
/* 块注释 */

// 变量
let a = 10;
let b = "hello";
let c;              // 默认为 <undefined>, 读前必须先赋值
a = 20;             // 赋值 (沿作用域链查找, 找到后更新)

// 函数
fn add(x, y) { return x + y; }
add(3, 4);          // 7

// 匿名函数 (lambda)
let double = fn(x) { return x * 2; };
double(5);          // 10

// 立即调用 (IIFE)
(fn(x) { return x * x; })(6);   // 36

// 控制流
if (cond) { ... } else if (cond) { ... } else { ... }
while (cond) { ... }
for (let i = 0; i < 10; i = i + 1) { ... }
return expr;
print expr;

// 运算符 (从低到高优先级)
or                     // 短路
and                    // 短路
== !=                  // 支持任意类型
< <= > >=              // 数字 / 字符串字典序
+ -                    // 数字加减, + 也作字符串拼接
* / %                  // 数字乘除取模
- !                    // 一元负号 / 逻辑非
fn(args)               // 函数调用
```

### 内置函数

| 函数 | 说明 |
|---|---|
| `len(s)` | 字符串长度 |
| `type(x)` | 返回类型字符串 `"int"/"float"/"string"/"bool"/"nil"/"function"/"native"` |
| `to_str(x)` | 任意值转字符串 |
| `parse_int(s)` | 字符串转整数，失败返回 `nil` |

---

## 8. 设计取舍总结

| 选择 | 原因 |
|---|---|
| 闭包按**引用**捕获 Environment（不按值拷贝） | 这是真正的闭包语义，同时自然支持闭包**修改**外层变量 |
| `for`/`while` 不为每次迭代建新作用域 | 如实暴露**循环闭包陷阱**，供教学理解；通过 IIFE 可手动规避 |
| 函数调用时局部作用域 parent = `closure_env` 而非调用点 | 保证**词法（静态）作用域**，与 JS/Lua/Python 主流一致 |
| 使用异常实现 `return` | 树遍历解释器的标准技巧，简洁可靠 |
| Pratt 风格分层递归下降 | 比 `shunting-yard` 更易扩展，优先级一目了然 |
