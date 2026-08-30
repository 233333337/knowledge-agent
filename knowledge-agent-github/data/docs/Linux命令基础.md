# Linux 命令基础

## 文件与目录命令

### 查看与切换

```bash
pwd                     # 显示当前路径
ls                      # 列出当前目录内容
ls -l                   # 详细信息（权限、所有者、大小、时间）
ls -a                   # 包含隐藏文件（. 开头）
ls -lh                  # 人类可读的大小
ls -lt                  # 按修改时间排序（常用）
cd /home/user           # 切换目录
cd ~                    # 回到家目录
cd ..                   # 上一级
```

### 创建、复制、移动、删除

```bash
mkdir newdir            # 创建目录
mkdir -p a/b/c          # 一次创建多层
touch file.txt          # 创建空文件或更新时间戳

cp file.txt backup.txt  # 复制
cp -r dir1 dir2         # 递归复制目录
cp -a                  # 保留权限、时间等属性（常用于备份）

mv file.txt /tmp/       # 移动
mv old.txt new.txt      # 重命名（同一目录下移动就是改名）

rm file.txt             # 删除文件
rm -r dir               # 递归删除目录
rm -rf dir              # 强制递归删除 ⚠️ 危险，慎用
```

**关于 `rm -rf` 的安全意识**：`rm -rf /` 会删系统；`rm -rf *` 在当前目录下误删。删除前先 `ls` 确认路径，重要数据用回收站/版本控制兜底。

## 查看文件内容

```bash
cat file.txt            # 打印整个文件
less file.txt           # 分页查看（q 退出，/搜索，g/G 跳首尾）
head -20 file.txt       # 看前 20 行
tail -20 file.txt       # 看后 20 行
tail -f app.log         # 实时跟踪文件新增内容（看日志神器）
wc -l file.txt          # 统计行数
```

### grep 搜索

```bash
grep "error" app.log                # 按关键字搜索
grep -i "error" app.log             # 忽略大小写
grep -n "error" app.log             # 显示行号
grep -r "keyword" /path/to/dir      # 递归搜索目录
grep -A 2 -B 2 "error" app.log      # 显示上下文前后 2 行
grep -v "debug" app.log             # 反向匹配（不含 debug 的行）
grep -E "error|warning" app.log     # 扩展正则，多关键字
```

## 管道与重定向

Linux 哲学："一个工具只做一件事，用管道组合"。管道 `|` 把前一个命令的输出作为后一个命令的输入：

```bash
ps aux | grep python               # 找 python 进程
cat app.log | grep "ERROR" | head -20   # 流水线：读→筛→取前20
ls -l | awk '{print $9}'           # 取第 9 列（文件名）
cat file.txt | wc -l               # 数行数
```

### 重定向

```bash
command > file.txt        # 覆盖写入
command >> file.txt       # 追加写入
command 2> error.log      # 错误输出重定向（2 是 stderr 的文件描述符）
command > out.log 2>&1    # 标准输出和错误都写到一个文件
command < input.txt       # 从文件读输入
```

### 常用文本处理三剑客

- **grep**：筛选行。
- **sed**：流编辑，替换/删除/插入。

```bash
sed -i 's/old/new/g' file.txt   # 全局替换并写回文件
sed -n '10,20p' file.txt        # 打印第 10 到 20 行
sed '/^#/d' config.conf         # 删除注释行
```

- **awk**：按列处理，适合日志统计。

```bash
awk '{print $1, $NF}' file.txt    # 打印第一列和最后一列
awk -F, '{sum += $3} END {print sum}' data.csv   # 按逗号分列并求和
awk '$4 > 100 {print}' access.log # 条件筛选
```

## 权限管理

### 权限的三组九位

```bash
-rw-r--r-- 1 user group 1024 Jun 1 10:00 file.txt
│└┬┘└┬┘└┬┘
│ │  │  └── 其他用户权限
│ │  └──── 用户组权限
│ └─────── 所有者权限
└──────── 类型（-文件 / d目录 / l链接）
```

每位权限：`r`（读=4）`w`（写=2）`x`（执行=1）。

### chmod 修改权限

**数字法**：每位数字 = r(4)+w(2)+x(1)。

```bash
chmod 755 script.sh   # 所有者 rwx(7)，组 r-x(5)，其他人 r-x(5)
chmod 644 file.txt    # 所有者 rw-，组 r--，其他人 r--
chmod +x script.sh    # 给所有人加执行权限
chmod -R 755 dir/     # 递归修改目录下所有文件
```

**符号法**：`u`所有者、`g`组、`o`其他、`a`所有人。

```bash
chmod u+x script.sh   # 只给所有者加执行
chmod g-w file.txt    # 去掉组的写权限
```

### 常见权限组合

| 权限 | 用途 |
|---|---|
| 755 | 目录/脚本（默认） |
| 644 | 普通文件 |
| 700 | 私有脚本/密钥 |
| 600 | 私密文件（如 .ssh/id_rsa 必须 600） |
| 777 | 危险，人人可写，别用 |

### chown 修改所有者

```bash
chown user file.txt           # 改所有者
chown user:group file.txt     # 同时改所有者和组
chown -R user:group dir/      # 递归
```

**为什么密钥文件要 600**：`ssh` 会拒绝权限过宽的私钥（提示 `Permissions too open`），安全机制强制最小权限。

## 进程管理

```bash
ps                        # 当前终端进程
ps aux                    # 所有进程，含 CPU/内存占用（最常用）
ps aux | grep python      # 找指定进程
top                       # 实时进程监控（类似任务管理器，q 退出）
htop                      # top 的增强版（更好看）

kill <PID>                # 发送 TERM 信号，优雅终止
kill -9 <PID>             # 强制杀死（SIGKILL，无法被捕获）
pkill -f "keyword"        # 按名字批量杀

# 后台运行
nohup python app.py > app.log 2>&1 &    # 脱离终端后台运行
jobs                      # 查看当前终端后台任务
```

**kill vs kill -9**：先 `kill`（让进程自己清理资源），不行再 `kill -9`。直接 -9 可能留下脏数据。

## 网络命令

```bash
ping baidu.com            # 测试连通性
curl -I https://example.com    # 查看 HTTP 头
curl -X POST -H "Content-Type: application/json" -d '{"a":1}' https://api.xxx
netstat -tlnp             # 查看端口监听（传统）
ss -tlnp                  # 更快更现代的替代
ss -tln | grep :8080      # 看 8080 端口谁在监听
telnet host 3306          # 测试端口连通
nc -zv host 3306          # nc 测试端口（更方便）
```

**排查"端口被占用"的标准流程**：`ss -tlnp | grep <port>` 找到 PID → `ps -fp <PID>` 看是什么程序 → 决定杀掉或改配置。

## 压缩与解压

```bash
# tar（最常用）
tar -czvf archive.tar.gz dir/     # 压缩（c创建 zgzip v显示 f文件）
tar -xzvf archive.tar.gz          # 解压
tar -tzf archive.tar.gz           # 查看内容不解压

# zip
zip -r archive.zip dir/
unzip archive.zip
```

## 软链接与硬链接

```bash
ln -s /usr/local/python3 python   # 软链接（类似 Windows 快捷方式）
ln /path/file hardlink            # 硬链接（同一文件的另一个名字）
```

- **软链接**：指向路径，源文件删除后失效，常用于目录；跨文件系统可用。
- **硬链接**：指向同一 inode，删除源文件不影响，不能跨文件系统、不能链接目录。

`/usr/bin/python -> /usr/local/bin/python3.11` 这种就是软链接。

## 系统信息与磁盘

```bash
df -h                     # 磁盘空间（人类可读）
du -sh dir/               # 目录占用大小
free -h                   # 内存使用
uptime                    # 负载情况（1/5/15 分钟负载）
uname -a                  # 内核信息
cat /etc/os-release       # 系统发行版
lsblk                     # 磁盘分区
```

## shell 基础

```bash
# 变量
NAME="world"
echo "hello $NAME"

# 条件判断
if [ -f file.txt ]; then echo "存在"; fi

# 循环
for i in 1 2 3; do echo $i; done

# 通配符
ls *.log                 # 所有 .log
cp config*.yaml /backup/
```

**环境变量与 PATH**：

```bash
export JAVA_HOME=/usr/lib/jvm/java-17
echo $PATH               # 查看可执行文件搜索路径
which python             # 看 python 实际在哪个目录
```

## 排查问题实战套路

1. **服务起不来**：先看日志 `tail -f app.log`，再查进程 `ps aux | grep app`，再查端口 `ss -tlnp`。
2. **系统慢**：`top` 看 CPU/内存大户，`df -h` 看磁盘是否满了，`dmesg` 看内核日志。
3. **找不到命令**：`which xxx`、`echo $PATH`、重装或改 PATH。
4. **端口被占**：`ss -tlnp | grep <port>` 找 PID，kill 或换端口。
5. **权限拒绝**：`ls -l` 看权限，`sudo` 或 `chmod`。

## 学习建议

- 命令记不住正常，用 `man` 和 `--help` 随时查：`man ls`、`ls --help`。
- 养成"先想清楚再执行"的习惯，尤其 `rm -rf`、`chmod 777` 这类危险操作。
- 多用管道组合，把常用组合写成 shell 脚本或 alias。
