# Redis 缓存

## Redis 是什么

Redis（Remote Dictionary Server）是一个高性能的内存数据库，常用于**缓存**、**消息队列**、**分布式锁**、**计数器**等场景。

### 为什么快

- **纯内存操作**：数据在内存，读写是微秒级。
- **单线程事件循环**：省去锁和上下文切换开销，配合 IO 多路复用实现高并发。
- **高效数据结构**：底层用合适的数据结构（哈希表、跳表等）。

> 注意：Redis 6.0+ 引入多线程用于网络 IO，但命令执行仍是单线程。

### 常用数据结构

| 结构 | 说明 | 典型用途 |
|---|---|---|
| String | 字符串/数字 | 缓存值、计数器、分布式锁 |
| Hash | 字段-值映射 | 存对象（用户信息） |
| List | 双向链表 | 消息队列、最新列表 |
| Set | 无序去重集合 | 去重、交集并集（共同好友） |
| Sorted Set | 有序集合（带分数） | 排行榜、延迟队列 |
| HyperLogLog | 基数统计 | 独立访客 UV 统计 |

```bash
# 常用命令
SET user:1001 '{"name":"张三"}' EX 3600    # 带过期时间
GET user:1001
INCR page_view                     # 计数器 +1
LPUSH task_queue "job1"            # 列表入队
BRPOP task_queue 0                 # 阻塞取队尾（消息队列）
ZADD rank 100 "player1"            # 有序集合
ZREVRANGE rank 0 9                 # 排行榜前 10
```

## 缓存三大经典问题：穿透、击穿、雪崩

这三个问题是缓存架构的必考题，也是线上事故高发区。核心是搞清楚**查不到的原因**和**影响范围**。

### 缓存穿透（查不存在的数据）

**定义**：查询一个**根本不存在**的 key（比如恶意刷一个不存在的商品 ID），缓存和数据库都没有。每次请求都穿透到数据库，数据库被大量无效查询打垮。

```text
请求 → 缓存没有 → 数据库也没有 → 直接返回空
每次请求都打数据库！
```

**解决方案**：

1. **缓存空值**：查询结果为 None 也缓存，设置短过期时间（如 5 分钟）。简单有效。

```python
def get_user(user_id):
    data = redis.get(f"user:{user_id}")
    if data is not None:          # 空值也被缓存了
        return data
    user = db.query_user(user_id)
    # 空值也缓存，防止穿透
    redis.set(f"user:{user_id}", user or None, ex=300 if user is None else 3600)
    return user
```

2. **布隆过滤器（Bloom Filter）**：请求前先过过滤器，不存在直接拦截，不进数据库。

```python
from pybloom_live import BloomFilter

bf = BloomFilter(capacity=1000000, error_rate=0.001)
bf.add("user:1001")
if "user:999999" not in bf:   # 直接返回，不打数据库
    return None
```

3. **参数校验**：对非法 ID（负数、超长）直接拒绝。

### 缓存击穿（热点 key 过期）

**定义**：某个**热点 key** 突然过期，大量并发请求同时打到数据库去重建缓存。

```text
热点 key 过期瞬间 → 1000 个请求同时发现缓存没有 → 全部打数据库
```

**和穿透的区别**：穿透是"查不存在的数据"，击穿是"热点数据刚好过期"。

**解决方案**：

1. **互斥锁**：只让一个请求去查库重建，其他请求等待。

```python
def get_hot(key, rebuild_func, ttl=3600):
    data = redis.get(key)
    if data is not None:
        return data
    # 只让一个线程重建缓存
    with redis.lock(f"lock:{key}", timeout=5):
        data = redis.get(key)      # 双重检查
        if data is not None:
            return data
        data = rebuild_func()      # 查库
        redis.set(key, data, ex=ttl)
    return data
```

2. **逻辑过期**：缓存不设物理过期时间，业务字段带过期标记，发现过期后异步重建（防止缓存击穿的进阶方案，还能保证永远能读到旧数据）。

3. **热点 key 永不过期** + 后台定时刷新（适合几乎不变的配置类数据）。

### 缓存雪崩（大量 key 同时过期）

**定义**：**大量缓存**在同一时间集中失效（比如同一批 key 设置了相同的过期时间，或 Redis 服务挂了），所有请求瞬间打到数据库，数据库被压垮。

**和击穿的区别**：击穿是**单个**热点 key，雪崩是**大批** key 或整个服务。

**解决方案**：

1. **过期时间加随机值**：`EXPIRE 3600 + random(0, 300)`，避免同一批 key 同时过期。

```python
ttl = 3600 + random.randint(0, 300)
redis.set(key, value, ex=ttl)
```

2. **热点数据不过期**：永不过期 + 后台更新。
3. **限流降级**：数据库扛不住时，直接限流、降级（返回旧缓存或友好提示）。
4. **Redis 高可用**：Redis 主从 + 哨兵/集群，防止 Redis 挂掉导致雪崩。
5. **多级缓存**：本地缓存（如 Caffeine）+ Redis + 数据库，多层兜底。

### 三兄弟对比总结

| 问题 | 触发原因 | 影响范围 | 最常用解法 |
|---|---|---|---|
| 穿透 | 查不存在的数据 | 每次请求打库 | 缓存空值 / 布隆过滤器 |
| 击穿 | 热点 key 过期 | 单个 key 打崩库 | 互斥锁 / 逻辑过期 |
| 雪崩 | 大量 key 同时过期 | 大规模打崩库 | 过期随机化 / 高可用 |

## 缓存更新策略

### Cache Aside（旁路缓存）——最常用

```text
读：先查缓存 → 命中返回 → 未命中查库并回填缓存
写：先更新数据库 → 再删除缓存（或更新缓存）
```

**为什么写操作"先更新库再删缓存"而不是"先更新缓存"**：
- 并发下先更新缓存容易产生脏数据（两个写并发，后写的缓存被先写覆盖）。
- 删缓存让下次读重新加载，配合"缓存重建"的原子性更安全。

### 延迟双删

高并发下"先更新库再删缓存"仍可能有短暂不一致（读请求在删缓存前读到了旧缓存）。加强版：

```python
def update_user(user_id, data):
    db.update(user_id, data)
    redis.delete(f"user:{user_id}")
    time.sleep(0.1)          # 等待可能读取旧缓存的请求过去
    redis.delete(f"user:{user_id}")   # 再删一次
```

**核心原则**：缓存一定要设置过期时间兜底，防止"缓存永远不一致"。

## 数据过期与淘汰策略

### 过期删除

- **惰性删除**：访问时才检查是否过期。
- **定期删除**：后台周期抽样删除过期 key。

### 内存淘汰（内存满了怎么办）

| 策略 | 行为 |
|---|---|
| noeviction | 不淘汰，直接报错（默认） |
| allkeys-lru | 淘汰最久没用的 key |
| volatile-lru | 只在有过期时间的 key 里淘汰最久没用的 |
| allkeys-lfu | 淘汰访问频率最低的 key |
| allkeys-random | 随机淘汰 |

生产常用 `allkeys-lru` 或 `volatile-lru`。设置合理 `maxmemory` 很重要，防止内存打满。

## 持久化

Redis 重启后数据会丢吗？取决于持久化配置。

### RDB（快照）

- 定期把内存数据 dump 成二进制文件。
- 恢复快、文件小；但两次快照之间的数据可能丢。
- 适合备份、冷备。

### AOF（追加日志）

- 记录每条写命令，重启时重放。
- 数据更安全（可以 everysec 每秒刷盘，最多丢 1 秒数据）。
- 文件大、恢复慢。

### 最佳实践

- 两者结合：RDB 做冷备，AOF 保证数据不丢。
- 缓存场景对持久化要求低，纯缓存甚至可以关掉持久化换性能。

## 分布式锁

跨多个服务实例互斥访问共享资源，用 Redis 实现分布式锁：

```python
# 加锁（SETNX + 过期时间原子操作，防止死锁）
ok = redis.set(f"lock:{key}", token, nx=True, ex=10)
if ok:
    try:
        do_critical_work()
    finally:
        # 释放锁：用 Lua 脚本保证"校验 token + 删除"原子性
        redis.eval("if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end",
                   1, f"lock:{key}", token)
```

要点：
- `SET key value NX EX 10` 原子地实现"不存在才设置 + 过期"。
- value 用唯一 token，释放时校验是"自己的锁"才删，防止误删别人的锁。
- 过期时间兜底，防止持有锁的进程挂掉导致死锁。

## 缓存设计实战

### 什么数据适合缓存

- 读多写少（用户信息、商品详情、配置）。
- 数据变化不频繁或能容忍短暂不一致。
- 热点集中（排行榜、爆款商品）。

### 什么数据不适合缓存

- 强一致性要求（余额、库存——需要事务性保证）。
- 写多读少（大量写入缓存收益低，还增加一致性负担）。

### 缓存键设计

```text
模块:业务:ID[:维度]
user:1001:profile
order:8888:detail
product:3001:stock
```

- 前缀分层级，避免 key 冲突和混乱。
- 控制 key 长度，过长的 key 浪费内存。
- 设置过期时间 TTL，防止垃圾数据堆积。

### 监控与排查

- **命中率**：缓存命中 / 总请求。命中率低 → 检查过期策略、缓存粒度、key 设计。
- **大 key / 热 key**：超大 value 影响网络和内存，拆分或压缩；热 key 造成单点压力，加本地缓存分散。
- **内存趋势**：监控 used_memory，接近 maxmemory 提前扩容或优化。
