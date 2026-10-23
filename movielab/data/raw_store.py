"""수집한 문서 원문 저장 — `data/raw/wiki/{movie_id}_{page_id}.json` (SPEC-F2004 §3.7).

파일 이름에 제목을 쓰지 않는다(특수문자 · 길이 문제). 필드는 제공 묶음과 같은 형식이다(§4.2).
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from movielab.core.types import SourceDocument


class RawStore:
    def __init__(self, raw_dir: Path) -> None:
        self.raw_dir = Path(raw_dir)

    def path(self, movie_id: str, page_id: str, kind: str = "wiki") -> Path:
        return self.raw_dir / kind / f"{movie_id}_{page_id}.json"

    def save(self, doc: SourceDocument) -> Path:
        path = self.path(doc.movie_id, doc.page_id, doc.source_kind)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(dataclasses.asdict(doc), ensure_ascii=False, indent=1), encoding="utf-8"
        )
        tmp.replace(path)
        return path

    def load(self, movie_id: str, page_id: str, kind: str = "wiki") -> SourceDocument | None:
        path = self.path(movie_id, page_id, kind)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        fields = {f.name for f in dataclasses.fields(SourceDocument)}
        return SourceDocument(**{k: v for k, v in data.items() if k in fields})

    def iter_documents(
        self, kind: str = "wiki", movie_id: str | None = None
    ) -> list[SourceDocument]:
        """저장된 원문. `movie_id`를 주면 그 영화의 파일만 읽는다."""
        folder = self.raw_dir / kind
        pattern = f"{movie_id}_*.json" if movie_id else "*.json"
        docs = []
        for path in sorted(folder.glob(pattern)):
            movie_id, _, page_id = path.stem.partition("_")
            doc = self.load(movie_id, page_id, kind)
            if doc is not None:
                docs.append(doc)
        return docs
