"""Atomic local persistence for Home Finder profiles and saved searches."""

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

from kr_apartment_market.utils import normalize_name, stable_id


@dataclass(slots=True)
class HomeFinderStore:
    path: Path
    timezone: str = "Asia/Seoul"

    def _now(self) -> str:
        return datetime.now(ZoneInfo(self.timezone)).isoformat(timespec="seconds")

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {
            "version": 1,
            "profiles": {},
            "saved_searches": {},
            "runs": {},
        }

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"home finder data file is not readable: {self.path}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("home finder data file must contain an object")
        payload.setdefault("version", 1)
        for key in ("profiles", "saved_searches", "runs"):
            if not isinstance(payload.get(key, {}), dict):
                raise RuntimeError(f"home finder data field '{key}' must be an object")
            payload.setdefault(key, {})
        return payload

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix="home-finder-", suffix=".json", dir=self.path.parent
        )
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

    def create_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        payload = self.read()
        profile_id = str(profile["profile_id"])
        if profile_id in payload["profiles"]:
            raise ValueError(f"profile already exists: {profile_id}")
        payload["profiles"][profile_id] = profile
        self._write(payload)
        return dict(profile)

    def put_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        payload = self.read()
        profile_id = str(profile["profile_id"])
        payload["profiles"][profile_id] = profile
        self._write(payload)
        return dict(profile)

    def get_profile(self, profile_id: str) -> dict[str, Any] | None:
        profile = self.read()["profiles"].get(profile_id)
        return dict(profile) if isinstance(profile, dict) else None

    def list_profiles(self) -> list[dict[str, Any]]:
        profiles = [dict(item) for item in self.read()["profiles"].values()]
        profiles.sort(key=lambda item: (str(item.get("name", "")), str(item.get("profile_id", ""))))
        return profiles

    def delete_profile(self, profile_id: str) -> bool:
        payload = self.read()
        existed = payload["profiles"].pop(profile_id, None) is not None
        if not existed:
            return False
        for search_id, search in list(payload["saved_searches"].items()):
            if search.get("profile_id") == profile_id:
                payload["saved_searches"].pop(search_id, None)
                payload["runs"].pop(search_id, None)
        self._write(payload)
        return True

    def save_search(
        self,
        *,
        profile_id: str,
        label: str | None = None,
        search_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        candidate_limit: int | None = None,
    ) -> dict[str, Any]:
        payload = self.read()
        if profile_id not in payload["profiles"]:
            raise ValueError(f"profile not found: {profile_id}")
        now = self._now()
        search_id = search_id or str(uuid.uuid4())
        existing = payload["saved_searches"].get(search_id, {})
        item = {
            "search_id": search_id,
            "profile_id": profile_id,
            "label": label or existing.get("label") or payload["profiles"][profile_id].get("name"),
            "date_from": date_from,
            "date_to": date_to,
            "candidate_limit": candidate_limit,
            "created_at": existing.get("created_at", now),
            "updated_at": now,
        }
        payload["saved_searches"][search_id] = item
        self._write(payload)
        return dict(item)

    def list_saved_searches(self, profile_id: str | None = None) -> list[dict[str, Any]]:
        rows = []
        for item in self.read()["saved_searches"].values():
            if profile_id is not None and item.get("profile_id") != profile_id:
                continue
            rows.append(dict(item))
        rows.sort(key=lambda item: (str(item.get("label", "")), str(item.get("search_id", ""))))
        return rows

    def get_saved_search(self, search_id: str) -> dict[str, Any] | None:
        item = self.read()["saved_searches"].get(search_id)
        return dict(item) if isinstance(item, dict) else None

    def delete_saved_search(self, search_id: str) -> bool:
        payload = self.read()
        deleted = payload["saved_searches"].pop(search_id, None) is not None
        payload["runs"].pop(search_id, None)
        if deleted:
            self._write(payload)
        return deleted

    @staticmethod
    def _candidate_key(candidate: dict[str, Any]) -> str:
        return stable_id(
            {
                "lawd_code": candidate.get("lawd_code"),
                "complex_name": normalize_name(str(candidate.get("complex_name", ""))),
                "transaction_type": candidate.get("transaction_type"),
            }
        )[:24]

    @classmethod
    def _snapshot_candidates(cls, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for rank, candidate in enumerate(candidates, start=1):
            facts = candidate.get("facts", {})
            score = candidate.get("score", {})
            rows.append(
                {
                    "candidate_key": cls._candidate_key(candidate),
                    "rank": rank,
                    "lawd_code": candidate.get("lawd_code"),
                    "region_name": candidate.get("region_name"),
                    "complex_name": candidate.get("complex_name"),
                    "transaction_type": candidate.get("transaction_type"),
                    "match_score": score.get("match_score"),
                    "confidence_score": score.get("confidence_score"),
                    "reference_price_10k_krw": facts.get("reference_price_10k_krw"),
                    "transaction_count": facts.get("transaction_count"),
                    "latest_contract_date": facts.get("latest_contract_date"),
                }
            )
        return rows

    def record_run(
        self,
        *,
        search_id: str,
        candidates: list[dict[str, Any]],
        query_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = self.read()
        if search_id not in payload["saved_searches"]:
            raise ValueError(f"saved search not found: {search_id}")
        run = {
            "run_id": str(uuid.uuid4()),
            "search_id": search_id,
            "ran_at": self._now(),
            "query_context": query_context or {},
            "candidates": self._snapshot_candidates(candidates),
        }
        payload["runs"][search_id] = run
        self._write(payload)
        return dict(run)

    def get_last_run(self, search_id: str) -> dict[str, Any] | None:
        run = self.read()["runs"].get(search_id)
        return dict(run) if isinstance(run, dict) else None

    @staticmethod
    def diff_runs(
        previous: dict[str, Any] | None,
        current_candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        current = HomeFinderStore._snapshot_candidates(current_candidates)
        old_rows = previous.get("candidates", []) if previous else []
        old_map = {row["candidate_key"]: row for row in old_rows}
        new_map = {row["candidate_key"]: row for row in current}
        events: list[dict[str, Any]] = []

        for key, row in new_map.items():
            old = old_map.get(key)
            if old is None:
                events.append({"type": "CANDIDATE_ADDED", "candidate": row})
                continue
            if old.get("rank") != row.get("rank"):
                events.append(
                    {
                        "type": "RANK_CHANGED",
                        "candidate": row,
                        "previous_rank": old.get("rank"),
                        "current_rank": row.get("rank"),
                    }
                )
            old_price = old.get("reference_price_10k_krw")
            new_price = row.get("reference_price_10k_krw")
            if old_price is not None and new_price is not None and old_price != new_price:
                events.append(
                    {
                        "type": "REFERENCE_PRICE_CHANGED",
                        "candidate": row,
                        "previous_price_10k_krw": old_price,
                        "current_price_10k_krw": new_price,
                        "change_10k_krw": new_price - old_price,
                    }
                )
            if old.get("transaction_count") != row.get("transaction_count"):
                events.append(
                    {
                        "type": "TRANSACTION_COUNT_CHANGED",
                        "candidate": row,
                        "previous_count": old.get("transaction_count"),
                        "current_count": row.get("transaction_count"),
                    }
                )

        for key, row in old_map.items():
            if key not in new_map:
                events.append({"type": "CANDIDATE_REMOVED", "candidate": row})

        order = {
            "CANDIDATE_ADDED": 0,
            "REFERENCE_PRICE_CHANGED": 1,
            "TRANSACTION_COUNT_CHANGED": 2,
            "RANK_CHANGED": 3,
            "CANDIDATE_REMOVED": 4,
        }
        events.sort(
            key=lambda item: (
                order.get(item["type"], 99),
                item.get("candidate", {}).get("rank") or 9999,
                item.get("candidate", {}).get("complex_name") or "",
            )
        )
        return events
