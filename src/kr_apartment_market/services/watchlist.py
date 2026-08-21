"""Single-user JSON watchlist with atomic writes."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


@dataclass(slots=True)
class WatchlistStore:
    path: Path
    timezone: str = "Asia/Seoul"

    def _empty(self) -> dict[str, Any]:
        return {"version": 1, "profiles": {}}

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"watchlist file is not readable: {self.path}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("profiles", {}), dict):
            raise RuntimeError("watchlist file has an invalid structure")
        payload.setdefault("version", 1)
        payload.setdefault("profiles", {})
        return payload

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix="watchlist-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def list_items(self, profile_id: str = "default") -> list[dict[str, Any]]:
        payload = self.read()
        profile = payload["profiles"].get(profile_id, {})
        return list(profile.get("items", []))

    def upsert(
        self,
        *,
        profile_id: str,
        lawd_code: str,
        complex_name: str,
        area_m2: float | None = None,
        label: str | None = None,
        item_id: str | None = None,
    ) -> dict[str, Any]:
        if len(lawd_code) != 5 or not lawd_code.isdigit():
            raise ValueError("lawd_code must be a 5-digit string")
        if not complex_name.strip():
            raise ValueError("complex_name must not be empty")
        payload = self.read()
        profile = payload["profiles"].setdefault(profile_id, {"items": []})
        items: list[dict[str, Any]] = profile.setdefault("items", [])
        now = datetime.now(ZoneInfo(self.timezone)).isoformat(timespec="seconds")
        found = next((item for item in items if item.get("id") == item_id), None) if item_id else None
        if found is None:
            found = {
                "id": item_id or str(uuid.uuid4()),
                "created_at": now,
            }
            items.append(found)
        found.update(
            {
                "lawd_code": lawd_code,
                "complex_name": complex_name.strip(),
                "area_m2": area_m2,
                "label": label,
                "updated_at": now,
            }
        )
        self._write(payload)
        return dict(found)

    def delete(self, *, profile_id: str, item_id: str) -> bool:
        payload = self.read()
        profile = payload["profiles"].get(profile_id)
        if not profile:
            return False
        items: list[dict[str, Any]] = profile.get("items", [])
        remaining = [item for item in items if item.get("id") != item_id]
        deleted = len(remaining) != len(items)
        if deleted:
            profile["items"] = remaining
            self._write(payload)
        return deleted
