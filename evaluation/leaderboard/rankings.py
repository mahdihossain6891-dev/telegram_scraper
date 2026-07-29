"""Leaderboard — historical rankings."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from evaluation.history.store import HistoryStore


class Leaderboard:
    CATEGORIES = (
        "keyword",
        "risk",
        "behavior",
        "relationship",
        "alert",
        "sebastian",
        "pipeline",
        "overall",
    )

    def __init__(self, history: HistoryStore) -> None:
        self._history = history

    def rankings(self) -> dict[str, list[dict[str, Any]]]:
        best: dict[str, tuple[float, dict[str, Any]]] = {}
        category_scores: dict[str, list[tuple[float, str, str]]] = defaultdict(list)
        for record in self._history._records:
            iqs = record.iqs
            entry = {
                "benchmark_id": record.benchmark_id,
                "version": record.version,
                "iqs": iqs,
                "created_at": record.created_at.isoformat(),
            }
            if "overall" not in best or iqs > best["overall"][0]:
                best["overall"] = (iqs, entry)
            subsystems = (record.results.get("subsystems") or {})
            for cat in self.CATEGORIES:
                if cat == "overall":
                    continue
                score = float((subsystems.get(cat) or {}).get("score") or 0)
                category_scores[cat].append((score, record.benchmark_id, record.version))
        out: dict[str, list[dict[str, Any]]] = {}
        for cat, scores in category_scores.items():
            ranked = sorted(scores, key=lambda x: x[0], reverse=True)[:10]
            out[cat] = [
                {"score": s, "benchmark_id": bid, "version": ver, "rank": i + 1}
                for i, (s, bid, ver) in enumerate(ranked)
            ]
        if "overall" in best:
            out["overall"] = [{**best["overall"][1], "rank": 1, "score": best["overall"][0]}]
        return out
