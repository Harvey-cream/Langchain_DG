"""演示：用户上传路径与 document_pipeline 是同一套清洗切块。"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT.parent / ".env")

from common.document_pipeline.ingest import chunks_from_path, load_documents_for_path
from common.oss_client import _bucket, build_object_key, object_exists
from common.document_pipeline.user_ingest import (
    ingest_user_document_from_oss,
    purge_user_document,
)
from common.rag import search_hits
from config.config import CORPUS_USER

RAW_MD = """# 清洗效果演示

![logo](https://example.com/a.png)
请看 [官方文档](https://example.com/docs)。

## 一、背景

正文里有 **加粗** 和 `代码`。

<img src="x.png" />

## 二、结论

M ySQL 不是 PDF，这里保留；Markdown 图片应被去掉。
"""


def main() -> int:
    print("说明：user_ingest 只做 OSS 下载 + 调 chunks_from_path + 写 Chroma")
    print("      清洗/切块全部来自 common.document_pipeline\n")

    tmp = Path(tempfile.mkdtemp(prefix="demo_clean_"))
    path = tmp / "demo_clean.md"
    path.write_text(RAW_MD, encoding="utf-8")

    print("== 原文 ==")
    print(RAW_MD)

    docs = load_documents_for_path(path, tmp, corpus="preview", domain="demo", fmt="markdown")
    cleaned = docs[0].page_content if docs else ""
    print("== document_pipeline 清洗后 ==")
    print(cleaned)
    print()
    print("检查:")
    print("  图片 markdown 已去:", "![logo]" not in cleaned and "<img" not in cleaned)
    print("  链接只留文字:", "[官方文档]" not in cleaned and "官方文档" in cleaned)
    print("  加粗符号已去:", "**" not in cleaned and "加粗" in cleaned)

    chunks = chunks_from_path(path, tmp, corpus="preview", domain="demo", fmt="markdown")
    print(f"\n== 切块数: {len(chunks)} ==")
    for i, ch in enumerate(chunks, 1):
        print(f"--- chunk {i} ({len(ch.page_content)} chars) ---")
        print(ch.page_content[:240])
        print()

    # 走与上传相同的 OSS → ingest 路径，验证召回
    user_id = 1
    document_id = int(time.time()) % 2_000_000_000
    filename = "demo_clean.md"
    oss_key = build_object_key(user_id=user_id, document_id=document_id, filename=filename)
    bucket, _ = _bucket()
    bucket.put_object(oss_key, RAW_MD.encode("utf-8"), headers={"Content-Type": "text/markdown"})
    assert object_exists(oss_key)

    n = ingest_user_document_from_oss(
        oss_key=oss_key,
        user_id=user_id,
        document_id=document_id,
        filename=filename,
        fmt="markdown",
    )
    print(f"== 经 user_ingest（内部 chunks_from_path）入库 chunks={n} ==")
    hits = search_hits("清洗效果演示 官方文档", corpus=CORPUS_USER, top_k=3, user_id=user_id)
    print(f"召回 {len(hits)} 条")
    if hits:
        print("top preview:", (hits[0][0].page_content or "")[:180].replace("\n", " / "))
        print("top 无图片标记:", "![logo]" not in (hits[0][0].page_content or ""))

    purge_user_document(document_id=document_id, oss_key=oss_key)
    print("\n已清理测试数据。结论：上传清洗 = document_pipeline，没有另一套逻辑。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
