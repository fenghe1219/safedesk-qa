from __future__ import annotations

from dataclasses import dataclass, field

from qa.client import SafeDeskClient


@dataclass(slots=True)
class KnowledgeCatalog:
    chunk_to_title: dict[str, str]
    doc_to_title: dict[str, str]
    _locator_cache: dict[tuple[str, str], str | None] = field(default_factory=dict)

    @classmethod
    def build(cls, evaluator: SafeDeskClient) -> KnowledgeCatalog:
        payload = evaluator.get_json("/api/knowledge/documents", params={"limit": 100})
        doc_to_title: dict[str, str] = {}
        chunk_to_title: dict[str, str] = {}
        for document in payload["items"]:
            doc_to_title[document["id"]] = document["title"]
            chunks = evaluator.get_json(
                f"/api/knowledge/documents/{document['id']}/chunks",
                params={"limit": 100},
            )
            for chunk in chunks["items"]:
                chunk_to_title[chunk["id"]] = document["title"]
        return cls(chunk_to_title=chunk_to_title, doc_to_title=doc_to_title)

    def titles_for_chunks(self, chunk_ids: list[str]) -> list[str]:
        return [
            self.chunk_to_title[chunk_id]
            for chunk_id in chunk_ids
            if chunk_id in self.chunk_to_title
        ]

    def quote_is_grounded(
        self,
        evaluator: SafeDeskClient,
        *,
        doc_id: str,
        chunk_id: str,
        quote: str,
    ) -> bool:
        key = (doc_id, chunk_id)
        if key not in self._locator_cache:
            response = evaluator.get(
                f"/api/knowledge/documents/{doc_id}/locator",
                params={"chunk_id": chunk_id},
            )
            if response.status_code != 200:
                self._locator_cache[key] = None
            else:
                self._locator_cache[key] = response.json().get("raw_content", "")
        raw = self._locator_cache[key]
        return bool(raw and quote and quote in raw)

    @property
    def document_count(self) -> int:
        return len(self.doc_to_title)

    @property
    def chunk_count(self) -> int:
        return len(self.chunk_to_title)

