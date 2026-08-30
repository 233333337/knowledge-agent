# Git 版本控制

## Git 的核心概念

Git 是一个**分布式版本控制系统**。和 SVN 的区别在于：每个开发者的本地都是完整的仓库，可以离线工作、本地提交，再和远程同步。

### Git 的三个区域

```
工作区（Working Directory）
   │  git add
   ▼
暂存区（Staging Area / Index）
   │  git commit
   ▼
版本库（Repository / HEAD）
```

- **工作区**：你正在编辑的文件。
- **暂存区**：`git add` 后文件进入这里，准备提交。
- **版本库**：`git commit` 后形成一次永久快照。

### Git 的对象模型

Git 内部用三种对象存储数据：

- **blob**：文件内容（按内容哈希命名，相同内容只存一份）。
- **tree**：目录结构，记录文件名 → blob 的映射。
- **commit**：一次提交的元数据，指向一个 tree、父 commit、作者、时间、提交信息。

`commit` 通过父指针形成一条链，这就是"历史"。理解这个模型后，`reset`/`rebase`/`cherry-pick` 的本质就清楚了：都是在改这条链。

## commit 与分支

### commit 的基本操作

```bash
git status                 # 查看工作区状态
git add .                  # 把所有改动加入暂存区
git commit -m "feat: 添加登录功能"   # 提交
git log --oneline          # 查看提交历史（一行显示）
git log --graph --all      # 图形化查看分支
git diff                   # 查看未暂存改动
git diff --staged          # 查看已暂存改动
```

### commit 信息规范

好的提交信息让人能快速理解历史。常见规范：

```
feat: 新功能
fix: 修复 bug
docs: 文档
refactor: 重构（不改变行为）
test: 测试
chore: 构建/工具
```

示例：`fix: 修复订单金额计算溢出的 bug`。写清楚"为什么改"比"改了什么"更有价值。

### 分支（branch）

分支是独立的工作线。本质上**分支只是指向某个 commit 的指针**，创建分支的开销几乎为零，所以 Git 鼓励多用分支。

```bash
git branch feature/login      # 创建分支
git switch feature/login      # 切换分支（git checkout 的现代替代）
git switch -c dev             # 创建并切换
git branch -d feature/login   # 删除已合并的分支
git branch -D feature/login   # 强制删除未合并的分支
```

### 分支模型

- **main（master）**：放稳定可发布的代码。
- **feature 分支**：开发新功能，完成后合并回 main。
- **release 分支**：发布前的测试、修 bug。
- **hotfix 分支**：线上紧急修复，从 main 分出，修完合并回 main 和 develop。

## merge 与 rebase

merge 和 rebase 都能把两个分支的改动合并到一起，但历史呈现完全不同。

### merge：保留分支历史

```bash
git switch main
git merge feature/login
```

- 产生一个**合并提交（merge commit）**，有两个父提交。
- 历史呈现分叉再合并，能看到"这个功能在哪个分支开发的"。
- 不会改写任何已有提交，**安全**。

```
main:     A --- B --- C --- M
                            /
feature:       D --- E --- /
```

### rebase：把提交"搬"到目标分支上

```bash
git switch feature/login
git rebase main
```

- 把 feature 的提交从公共祖先之后**摘下来，重新放到 main 的最新提交之上**。
- 历史变成一条直线，更干净。
- **会改写提交**（提交哈希会变），在共享分支上慎用。

```
main:     A --- B --- C
                        \
feature:                 D' --- E'
```

### 怎么选

| 场景 | 推荐 |
|---|---|
| 公共/共享分支合并 | **merge**（不改写历史，安全） |
| 个人开发分支整理历史 | **rebase**（历史干净） |
| 只想把别人的改动拿过来 | `git pull --rebase` 或 `git rebase` |
| 团队协作提 PR 之前 | 常用 rebase 整理成清晰提交 |

### 冲突解决

合并冲突是正常的，别怕：

```bash
git merge feature/login
# 提示 CONFLICT in xxx.py
```

打开冲突文件，会看到：

```
<<<<<<< HEAD
你的代码
=======
对方的代码
>>>>>>> feature/login
```

手动保留正确部分，删掉标记，然后：

```bash
git add xxx.py
git commit   # merge 模式
# 或 git rebase --continue
```

**预防冲突**的经验：小步提交、频繁同步远程、每个任务尽量独立文件。

## 远程仓库协作

### 基本命令

```bash
git clone https://github.com/user/repo.git   # 克隆
git remote -v                                # 查看远程
git push origin main                         # 推送
git pull origin main                         # 拉取并合并
git fetch origin                             # 只下载不合并
git remote add origin <url>                  # 添加远程
```

`git pull` = `git fetch` + `git merge`。想用 rebase 方式拉取：`git pull --rebase`。

### 多人协作标准流程

1. 开始任务前：`git switch main && git pull`（确保基于最新代码）。
2. 开分支：`git switch -c feat/xxx`。
3. 小步提交：`git add` + `git commit`。
4. 提交前：`git pull --rebase` 把自己的改动放到最新代码之上，解决冲突。
5. 推送：`git push -u origin feat/xxx`，提 PR（Pull Request）。
6. 合并后删除分支，回 main 拉最新。

### 提 PR 的最佳实践

- PR 尽量小，一次只解决一个问题，便于 review。
- 标题清晰，描述里写背景、改了什么、怎么测。
- 引用相关 issue。

## 撤销与后悔药

```bash
# 撤销工作区修改（危险，会丢改动）
git restore xxx.py

# 撤销暂存（保留工作区改动）
git restore --staged xxx.py

# 修改最近一次提交信息
git commit --amend -m "新信息"

# 回到过去：软重置（保留改动，只移动指针）
git reset --soft HEAD~1

# 硬重置（危险，丢弃提交和改动）
git reset --hard HEAD~1

# 找回被删的提交（reflog 记录所有 HEAD 移动）
git reflog
git reset --hard <hash>
```

`git reflog` 是后悔药的核心：Git 会记录 HEAD 的每一次移动，即使你 reset 掉了提交，只要 reflog 还在，就能找回。

## stash：临时保存工作现场

```bash
git stash            # 保存当前工作区，恢复干净状态
git stash list       # 查看 stash 列表
git stash pop        # 恢复最近一次 stash
git stash apply stash@{1}   # 恢复指定 stash
git stash drop stash@{1}    # 删除指定 stash
```

典型场景：正在改 feature A 的代码，线上突然要紧急修 bug，先 stash 保存现场，修完 bug 再 pop 回来。

## 标签与版本发布

```bash
git tag v1.0.0                 # 打标签
git tag -a v1.0.0 -m "1.0 正式版"   # 带说明的注解标签
git push origin v1.0.0         # 推送标签
git tag                       # 查看所有标签
```

标签用于标记发布版本，比 commit hash 好记。

## .gitignore

用 `.gitignore` 排除不需要纳入版本控制的文件：

```gitignore
# Python
__pycache__/
*.pyc
.venv/
venv/

# 环境与密钥
.env
*.env.local

# IDE
.idea/
.vscode/

# 依赖
node_modules/
```

注意：**已经被 Git 跟踪的文件不受 .gitignore 影响**，需要 `git rm --cached <file>` 先取消跟踪。千万别把 `.env`（含密钥）提交到仓库。

## 常用工作流总结

- **GitHub Flow**：main 始终可部署，每个功能一条分支 + PR 合并，适合持续部署的团队。
- **Git Flow**：main + develop + feature + release + hotfix 五类分支，适合定期发版的团队。
- **Trunk-Based**：所有人直接提交到主干，靠功能开关控制发布，适合超高速迭代。

对个人项目和大部分团队，**GitHub Flow 是最实用的选择**。
