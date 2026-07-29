"""Regression comparison between benchmark versions."""

from __future__ import annotations

from typing import Any


class RegressionComparator:
    IMPROVED = "improved"
    REGRESSED = "regressed"
    UNCHANGED = "unchanged"

    def compare(self, baseline: dict[str, Any], candidate: dict[str, Any], *, threshold: float = 1.0) -> dict[str, Any]:
        base_iqs = float((baseline.get("iqs") or {}).get("iqs") or baseline.get("iqs") or 0)
        cand_iqs = float((candidate.get("iqs") or {}).get("iqs") or candidate.get("iqs") or 0)
        delta = cand_iqs - base_iqs
        if delta > threshold:
            verdict = self.IMPROVED
        elif delta < -threshold:
            verdict = self.REGRESSED
        else:
            verdict = self.UNCHANGED
        subsystems: dict[str, dict[str, Any]] = {}
        base_sub = (baseline.get("subsystems") or baseline.get("results", {}).get("subsystems") or {})
        cand_sub = (candidate.get("subsystems") or candidate.get("results", {}).get("subsystems") or {})
        for name in set(base_sub) | set(cand_sub):
            b_score = float((base_sub.get(name) or {}).get("score") or 0)
            c_score = float((cand_sub.get(name) or {}).get("score") or 0)
            d = c_score - b_score
            if d > threshold:
                status = self.IMPROVED
            elif d < -threshold:
                status = self.REGRESSED
            else:
                status = self.UNCHANGED
            subsystems[name] = {"baseline": b_score, "candidate": c_score, "delta": round(d, 2), "status": status}
        return {
            "verdict": verdict,
            "iqs_delta": round(delta, 2),
            "baseline_iqs": base_iqs,
            "candidate_iqs": cand_iqs,
            "subsystems": subsystems,
        }
