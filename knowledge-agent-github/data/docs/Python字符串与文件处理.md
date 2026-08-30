# Python 字符串与文件处理

## 字符串基础

Python 字符串是**不可变**的字符序列。不可变意味着：字符串一旦创建就不能修改，所有"修改"操作其实都是生成新字符串。这是很多性能陷阱的根源。

```python
s = "hello"
# s[0] = "H"  # ❌ TypeError: 'str' object does not support item assignment
s2 = s.replace("h", "H")   # 生成新字符串 "Hello"
```

### 字符串切片

字符串支持下标访问和切片语法 `s[start:end:step]`：

```python
s = "Hello, Python"

s[0]        # 'H'（第 1 个字符）
s[-1]       # 'n'（最后一个字符）
s[7:]       # 'Python'（第 8 位到最后）
s[:5]       # 'Hello'（前 5 个）
s[::2]      # 'Hlo ot'（每隔一个取）
s[::-1]     # 'nohtyP ,olleH'（反转）
```

**负数索引**从末尾算起，`-1` 是最后一个字符。切片越界不会报错，而是返回尽可能多的内容——这是和其他语言不同的地方。

### 常用字符串方法

| 方法 | 作用 | 示例 |
|---|---|---|
| `strip()` | 去首尾空白 | `"  hi  ".strip()` → `"hi"` |
| `split()` | 按分隔符切分 | `"a,b,c".split(",")` → `["a","b","c"]` |
| `join()` | 拼接序列 | `"-".join(["a","b"])` → `"a-b"` |
| `replace()` | 替换子串 | `"a-b".replace("-","_")` → `"a_b"` |
| `find()` | 找子串位置 | `"abc".find("b")` → `1`，找不到返回 `-1` |
| `startswith()` | 前缀判断 | `"report.pdf".startswith("report")` → `True` |
| `endswith()` | 后缀判断 | `"report.pdf".endswith(".pdf")` → `True` |
| `upper()/lower()` | 大小写转换 | `"Hi".lower()` → `"hi"` |
| `isdigit()` | 是否全是数字 | `"123".isdigit()` → `True` |
| `count()` | 统计出现次数 | `"aaa".count("a")` → `3` |
| `zfill()` | 补零 | `"7".zfill(3)` → `"007"` |

```python
text = "  Hello, World!  "
text.strip()                    # 'Hello, World!'
words = text.split(",")         # ['  Hello', ' World!  ']
",".join(w.strip() for w in words)  # 'Hello,World!'
```

### 格式化

```python
name, score = "小明", 95.5

# 老式 %
print("成绩：%s %d" % (name, score))

# format 方法
print("成绩：{} {}".format(name, score))
print("成绩：{1} {0}".format(name, score))   # 按索引

# f-string（Python 3.6+，推荐）
print(f"成绩：{name} {score}")
print(f"成绩：{score:.1f}")       # 保留 1 位小数
print(f"完成度：{0.856:.1%}")     # 百分比 → 85.6%
```

### 编码与字节

```python
s = "中文"
b = s.encode("utf-8")       # b'\xe4\xb8\xad\xe6\x96\x87'（字节）
s2 = b.decode("utf-8")      # 转回字符串 "中文"
```

- **str** 是 Unicode 文本，**bytes** 是原始字节。
- 文件读写、网络传输都是字节，要显式编解码。
- 读写文件不指定编码时，Windows 默认可能用 GBK，**建议始终显式写 `encoding="utf-8"`**。

## 文件读写

### 打开文件

```python
# 最安全的方式：with 语句，用完自动关闭
with open("data.txt", "r", encoding="utf-8") as f:
    content = f.read()
```

### 文件模式

| 模式 | 含义 |
|---|---|
| `r` | 只读（默认） |
| `w` | 覆盖写（不存在则创建） |
| `a` | 追加写 |
| `r+` | 读写 |
| `w+` | 读写（覆盖） |
| `rb` / `wb` | 二进制读/写（图片、压缩包） |
| `x` | 独占创建（已存在则报错） |

### 三种读取方式

```python
# 1. 一次读全部（小文件）
content = f.read()

# 2. 按行读列表
lines = f.readlines()

# 3. 逐行迭代（大文件推荐）
for line in f:
    process(line)
```

**为什么读大文件要逐行**：`f.read()` 会把整个文件读进内存，一个 2GB 的日志文件直接内存爆掉。`for line in f` 底层有缓冲，一次只处理一行，内存占用恒定。

### 处理超大文件的技巧

```python
# 逐块读取，避免一次读入全部
def read_large_file(path, chunk_size=65536):
    with open(path, "r", encoding="utf-8") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk   # 生成器，边读边处理
```

配合 `enumerate` 还能带行号遍历：

```python
with open("app.log", encoding="utf-8") as f:
    for line_no, line in enumerate(f, 1):
        if "ERROR" in line:
            print(line_no, line)
```

### 写入文件

```python
# 覆盖写
with open("out.txt", "w", encoding="utf-8") as f:
    f.write("第一行\n")
    f.write("第二行\n")

# 追加
with open("out.txt", "a", encoding="utf-8") as f:
    f.write("追加的内容\n")

# 写多行
lines = ["a", "b", "c"]
with open("out.txt", "w", encoding="utf-8") as f:
    f.writelines(l + "\n" for l in lines)
```

**注意**：`open` 的编码参数很重要。读文件时如果编码猜错，会抛 `UnicodeDecodeError`。处理未知编码时可以用 `errors="replace"` 兜底：

```python
with open("data.txt", encoding="utf-8", errors="replace") as f:
    content = f.read()
```

### 常见坑

1. **忘记关闭文件**：用 `with` 就不会有这个坑。
2. **编码不对**：写中文永远显式 `encoding="utf-8"`。
3. **二进制文件用文本模式打开**：会乱码或报错，用 `rb`。
4. **`w` 模式误覆盖**：`w` 会清空原文件，想保留原内容用 `a`。
5. **相对路径依赖当前目录**：用 `pathlib` 或 `os.path.abspath` 明确路径。

## 路径与目录操作

### os.path 传统写法

```python
import os

os.path.join("a", "b", "c.txt")   # 'a\\b\\c.txt'（自动处理分隔符）
os.path.exists("data.txt")        # 是否存在
os.path.isfile("data.txt")        # 是否文件
os.path.isdir("data")             # 是否目录
os.path.splitext("a.txt")         # ('a', '.txt') 拆后缀
os.path.basename("/a/b/c.txt")    # 'c.txt'
os.path.dirname("/a/b/c.txt")     # '/a/b'
os.makedirs("a/b/c", exist_ok=True)   # 创建多层目录
os.remove("tmp.txt")              # 删除文件
os.listdir(".")                   # 列出目录内容
```

### pathlib 现代写法（推荐）

Python 3.4+ 的 `pathlib` 提供面向对象的路径操作：

```python
from pathlib import Path

p = Path("data/docs/report.md")

p.parent          # data/docs
p.name            # report.md
p.stem            # report
p.suffix          # .md
p.exists()        # 是否存在
p.is_file()       # 是否文件

# 拼接
data_dir = Path("data") / "docs" / "report.md"   # 用 / 拼接！

# 读写（自带 open，且自动处理编码）
text = Path("data.txt").read_text(encoding="utf-8")
Path("out.txt").write_text("hello", encoding="utf-8")

# 遍历目录
for f in Path("data").rglob("*.md"):   # 递归找所有 .md
    print(f)

# 创建目录
Path("a/b/c").mkdir(parents=True, exist_ok=True)
```

**为什么推荐 pathlib**：`/` 操作符直观、跨平台（Windows 自动用 `\`，Linux/macOS 用 `/`）、方法齐全、代码可读性高。新代码优先用 pathlib。

### 获取路径的常见技巧

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent   # 当前文件所在目录
PROJECT_DIR = BASE_DIR.parent                # 上一级（项目根目录）
CACHE_FILE = BASE_DIR / "cache" / "data.json"

# 保证目录存在
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
```

用 `Path(__file__).resolve().parent` 定位项目路径，比依赖"当前工作目录"可靠得多——不管你从哪启动脚本，路径都不会飘。

## JSON 与配置文件

### 读写 JSON

```python
import json

data = {"name": "张三", "scores": [90, 95]}

# 写入
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# 读取
with open("data.json", encoding="utf-8") as f:
    loaded = json.load(f)

# 字符串互转
s = json.dumps(data, ensure_ascii=False)   # 对象 → JSON 字符串
obj = json.loads(s)                        # JSON 字符串 → 对象
```

**`ensure_ascii=False` 一定要写**：否则中文会变成 `\u4e2d\u6587` 转义，人没法读。

### 解析常见数据格式

```python
# CSV
import csv
with open("data.csv", encoding="utf-8") as f:
    rows = list(csv.reader(f))

# 或直接手工 split（注意引号嵌套问题，最好用 csv 模块）
# with open("data.csv", encoding="utf-8") as f:
#     rows = [line.strip().split(",") for line in f]
```

## 实战：按关键字统计日志

```python
from collections import Counter
from pathlib import Path

def count_log_levels(log_path):
    """统计日志中各级别出现次数。"""
    levels = Counter()
    for line in Path(log_path).read_text(encoding="utf-8", errors="replace").splitlines():
        for level in ("DEBUG", "INFO", "WARN", "ERROR"):
            if f" {level} " in line:
                levels[level] += 1
                break
    return levels

print(count_log_levels("app.log"))
# Counter({'INFO': 120, 'ERROR': 13, 'WARN': 5})
```

这串代码综合了本章核心：pathlib、编码处理、逐行处理、Counter 统计。
