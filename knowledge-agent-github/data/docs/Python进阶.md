# Python 进阶

## 上下文管理器

上下文管理器是 Python 里管理资源的推荐方式，核心是 `with` 语句。它保证资源在使用结束后一定被正确释放，即使中途抛出异常。

### 最典型的例子：文件操作

```python
# 推荐写法
with open("data.txt", "r", encoding="utf-8") as f:
    content = f.read()
# 离开 with 块，文件自动关闭

# 不推荐的写法
f = open("data.txt", "r", encoding="utf-8")
content = f.read()
f.close()  # 如果中间抛异常，这里可能执行不到
```

用 `with` 的好处是：即使 `f.read()` 抛异常，文件也会在退出 `with` 块时被关闭，不会泄漏文件句柄。

### with 语句的原理

`with` 语句依赖两个魔术方法：

- `__enter__(self)`：进入 `with` 块时调用，返回值赋给 `as` 后面的变量。
- `__exit__(self, exc_type, exc_value, traceback)`：离开 `with` 块时调用。如果返回 `True`，表示异常已被处理，不会继续抛出。

```python
class ManagedFile:
    def __init__(self, path, mode):
        self.path = path
        self.mode = mode

    def __enter__(self):
        self.f = open(self.path, self.mode, encoding="utf-8")
        return self.f

    def __exit__(self, exc_type, exc_value, traceback):
        self.f.close()
        return False  # 不吞掉异常

with ManagedFile("data.txt", "r") as f:
    content = f.read()
```

### 用 contextlib 简化

手写 `__enter__`/`__exit__` 比较繁琐，可以用 `contextlib.contextmanager` 把一个生成器函数变成上下文管理器：

```python
from contextlib import contextmanager

@contextmanager
def managed_file(path, mode):
    f = open(path, mode, encoding="utf-8")
    try:
        yield f          # with 块里的 f
    finally:
        f.close()        # 无论是否异常都会执行

with managed_file("data.txt", "r") as f:
    content = f.read()
```

### 上下文管理器的应用场景

- **文件、网络连接、数据库连接、锁**等资源的自动释放。
- **临时切换状态**：比如临时修改环境变量、临时禁用异常、测量代码块耗时。

```python
import time
from contextlib import contextmanager

@contextmanager
def timer():
    start = time.perf_counter()
    yield
    print(f"耗时：{time.perf_counter() - start:.3f}s")

with timer():
    do_something()
```

- **多资源管理**：可以用 `with open(a) as f1, open(b) as f2:` 一次管理多个资源。

## 带参数的装饰器

普通装饰器接收函数本身；带参数的装饰器需要再包一层：外层函数接收配置参数并返回真正的装饰器。

```python
from functools import wraps

def retry(times=3, delay=1.0):
    """失败重试装饰器：最多重试 times 次，每次间隔 delay 秒。"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time
            last_exc = None
            for i in range(times):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    print(f"第 {i + 1} 次失败：{e}")
                    if i < times - 1:
                        time.sleep(delay)
            raise last_exc
        return wrapper
    return decorator

@retry(times=3, delay=0.5)
def call_api():
    ...
```

调用顺序：`retry(times=3, delay=0.5)` 先执行，返回 `decorator`；Python 再把 `call_api` 传给 `decorator`，得到 `wrapper`。

### 什么时候需要带参数装饰器

- **重试**：`@retry(times=3)`
- **限流/超时**：`@timeout(seconds=10)`
- **权限**：`@require_role("admin")`
- **限频**：`@rate_limit(calls=100, per=60)`

参数装饰器的三层结构是固定的套路：**参数层 → 装饰器层 → 包装层**，要能闭着眼睛写出来。

### functools.partial 与装饰器的替代方案

如果参数比较简单，也可以用 `functools.partial` 实现"部分参数预绑定"。但装饰器写法的可读性更好，工程上更常用。

### 装饰器的执行时机

装饰器在**模块导入时**执行，而不是函数被调用时。所以装饰器里尽量别放耗时操作（比如开数据库连接），否则会拖慢导入速度。

## asyncio 异步编程

asyncio 是 Python 官方的异步编程框架，核心是**事件循环（event loop）** 和 **协程（coroutine）**。它解决的是 IO 密集场景下的并发问题：一个线程内通过"等待时切走"实现高并发，而不是靠多线程。

### 为什么需要异步

网络请求、文件读写、数据库查询都属于 IO 操作。IO 期间 CPU 基本是空闲的，传统同步代码会让线程阻塞等待。异步的核心思想是：**在等待 IO 时，把 CPU 让给其他任务**。

```python
import asyncio

async def fetch(url):
    print(f"开始请求 {url}")
    await asyncio.sleep(1)   # 模拟 IO 等待
    print(f"完成请求 {url}")
    return f"data from {url}"

async def main():
    # 并发执行两个请求，总耗时约 1 秒而不是 2 秒
    results = await asyncio.gather(
        fetch("https://a.com"),
        fetch("https://b.com"),
    )
    print(results)

asyncio.run(main())
```

### 核心概念

- **协程（coroutine）**：用 `async def` 定义的函数，调用后返回协程对象，不会立即执行。
- **`await`**：挂起当前协程，把控制权交回事件循环，等被 await 的对象完成后再继续。
- **事件循环**：负责调度所有协程，谁在等待就让谁让出 CPU。

### async/await 常见用法

```python
import asyncio

async def main():
    task1 = asyncio.create_task(fetch("https://a.com"))
    task2 = asyncio.create_task(fetch("https://b.com"))
    # create_task 创建任务，让协程并发运行

    r1, r2 = await asyncio.gather(task1, task2)   # 同时等两个

    # 带超时的等待
    try:
        result = await asyncio.wait_for(fetch("https://a.com"), timeout=3)
    except asyncio.TimeoutError:
        print("请求超时")
```

### 协程 vs 线程

| 维度 | 多线程 | asyncio 协程 |
|---|---|---|
| 调度单位 | 操作系统线程 | 事件循环里的协程 |
| 切换代价 | 大（涉及系统调用） | 小（用户态切换） |
| 并发量 | 受线程数限制 | 可上万（IO 密集） |
| GIL 影响 | CPU 密集受限 | CPU 密集同样受限 |
| 代码复杂度 | 需处理锁、竞态 | 单线程无数据竞争 |

关键结论：**asyncio 适合 IO 密集**（网络、文件、数据库），**不适合 CPU 密集**。CPU 密集任务用多进程（`ProcessPoolExecutor`），普通并发用多线程（`ThreadPoolExecutor`）。

### 异步 HTTP 请求

工程上异步网络请求常用 `aiohttp` 或 `httpx`：

```python
import asyncio
import httpx

async def fetch(url):
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        return resp.status_code

async def main():
    urls = [f"https://example.com/page/{i}" for i in range(20)]
    results = await asyncio.gather(*(fetch(u) for u in urls))
    print(results)

asyncio.run(main())
```

### 常见坑

1. **在同步函数里调用协程**：要用 `asyncio.run()` 或者 `asyncio.create_task()`，不能直接调用。
2. **阻塞操作会卡死事件循环**：协程里如果调用 `time.sleep()` 或同步 requests，会阻塞整个事件循环。必须用 `await asyncio.sleep()` 或异步库。
3. **CPU 密集任务放协程里没意义**：要配合 `loop.run_in_executor()` 丢给线程/进程池。
4. **忘了 `await`**：协程对象不执行就丢弃，最常见的新手错误。

## 类型注解

Python 3.10+ 的类型注解能力大幅增强：

```python
from typing import Optional, Union, Literal

def process(items: list[str], limit: int = 10) -> dict[str, int]:
    """返回 {key: count} 的统计结果。"""
    return {}

# 旧写法（3.9 之前）
# def process(items: List[str]) -> Dict[str, int]:

# 可空类型
def find(user_id: int) -> Optional[str]:  # 或 str | None
    ...

# 字面量类型（限定取值）
def set_mode(mode: Literal["fast", "slow"]): ...
```

类型注解不改变运行行为，但配合 IDE（PyCharm、VS Code）和 mypy 可以：
- 提前发现类型错误。
- 让 IDE 提供智能补全和跳转。
- 让代码自文档化。

## 内存管理与引用计数

Python 用**引用计数 + 垃圾回收**管理内存：

- 每个对象维护一个引用计数，计数归零立即释放。
- 循环引用（A 引用 B、B 引用 A）靠分代垃圾回收器处理。
- `sys.getrefcount()` 可以查看引用计数。
- `gc.collect()` 手动触发垃圾回收，调试内存泄漏时常用。

### 深浅拷贝

```python
import copy

a = [1, 2, [3, 4]]
b = copy.copy(a)        # 浅拷贝：外层独立，内层列表还是同一个
c = copy.deepcopy(a)    # 深拷贝：完全独立
b[2].append(5)
print(a)  # [1, 2, [3, 4, 5]]  浅拷贝受影响
print(c)  # [1, 2, [3, 4]]     深拷贝不受影响
```

可变对象共享是很多隐蔽 bug 的来源，比如把可变对象当函数默认参数：

```python
def add_item(item, items=[]):  # 反模式！
    items.append(item)
    return items

print(add_item(1))  # [1]
print(add_item(2))  # [1, 2]  ← 默认列表被共享了
```

正确写法是默认参数用 `None`，函数内再创建。

## 常用标准库

| 库 | 用途 |
|---|---|
| `os` | 操作系统接口：路径、环境变量、进程 |
| `sys` | 解释器相关：命令行参数、退出、路径 |
| `json` | JSON 序列化/反序列化 |
| `re` | 正则表达式 |
| `datetime` | 日期时间处理 |
| `collections` | 高性能容器：Counter、defaultdict、deque |
| `itertools` | 迭代工具：product、permutations、chain |
| `functools` | 高阶函数工具：wraps、partial、lru_cache |
| `pathlib` | 面向对象的路径操作 |
| `argparse` | 命令行参数解析 |
| `logging` | 日志框架 |
| `subprocess` | 调用外部命令 |
| `concurrent.futures` | 线程池/进程池 |
