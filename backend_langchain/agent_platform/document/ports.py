from __future__ import annotations

from pathlib import Path
from typing import Protocol

from langchain_core.documents import Document


class DocumentSource(Protocol):
    key: str
    filename: str


class DocumentParserPort(Protocol):
    def parse(self, path: Path, *, source: DocumentSource) -> list[Document]: ...
