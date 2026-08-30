# Python 学习笔记

## 装饰器

装饰器是 Python 里非常经典的高级特性。本质上它是一个接收函数作为参数、返回一个新函数的高阶函数。它的作用是在不修改原函数代码的前提下，给函数增加额外的能力，比如日志、计时、权限校验、缓存等。

理解装饰器要先理解 Python 的一个核心事实：**函数在 Python 里是一等公民**，函数可以像普通变量一样被赋值、作为参数传递、作为返回值返回。

### 装饰器的原理

```python
def log(func):
    def wrapper(*args, **kwargs):
        print(f"调用 {func.__name__}")
        result = func(*args, **kwargs)
        print(f"{func.__name__} 执行完毕")
        return result
    return wrapper

@log
def add(a, b):
    return a + b

# 等价写法：
# add = log(add)
```

上面 `@log` 的语法糖等价于 `add = log(add)`。调用 `add(1, 2)` 时，实际上调用的是 `log` 返回的 `wrapper` 函数。

### 使用 functools.wraps 保留原函数信息

直接用上面的写法，`add.__name__` 会变成 `wrapper`，丢失了原函数的信息。解决办法是用 `functools.wraps`：

```python
from functools import wraps

def log(func):
    @wraps(func)  # 把原函数的 __name__、__doc__ 等拷贝到 wrapper 上
    def wrapper(*args, **kwargs):
        print(f"调用 {func.__name__}")
        return func(*args, **kwargs)
    return wrapper
```

### 装饰器的常见应用

- **日志记录**：记录函数调用参数、执行时间、异常信息。
- **性能计时**：统计函数运行耗时，定位性能瓶颈。
- **权限校验**：检查用户是否登录、是否有权限。
- **重试机制**：网络请求失败后自动重试。
- **缓存**：对计算结果做缓存（如 `functools.lru_cache`）。

### 带参数的装饰器

带参数的装饰器需要再包一层。比如 `@retry(times=3)`：

```python
def retry(times):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for _ in range(times):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
            raise last_exc
        return wrapper
    return decorator

@retry(times=3)
def fetch_data():
    ...
```

这里 `retry(times)` 先执行返回 `decorator`，`decorator` 再接收真正的函数。三层嵌套是带参数装饰器的标准写法。

### 多个装饰器的执行顺序

```python
@log
@cache
def heavy(x):
    return x ** 2
```

装饰器从下往上应用，`heavy` 先被 `cache` 装饰，再被 `log` 装饰；但执行时从上往下，先执行 `log` 的外层，再进 `cache`。

## 生成器

生成器是一种惰性求值的迭代器，用 `yield` 关键字实现。它的核心价值是**按需生成**：每次调用 `next()` 才计算下一个值，不会一次性把所有结果放进内存。

### 生成器函数

```python
def fibonacci():
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b

fib = fibonacci()
print(next(fib))  # 0
print(next(fib))  # 1
print(next(fib))  # 1
```

`fibonacci()` 调用时不会立即执行函数体，而是返回一个生成器对象。每次 `next()` 会执行到下一个 `yield` 暂停，记住当前状态。

### 迭代器协议

可迭代对象实现了 `__iter__`，迭代器实现了 `__iter__` 和 `__next__`。生成器天然实现了这两者，所以可以直接用在 `for` 循环里，也可以传给 `sum()`、`list()` 等函数。

### 生成器表达式

```python
squares = (x * x for x in range(10))  # 生成器表达式，不是列表推导式
```

把列表推导式的方括号换成圆括号就是生成器表达式，它在遍历时才逐个计算，适合处理大数据流。

### 为什么生成器能省内存

看这个对比：`range(1_000_000)` 的列表推导式会一次性创建一百万个元素；而生成器只保存当前值和迭代状态。处理大文件时，逐行读取本质就是在用生成器思想，避免把整个文件读进内存。

### yield from

`yield from` 可以把一个子生成器"委托"给外层生成器，简化嵌套迭代：

```python
def flatten(lists):
    for sub in lists:
        yield from sub
```

### 生成器的主要应用

- 处理大文件、大数据流（逐行逐块读取）。
- 实现无限序列（如斐波那契、素数）。
- 协程的基础（配合 `send()`、`throw()` 实现生成器间的数据传递）。
- 惰性计算的流水线。

## 虚拟环境

虚拟环境（virtual environment）是 Python 项目隔离依赖的标准方案。核心问题是：不同项目可能依赖同一包的不同版本，如果都装到全局，会互相冲突。

### venv 的基本使用

```powershell
# 创建虚拟环境
python -m venv venv

# 激活（Windows PowerShell）
venv\Scripts\activate

# 激活（macOS/Linux）
source venv/bin/activate

# 退出
deactivate
```

激活后，`pip install` 装的包只进入当前虚拟环境，不会污染全局环境。

### 为什么需要虚拟环境

- **依赖隔离**：项目 A 用 Django 4，项目 B 用 Django 3，互不干扰。
- **版本可控**：每个项目有独立的包版本，升级一个项目不会弄坏另一个。
- **便于复现**：配合 `requirements.txt` 可以精确还原环境。
- **避免权限问题**：很多系统 Python 目录是受保护的，直接全局安装会失败。

### 生成和安装依赖清单

```powershell
# 导出当前环境的依赖
pip freeze > requirements.txt

# 在别的机器/环境安装
pip install -r requirements.txt
```

`pip freeze` 会列出所有已安装包的精确版本号，这是项目交付和环境复现的关键文件。

### pip 常用命令

```powershell
pip install <包名>           # 安装
pip install <包名>==2.1.0    # 安装指定版本
pip uninstall <包名>         # 卸载
pip list                     # 列出已安装包
pip show <包名>              # 查看包详情
pip install -U <包名>        # 升级
```

### 其他虚拟环境工具

- **conda**：不仅管 Python，还能管整个环境（包括 C 库），适合数据科学，缺点是环境管理较重。
- **poetry / pipenv**：把依赖管理和虚拟环境一体化，支持锁文件（lock file），更现代。
- **uv**：用 Rust 编写的新一代包管理器，安装和解析速度快很多。

### 实践建议

- 每个项目从第一天就用虚拟环境，别等出问题再补。
- `requirements.txt` 要提交到版本控制，保证环境可复现。
- 虚拟环境目录（`venv/`）本身不提交，要加进 `.gitignore`。

## 异常处理

Python 程序运行时的错误通过异常机制暴露。合理处理异常能让程序在出错时优雅降级，而不是直接崩溃。

```python
try:
    result = 10 / int(input("请输入数字："))
except ValueError:
    print("输入的不是数字")
except ZeroDivisionError:
    print("不能除以 0")
else:
    print(f"结果是 {result}")
finally:
    print("无论是否出错都会执行")
```

- `except` 捕获指定异常，可以有多个。
- `else` 在没有异常时执行。
- `finally` 无论是否异常都会执行，常用于释放资源。

### 自定义异常

```python
class BalanceNotEnough(Exception):
    pass

def withdraw(amount, balance):
    if amount > balance:
        raise BalanceNotEnough(f"余额不足，当前余额 {balance}")
    return balance - amount
```

自定义异常让业务错误可以分类处理，比返回错误码更清晰。

## 列表推导式与常用数据结构

```python
# 列表推导式
squares = [x * x for x in range(10) if x % 2 == 0]

# 字典推导式
squares_dict = {x: x * x for x in range(5)}

# 集合推导式
squares_set = {x * x for x in range(5)}

# 元组：不可变，可用于字典键
point = (1, 2)

# 集合：去重、交集并集差集
a = {1, 2, 3}
b = {2, 3, 4}
print(a & b)  # {2, 3} 交集
print(a | b)  # {1, 2, 3, 4} 并集
print(a - b)  # {1} 差集
```

### collections 常用容器

- `defaultdict`：访问不存在的键时自动创建默认值。
- `Counter`：统计元素出现次数。
- `deque`：双端队列，两端都能高效增删。
- `OrderedDict`：保持插入顺序的字典（Python 3.7+ 普通 dict 也保序）。

```python
from collections import Counter, defaultdict, deque

counts = Counter("hello world")   # {'l': 3, 'o': 2, ...}
words = defaultdict(list)          # 访问缺失键时自动创建空列表
d = deque([1, 2, 3])
d.appendleft(0)                    # 左端 O(1) 插入
```

## 函数式编程基础

Python 支持函数式编程风格，常用工具：

```python
from functools import reduce

nums = [1, 2, 3, 4, 5]

# map：对每个元素应用函数
doubled = list(map(lambda x: x * 2, nums))

# filter：按条件筛选
evens = list(filter(lambda x: x % 2 == 0, nums))

# reduce：累积计算
total = reduce(lambda acc, x: acc + x, nums)
```

`lambda` 用于定义匿名函数。列表推导式在很多场景下比 `map`/`filter` 更直观，选择哪种是风格问题，但都要保证可读性。

## 面向对象基础

```python
class Animal:
    def __init__(self, name):
        self.name = name

    def speak(self):
        return "..."

class Dog(Animal):
    def speak(self):
        return f"{self.name} 汪汪叫"

    def __str__(self):
        return f"Dog({self.name})"
```

- `__init__` 是构造方法，在创建对象时初始化属性。
- 子类可以继承父类方法并重写（多态）。
- `__str__` 定义 `print(obj)` 的输出。
- 属性用 `self.xxx` 绑定在实例上，类变量用类内直接定义。

### 魔术方法速查

| 方法 | 作用 |
|---|---|
| `__init__` | 初始化对象 |
| `__str__` | `str(obj)` / `print(obj)` |
| `__repr__` | 交互环境下的表示 |
| `__len__` | `len(obj)` |
| `__getitem__` | `obj[key]` 下标访问 |
| `__call__` | 让对象可调用 `obj()` |
| `__enter__` / `__exit__` | 配合 `with` 使用 |
