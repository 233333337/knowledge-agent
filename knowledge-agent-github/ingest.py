"""文档导入入口：把文档切片、向量化后写入 Chroma 向量库。

v2 支持**增量更新**：
- 只对「新增」或「内容有改动」的文件做切片与向量化（按文件内容哈希判断）
- 自动清理已从磁盘删除的文件对应的片段
- 未改动的文件直接跳过，不再全量重建

用法：
    python ingest.py                  # 增量导入 data/docs 下所有文档（默认）
    python ingest.py 某个文件.md       # 导入指定文件
    python ingest.py 某个目录          # 导入指定目录
    python ingest.py --force          # 忽略哈希，强制全量重建
"""
import sys
from pathlib import Path

import chunker
import store
from config import settings
from embedder import embed


def collect_files(paths: list[str]) -> list[Path]:
    """收集待处理的文件（支持目录递归）。"""
    files = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            files.extend(f for f in p.rglob("*") if f.suffix.lower() in chunker.SUPPORTED)
        elif p.is_file() and p.suffix.lower() in chunker.SUPPORTED:
            files.append(p)
        else:
            print(f"跳过（不支持或不存在）: {p}")
    return files


def ingest(paths: list[str], force: bool = False):
    files = collect_files(paths)
    if not files:
        print("没有可导入的文档，请把 .md/.txt/.docx/.pdf 文件放到 data/docs 目录")
        return

    indexed = store.get_indexed_sources()      # {source: file_hash}
    current = {str(f) for f in files}

    print(f"发现 {len(files)} 个文档，向量库中已有 {len(indexed)} 个来源\n")

    # 1) 清理：磁盘上已删除的文件
    removed = [s for s in indexed if s not in current]
    for src in removed:
        store.delete_source(src)
        print(f"  [删除] {Path(src).name}（文件已不存在）")
    if removed:
        print()

    # 2) 筛选：只处理新增或有改动的文件
    todo = []
    for f in files:
        src = str(f)
        h = store.file_hash(f)
        if force or indexed.get(src) != h:
            todo.append((f, h))
        else:
            print(f"  [跳过] {f.name}（内容未改动）")

    if not todo:
        print(f"\n没有需要更新的文档。当前共 {store.count()} 个片段")
        return

    # 3) 只对需要处理的文件做切片 + 向量化
    print(f"\n{len(todo)} 个文件需要处理，开始切片与向量化 ...")
    total = 0
    for f, h in todo:
        chunks = chunker.chunk_file(f, settings.chunk_size, settings.chunk_overlap)
        if not chunks:
            print(f"  {f.name}: 无有效内容，跳过")
            continue
        vectors = embed([c["text"] for c in chunks])
        n = store.upsert_file(str(f), chunks, vectors, h)
        total += n
        print(f"  {f.name}: {n} 个片段")

    print(f"\n完成：本次写入 {total} 个片段，向量库共 {store.count()} 个片段")
    print(f"存储位置：{settings.chroma_dir}")


if __name__ == "__main__":
    force = "--force" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--force"]
    paths = args or [str(settings.docs_dir)]
    ingest(paths, force=force)
