# Docker 容器

## 镜像与容器

Docker 是容器化技术的代表，核心概念就是**镜像（Image）** 和**容器（Container）**。

### 镜像（Image）

镜像是**只读的模板**，打包了应用代码、依赖、运行时和配置，是"怎么做"的说明书。一个镜像包含了从操作系统基础层到你的应用运行所需的全部文件。

```bash
docker images          # 查看本地镜像
docker pull nginx      # 拉取镜像
docker rmi nginx       # 删除镜像
```

### 容器（Container）

容器是**镜像运行起来的实例**，是"正在跑"的应用，可以启动、停止、删除。同一个镜像可以启动多个容器，互不影响。

```bash
docker run -d -p 8080:80 --name my-web nginx   # 启动容器
docker ps                 # 查看运行中的容器
docker ps -a              # 查看所有容器（含已停止）
docker stop my-web        # 停止
docker rm my-web          # 删除容器
docker exec -it my-web bash   # 进入容器执行命令
docker logs my-web        # 查看容器日志
```

### 镜像的分层结构

镜像基于**分层（layer）构建**，每层是构建过程中的一次文件变化：

- 基础镜像层（如 Ubuntu、python:3.11）→ 安装依赖层 → 拷贝代码层 → 启动命令层。
- **层可缓存复用**：很多镜像共享底层，节省磁盘；构建时某层没变就不用重建。
- 每层是只读的，容器运行时在镜像之上加一个可写层。

这就是为什么 `docker build` 第二次通常更快：没变的层直接复用缓存。

## Dockerfile 与构建

Dockerfile 是构建镜像的"配方脚本"，用一条条指令描述如何从基础镜像构建出你的应用镜像。

### 核心指令

| 指令 | 作用 | 示例 |
|---|---|---|
| `FROM` | 指定基础镜像 | `FROM python:3.11-slim` |
| `WORKDIR` | 设置工作目录 | `WORKDIR /app` |
| `COPY` | 拷贝文件进镜像 | `COPY . /app` |
| `RUN` | 构建期执行命令（装依赖等） | `RUN pip install -r requirements.txt` |
| `EXPOSE` | 声明容器要监听的端口 | `EXPOSE 8000` |
| `CMD` | 定义容器启动时运行的命令 | `CMD ["python", "app.py"]` |
| `ENTRYPOINT` | 固定启动入口，可接收参数 | `ENTRYPOINT ["python"]` |
| `ENV` | 设置环境变量 | `ENV TZ=Asia/Shanghai` |
| `ARG` | 构建期参数 | `ARG VERSION=1.0` |

### 一个完整的 Dockerfile

```dockerfile
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 先拷贝依赖清单，充分利用层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再拷贝代码（代码变更不会导致依赖层重建）
COPY . .

# 声明端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 构建与运行

```bash
docker build -t my-app:v1 .     # 构建（-t 指定名字和标签，. 是构建上下文）
docker run -p 8000:8000 my-app:v1
```

### 构建上下文与 .dockerignore

`docker build .` 会把当前目录作为**构建上下文**发送给 Docker 守护进程。大目录会让构建变慢，所以：

```dockerignore
__pycache__/
*.pyc
.venv/
venv/
.git/
*.log
node_modules/
```

和 `.gitignore` 一样，`.dockerignore` 排除不该进镜像的文件（比如 .venv 几百 MB 绝对不能进镜像）。

### 镜像大小优化

1. 用轻量基础镜像：`python:3.11-slim`、`alpine`。
2. 合并 RUN：`RUN apt-get update && apt-get install -y xxx && rm -rf /var/lib/apt/lists/*`，减少层数和中间产物。
3. 多阶段构建：编译阶段和运行阶段分离，运行时镜像只带产物。

```dockerfile
# 阶段 1：构建
FROM node:20 AS build
WORKDIR /app
COPY . .
RUN npm ci && npm run build

# 阶段 2：运行（只带构建产物，镜像小很多）
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
```

## 容器与虚拟机的区别

### 原理对比

| 维度 | 虚拟机 | 容器 |
|---|---|---|
| 虚拟化层面 | 虚拟整台机器（硬件级） | 只隔离进程和文件系统（OS 级） |
| 操作系统 | 每个 VM 一个完整 OS | **共享宿主内核** |
| 启动时间 | 分钟级 | 秒级 |
| 资源占用 | 大（每台要完整 OS） | 小（只多几个进程） |
| 隔离性 | 强（独立内核） | 中（共享内核，靠命名空间隔离） |
| 密度 | 一台机器几台 VM | 一台机器上百个容器 |

### 为什么容器这么快、这么轻

容器共享宿主机内核，不需要虚拟一个完整操作系统。它只通过 Linux 的**命名空间（Namespace）** 隔离进程视图（PID、网络、文件系统、用户等），用 **cgroups** 限制资源（CPU、内存）。所以：

- 启动只花几毫秒到几秒（起一个进程的事）。
- 一个镜像几 MB~几百 MB，而虚拟机镜像要几个 GB。

### 容器的缺点

- **与宿主机共享内核**：Windows 容器和 Linux 容器不能通用（Windows 上有 WSL2 兜底）；如果宿主内核有漏洞，容器隔离可能被绕过。
- 没有硬件级隔离，安全边界比虚拟机弱。
- 逃逸风险：恶意容器可能攻击宿主机，所以生产环境要加固（非 root 运行、只读文件系统、限制 capabilities）。

### 怎么选

- **微服务、云原生、CI/CD、弹性扩缩容** → 容器。
- **需要强隔离、跑不同内核的软件、安全要求极高** → 虚拟机。
- 现实中常两者结合：容器跑在虚拟机之上（云厂商的托管 K8s 就是这样）。

## 常用 Docker 运维命令

```bash
# 查看和清理
docker stats                    # 实时资源占用
docker system df                # 磁盘占用统计
docker system prune -a          # 清理未使用的镜像/容器/网络

# 网络
docker network ls
docker run --network my-net ...

# 数据卷（持久化）
docker volume create data
docker run -v data:/app/data my-app
docker run -v $(pwd):/app my-app     # 挂载宿主机目录
```

### 数据卷（Volume）

容器是"用完即走"的，默认容器删除后里面的数据也没了。持久化方案：

1. **Volume**：Docker 管理的持久化存储，推荐。
2. **Bind Mount**：把宿主机目录挂载进容器，开发和调试方便。
3. 容器内数据库等有状态服务，数据必须挂到卷上，否则重启就丢数据。

## docker compose

单容器用 `docker run`，多服务（应用 + Redis + MySQL）用 **docker compose**：

```yaml
# docker-compose.yml
services:
  web:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - redis
  redis:
    image: redis:7-alpine
```

```bash
docker compose up -d        # 启动所有服务
docker compose down         # 停止并删除
docker compose logs -f      # 跟随日志
```

compose 把"环境即代码"落实：一套 yaml 文件描述整个环境，团队其他人一条命令就能拉起一样的开发环境。

## Docker 与 CI/CD

容器是 CI/CD 流水线的最佳载体：

```
代码提交 → CI 构建镜像 → 推送到镜像仓库 → CD 部署到服务器/集群
```

- 开发、测试、生产用**同一个镜像**，消除"在我机器上能跑"的经典问题。
- 弹性扩缩容：K8s 根据负载自动增减容器副本。
- 回滚 = 部署上一个镜像版本。

## 面试常问

- "Docker 镜像和容器有什么区别？" → 只读模板 vs 运行实例，类比"类和对象"。
- "容器为什么比虚拟机轻？" → 共享宿主内核 + 命名空间/cgroups 隔离。
- "如何减小镜像体积？" → 轻量基础镜像、多阶段构建、合并 RUN、.dockerignore。
- "容器数据如何持久化？" → 数据卷 / Bind Mount。
- "如何保证容器安全？" → 非 root、最小权限、镜像扫描、只读根文件系统、限制资源。
