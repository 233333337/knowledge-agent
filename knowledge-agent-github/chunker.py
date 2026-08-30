"""文档切片：支持 md / txt / docx / pdf，切成带重叠的片段。"""
import re
from pathlib import Path

SUPPORTED = {".md", ".markdown", ".txt", ".docx", ".pdf"}


def read_text(path: Path) -> str:
    """按文件后缀分发到对应的文本提取函数。"""
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown", ".txt"}:
        return path.read_text(encoding="utf-8")
    if suffix == ".docx":
        return read_docx(path)
    if suffix == ".pdf":
        return read_pdf(path)
    raise ValueError(f"不支持的文件类型: {suffix}")


def read_docx(path: Path) -> str:
    """提取 Word 文档（.docx）的段落文本。"""
    from docx import Document

    doc = Document(str(path))
    paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paras)


def read_pdf(path: Path) -> str:
    """提取 PDF 的文字内容（仅文字版 PDF，扫描版需 OCR）。"""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(p.strip() for p in pages if p.strip())


def split_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    """先按空行分段落，段落过长再按字符切（带重叠），尽量保留语义完整。"""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paras:
        if len(buf) + len(p) + 1 <= chunk_size:
            buf = (buf + "\n" + p).strip()
        else:
            if buf:
                chunks.append(buf)
            if len(p) > chunk_size:
                step = max(chunk_size - overlap, 1)
                for i in range(0, len(p), step):
                    chunks.append(p[i:i + chunk_size])
                buf = ""
            else:
                buf = p
    if buf:
        chunks.append(buf)
    return chunks


def chunk_file(path: Path, chunk_size: int = 400, overlap: int = 50) -> list[dict]:
    """读取单个文件并切片，返回 [{text, source, title}]。"""
    text = read_text(path)
    return [
        {"text": c, "source": str(path), "title": path.stem}
        for c in split_text(text, chunk_size, overlap)
    ]
