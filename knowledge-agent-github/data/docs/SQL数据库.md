# SQL 数据库

## JOIN 类型

JOIN 用于把多张表按关联条件合并查询。理解 JOIN 的关键是先想清楚"以哪张表为基准、要不要保留不匹配的行"。

### 四种 JOIN 的区别

假设有 `users` 表和 `orders` 表：

| JOIN 类型 | 返回结果 | 典型使用场景 |
|---|---|---|
| `INNER JOIN` | 只返回两表都匹配的行 | 只要"有订单的用户" |
| `LEFT JOIN` | 左表全部行，右表不匹配的用 NULL 填充 | 统计"所有用户，包括没下过单的" |
| `RIGHT JOIN` | 右表全部行，左表不匹配的用 NULL 填充 | 与 LEFT 对称，少用 |
| `FULL OUTER JOIN` | 两表所有行，不匹配的补 NULL | 合并两表全集，MySQL 不直接支持 |

```sql
-- 只返回有订单的用户
SELECT u.name, o.amount
FROM users u
INNER JOIN orders o ON u.id = o.user_id;

-- 返回所有用户，没下单的 amount 为 NULL
SELECT u.name, o.amount
FROM users u
LEFT JOIN orders o ON u.id = o.user_id;
```

实际业务里 **LEFT JOIN 用得最多**，因为它最符合"以主表为主，缺数据就补空"的直觉。

### JOIN 底层执行方式

- **Nested Loop Join**：两层循环逐行匹配，适合小表。
- **Hash Join**：把一张表做成哈希表，另一张表探测，适合大表等值连接。
- **Merge Join**：两表都按连接键排序后归并，适合已经排好序的情况。

优化器会根据表大小、索引情况自动选择执行方式。`EXPLAIN` 里可以看到用的哪种。

### ON 与 WHERE 的区别（易错点）

`LEFT JOIN ... ON` 里的条件控制"是否匹配"，`WHERE` 里的条件控制"是否保留行"。放在 WHERE 里过滤右表条件，效果可能等于 INNER JOIN：

```sql
-- 下面这行会过滤掉没下单的用户（NULL 不满足条件），等价于 INNER JOIN
SELECT u.name, o.amount
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE o.amount > 100;
```

如果想保留所有用户，条件要写在 ON 里。

## 索引

索引是加速查询的数据结构，类似书的目录：没有目录要一页页翻（全表扫描），有目录直接定位。

### 为什么索引能加速

以最常用的 **B+ 树索引**为例：
- B+ 树是平衡多路搜索树，层高很低（几百万行的表，3~4 层）。
- 每层一个磁盘 IO，所以查询只需要几次 IO。
- 叶子节点存数据并互相链接，范围查询（`BETWEEN`、`> <`）很高效。

而全表扫描要读所有数据页，IO 次数和数据量成正比。

### 索引的类型

- **主键索引（聚簇索引）**：InnoDB 里数据行就按主键有序存放，主键索引的叶子节点就是整行数据。
- **普通索引（二级索引/辅助索引）**：叶子节点存主键值，查数据时先查索引再回表取整行。
- **唯一索引**：保证列值不重复，自动加唯一约束。
- **联合索引**：多列组成一个索引，遵循"最左前缀原则"：`(a, b, c)` 索引能加速 `a`、`a,b`、`a,b,c` 的查询，但单独查 `b` 或 `c` 用不上。
- **覆盖索引**：查询的列全部在索引里，无需回表，性能最好。

### 索引的成本

索引不是越多越好：
- **减慢写入**：每次 INSERT/UPDATE/DELETE 都要同步维护所有索引。
- **占用空间**：每个索引都是一棵 B+ 树，都要磁盘空间。
- **增加优化器负担**：索引太多，优化器选错索引的概率也增加。

### 建索引的实践经验

- 给 WHERE、JOIN、ORDER BY 里高频出现的列建索引。
- 区分度高的列优先（性别这种只有两个值的列索引价值低）。
- 字符串列前缀索引：`CREATE INDEX idx ON table(name(10))` 只索引前 10 个字符，节省空间。
- 不要给频繁更新的列建太多索引。
- 用 `EXPLAIN` 验证索引是否真的被用上。

## 主键与外键

### 主键（Primary Key）

主键唯一标识一张表里的一行，**不能重复、不能为 NULL**。设计要点：

- **业务主键 vs 自增主键**：自增主键插入有序，B+ 树页分裂少，性能好；业务主键（如身份证号）可能更新，不建议做主键。
- **UUID vs 自增**：UUID 全局唯一、利于分布式，但无序导致频繁页分裂、占用空间大。分布式场景常用雪花算法（Snowflake）生成有序 ID。
- 主键选择直接影响聚簇索引性能，是表设计的核心决策。

### 外键（Foreign Key）

外键用于建立表之间的关联，引用另一张表的主键（或唯一键）：

```sql
CREATE TABLE orders (
    id INT PRIMARY KEY,
    user_id INT,
    amount DECIMAL(10, 2),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

外键能**保证引用完整性**：不允许插入不存在的 user_id；删除被引用的用户时，可以设置为级联删除（`ON DELETE CASCADE`）或限制（`RESTRICT`）。

### 外键的争议

- **优点**：数据一致性由数据库保证，应用层不用自己写检查逻辑。
- **缺点**：每次写入都要做引用检查，影响性能；在分库分表后外键无法跨库工作。
- 实践中，**很多互联网公司选择不用外键**，靠应用层保证一致性（因为分库分表和性能原因），但**单机小系统用外键是合理的**。

## 事务与 ACID

事务是把多个操作打包成一个原子单元：要么全部成功，要么全部回滚。

| 特性 | 含义 |
|---|---|
| **A**tomicity 原子性 | 全部成功或全部失败，不可拆 |
| **C**onsistency 一致性 | 事务前后数据都满足约束 |
| **I**solation 隔离性 | 并发事务互不干扰 |
| **D**urability 持久性 | 提交后数据不丢失 |

```sql
START TRANSACTION;
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;    -- 或 ROLLBACK;
```

### 隔离级别

| 隔离级别 | 脏读 | 不可重复读 | 幻读 |
|---|---|---|---|
| READ UNCOMMITTED | 可能 | 可能 | 可能 |
| READ COMMITTED | 不会 | 可能 | 可能 |
| REPEATABLE READ（MySQL 默认） | 不会 | 不会 | 可能（InnoDB 靠 MVCC+间隙锁基本解决） |
| SERIALIZABLE | 不会 | 不会 | 不会 |

- **脏读**：读到另一个事务未提交的数据。
- **不可重复读**：同一事务内两次读同一行，结果不同。
- **幻读**：同一事务内两次范围查询，结果行数不同。

MySQL InnoDB 默认 REPEATABLE READ，通过多版本并发控制（MVCC）和间隙锁（gap lock）在多数场景下避免了幻读。

## 三大范式与反范式

- **第一范式（1NF）**：列不可再分，每列都是原子值。
- **第二范式（2NF）**：在 1NF 基础上，非主键列完全依赖主键，不依赖主键的一部分。
- **第三范式（3NF）**：在 2NF 基础上，非主键列不依赖其他非主键列（消除传递依赖）。

实际工程中**经常适度反范式**：比如订单表冗余一个"用户名"字段，避免每次都要 JOIN 用户表。用冗余换查询性能是常见取舍。

## 常用聚合与窗口函数

```sql
-- 聚合：GROUP BY 后只能用聚合函数和分组列
SELECT user_id, COUNT(*) AS cnt, SUM(amount) AS total
FROM orders
GROUP BY user_id
HAVING cnt > 5;

-- 窗口函数：不改变行数，在每行上算窗口内的值
SELECT
    user_id,
    amount,
    RANK() OVER (PARTITION BY user_id ORDER BY amount DESC) AS rnk,
    SUM(amount) OVER (PARTITION BY user_id) AS user_total
FROM orders;
```

窗口函数（`ROW_NUMBER()`、`RANK()`、`LAG()`、`SUM() OVER`）在排行榜、同环比、去重取最新等场景非常强大，是 SQL 进阶的核心技能。

## EXPLAIN 阅读入门

```sql
EXPLAIN SELECT * FROM orders WHERE user_id = 100;
```

重点关注列：
- `type`：`const` > `ref` > `range` > `index` > `ALL`。出现 `ALL`（全表扫描）通常要优化。
- `key`：实际用到的索引，`NULL` 表示没走索引。
- `rows`：预计扫描行数，越小越好。
- `Extra`：`Using index`（覆盖索引，好）、`Using filesort`（文件排序，需注意）、`Using temporary`（临时表，重）。

## 常见 SQL 优化手段

1. 避免 `SELECT *`，只取需要的列。
2. 避免在索引列上用函数或运算（`WHERE YEAR(create_time)=2024` 会让索引失效）。
3. 大分页优化：`LIMIT 1000000, 10` 很慢，可以改成基于主键的 `WHERE id > 1000000 LIMIT 10`。
4. 用 `EXPLAIN` 验证每次改动。
5. 数据量小的时候，简单查询往往比复杂索引更划算。
