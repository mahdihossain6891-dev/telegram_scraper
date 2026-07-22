"""Evidence validation before LLM explain — fail soft with reports, not hard abort."""

from __future__ import annotations

from typing import Any

from ai.investigation.context import InvestigationContext


def validate_investigation_evidence(ctx: InvestigationContext) -> dict[str, Any]:
    """Validate evidence package and assign confidence where missing.

    Returns a validation report attached to workflow metadata.
    """
    issues: list[str] = []
    warnings: list[str] = []
    evidence = list(ctx.evidence or [])

    # Dedup labels / source ids
    seen_labels: set[str] = set()
    seen_sources: set[str] = set()
    cleaned: list[dict[str, Any]] = []
    for item in evidence:
        label = str(item.get("label") or "")
        source = str(item.get("source_id") or item.get("chunk_id") or "")
        if label and label in seen_labels:
            warnings.append(f"Duplicate citation label removed: {label}")
            continue
        if source and source in seen_sources:
            warnings.append(f"Duplicate source removed: {source}")
            continue
        if label:
            seen_labels.add(label)
        if source:
            seen_sources.add(source)

        if not item.get("snippet") and not item.get("text"):
            warnings.append(f"Evidence {label or source or '?'} missing snippet")
        if not item.get("timestamp"):
            warnings.append(f"Evidence {label or source or '?'} missing timestamp")
            item = {**item, "timestamp": item.get("timestamp") or "unknown"}

        # Citation validity: labels should look like [E#] or E#
        if label and not (
            label.startswith("[E") or label.startswith("E") or label.startswith("e")
        ):
            # Still allow — just note.
            warnings.append(f"Nonstandard citation label: {label}")

        # Assign confidence if missing
        if "confidence" not in item or item.get("confidence") is None:
            item = {**item, "confidence": _estimate_item_confidence(item)}

        cleaned.append(item)

    # Orphan relationships — edges without endpoints
    orphans = 0
    for edge in ctx.relationships or []:
        if not isinstance(edge, dict):
            continue
        if not (edge.get("source") or edge.get("from") or edge.get("user_id")) and not (
            edge.get("target") or edge.get("to") or edge.get("peer_id")
        ):
            orphans += 1
    if orphans:
        warnings.append(f"{orphans} relationship edge(s) missing endpoints")

    # Mixed environments (live vs simulation) if flagged on evidence
    envs = {
        str(i.get("environment")).lower()
        for i in cleaned
        if i.get("environment")
    }
    if len(envs) > 1:
        issues.append(f"Mixed environments in evidence: {sorted(envs)}")

    ctx.evidence = cleaned
    ok = len(issues) == 0
    report = {
        "ok": ok,
        "issues": issues,
        "warnings": warnings,
        "evidence_count": len(cleaned),
        "duplicate_labels_removed": len(evidence) - len(cleaned),
        "critical": bool(issues),
    }
    ctx.metadata["evidence_validation"] = report
    return report


def _estimate_item_confidence(item: dict[str, Any]) -> float:
    score = 0.5
    if item.get("timestamp") and item.get("timestamp") != "unknown":
        score += 0.15
    if item.get("snippet") or item.get("text"):
        score += 0.15
    if item.get("source_id") or item.get("chunk_id"):
        score += 0.1
    rs = item.get("score")
    if isinstance(rs, (int, float)):
        score += min(0.2, float(rs))
    return round(min(1.0, score), 3)
