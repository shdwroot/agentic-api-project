from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from .models import EvidenceRef, InputDocument


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _excerpt(value: Any, limit: int = 280) -> str:
    rendered = value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)
    rendered = " ".join(rendered.split())
    return rendered if len(rendered) <= limit else f"{rendered[: limit - 1]}…"


@dataclass
class EvidenceIndex:
    """Builds stable, user-visible evidence references for every agent decision."""

    items: list[EvidenceRef] = field(default_factory=list)
    _by_key: dict[tuple[str, str], str] = field(default_factory=dict)

    def add(self, source: str, location: str, value: Any) -> str:
        key = (source, location)
        if key in self._by_key:
            return self._by_key[key]
        rendered = (
            value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)
        )
        identifier = f"EV-{len(self.items) + 1:04d}"
        item = EvidenceRef(
            id=identifier,
            source=source,
            location=location,
            excerpt=_excerpt(value),
            sha256=_digest(rendered),
        )
        self.items.append(item)
        self._by_key[key] = identifier
        return identifier

    def add_document_lines(self, document: InputDocument) -> list[str]:
        ids: list[str] = []
        lines = document.content.splitlines()
        chunk_size = 20
        for start in range(0, len(lines), chunk_size):
            end = min(start + chunk_size, len(lines))
            chunk = "\n".join(lines[start:end]).strip()
            if chunk:
                ids.append(
                    self.add(
                        source=document.name,
                        location=f"lines {start + 1}-{end}",
                        value=chunk,
                    )
                )
        return ids

    def find(self, *, source: str | None = None, location_contains: str | None = None) -> list[str]:
        matches = self.items
        if source is not None:
            matches = [item for item in matches if item.source == source]
        if location_contains is not None:
            matches = [item for item in matches if location_contains in item.location]
        return [item.id for item in matches]
