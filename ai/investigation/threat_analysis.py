"""Enterprise threat intelligence analysis for investigations.

Deterministic SOC-style reasoning layer — runs before the LLM explain step.
Separates keyword detection from intent, scores false positives, and produces
analyst-grade structured reports without inventing evidence.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from ai.investigation.context import InvestigationContext
from risk_scoring import score_message

IntentClass = Literal[
    "Selling",
    "Buying",
    "Distribution",
    "Recruitment",
    "Coordination",
    "Threatening",
    "Educational/reference",
    "News/reporting",
    "Keyword/test data",
    "Unknown",
]

ActivityAssessment = Literal[
    "malicious",
    "suspicious",
    "informational",
    "unknown",
]

RiskBand = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
Priority = Literal["Low", "Medium", "High", "Critical"]

# Transaction / operational language (intent signals).
_SELL_PATTERNS = (
    r"\bfor sale\b",
    r"\bselling\b",
    r"\bavailable\b",
    r"\bdm me\b",
    r"\bpm for\b",
    r"\bprice\b",
    r"\$\d+",
    r"\bdelivery\b",
    r"\bships?\b",
)
_BUY_PATTERNS = (r"\blooking for\b", r"\bwant to buy\b", r"\bneed to buy\b", r"\bpurchas")
_DIST_PATTERNS = (r"\bdistribut", r"\bbulk\b", r"\bsupply\b", r"\bwholesale\b")
_RECRUIT_PATTERNS = (r"\bjoin us\b", r"\brecruit", r"\bhiring\b")
_COORD_PATTERNS = (
    r"\bmeet at\b",
    r"\bpick up\b",
    r"\brendezvous\b",
    r"\bcoordinate\b",
    r"\bhandoff\b",
)
_THREAT_PATTERNS = (
    r"\bkill\b",
    r"\battack\b",
    r"\bbomb\b",
    r"\bshoot\b",
    r"\bharm\b",
    r"\bthreaten",
)
_EDU_PATTERNS = (
    r"\bdictionary\b",
    r"\bglossary\b",
    r"\breference\b",
    r"\bresearch\b",
    r"\bawareness\b",
    r"\beducational\b",
    r"\barticle\b",
    r"\bdefinition\b",
    r"\bmonitoring\b",
    r"\bkeyword list\b",
    r"\btest data\b",
    r"\btraining material\b",
)
_NEWS_PATTERNS = (
    r"\bbreaking\b",
    r"\breported\b",
    r"\baccording to\b",
    r"\bnews\b",
    r"\bpress release\b",
)

_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "narcotics": (
        "meth",
        "methamphetamine",
        "heroin",
        "cocaine",
        "fentanyl",
        "opioid",
        "narcotic",
        "drug",
        "drugs",
    ),
    "firearms": (
        "gun",
        "guns",
        "firearm",
        "firearms",
        "weapon",
        "weapons",
        "ak-47",
        "ak47",
        "ammunition",
    ),
    "trafficking": (
        "trafficking",
        "smuggling",
        "human trafficking",
        "sex trafficking",
    ),
    "fraud": ("passport", "fake id", "counterfeit", "scam"),
}


def _match_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(p, text, re.I) for p in patterns)


def _intent_from_text(text: str) -> tuple[IntentClass, int, str]:
    """Classify message intent and return (intent, confidence 0-100, reason)."""
    t = (text or "").strip()
    if not t:
        return "Unknown", 10, "Empty message text."

    if _match_any(t, _EDU_PATTERNS):
        return "Educational/reference", 82, "Reference or monitoring language detected."
    if _match_any(t, _NEWS_PATTERNS):
        return "News/reporting", 78, "News or reporting language detected."
    if _match_any(t, _THREAT_PATTERNS):
        return "Threatening", 75, "Threat-related language detected."
    if _match_any(t, _SELL_PATTERNS):
        return "Selling", 72, "Transaction or sales language detected."
    if _match_any(t, _BUY_PATTERNS):
        return "Buying", 68, "Purchase-seeking language detected."
    if _match_any(t, _DIST_PATTERNS):
        return "Distribution", 70, "Distribution or supply language detected."
    if _match_any(t, _RECRUIT_PATTERNS):
        return "Recruitment", 65, "Recruitment language detected."
    if _match_any(t, _COORD_PATTERNS):
        return "Coordination", 68, "Coordination or meetup language detected."

    # Keyword-only mention without operational language.
    lowered = t.lower()
    if any(kw in lowered for kws in _CATEGORY_KEYWORDS.values() for kw in kws):
        return "Unknown", 35, "Category keywords present without operational intent language."

    return "Unknown", 20, "No clear intent indicators in message text."


def _detect_categories(text: str, keywords: list[str] | None = None) -> list[dict[str, Any]]:
    lowered = (text or "").lower()
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    tokens = [str(k).lower() for k in (keywords or []) if k]
    for cat, kws in _CATEGORY_KEYWORDS.items():
        matched = [kw for kw in kws if kw in lowered or kw in tokens]
        if not matched:
            continue
        if cat in seen:
            continue
        seen.add(cat)
        intent, conf, reason = _intent_from_text(text)
        hits.append(
            {
                "category": cat.title(),
                "detection": matched[0],
                "threat_type": "Keyword mention",
                "intent": intent,
                "confidence_pct": conf,
                "evidence": f"Matched: {', '.join(matched[:3])}. {reason}",
            }
        )
    return hits


def _risk_band(score: int) -> RiskBand:
    s = max(0, min(100, int(score)))
    if s <= 20:
        return "LOW"
    if s <= 50:
        return "MEDIUM"
    if s <= 75:
        return "HIGH"
    return "CRITICAL"


def _priority_from_band(band: RiskBand) -> Priority:
    return {"LOW": "Low", "MEDIUM": "Medium", "HIGH": "High", "CRITICAL": "Critical"}[band]


@dataclass(slots=True)
class ThreatReport:
    """Structured enterprise threat intelligence report."""

    subject_overview: dict[str, Any] = field(default_factory=dict)
    executive_summary: str = ""
    activity_assessment: ActivityAssessment = "unknown"
    detection_reason: str = ""
    evidence_analysis: list[dict[str, Any]] = field(default_factory=list)
    false_positive_assessment: dict[str, Any] = field(default_factory=dict)
    risk_scores: dict[str, Any] = field(default_factory=dict)
    behavioral_analysis: dict[str, Any] = field(default_factory=dict)
    network_analysis: dict[str, Any] = field(default_factory=dict)
    threat_categories: list[dict[str, Any]] = field(default_factory=list)
    analyst_recommendation: dict[str, Any] = field(default_factory=dict)
    confidence_level: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _personnel_data(ctx: InvestigationContext) -> dict[str, Any]:
    for t in ctx.tool_results:
        if t.name == "personnel" and t.ok:
            return dict(t.data or {})
    return {}


def _build_subject_overview(ctx: InvestigationContext) -> dict[str, Any]:
    subject = dict(ctx.subject or {})
    personnel = _personnel_data(ctx)
    behavior = dict(ctx.behavior or {})
    timeline = list(ctx.timeline or [])

    message_count = (
        personnel.get("message_count")
        or behavior.get("metrics", {}).get("message_count")
        or len(ctx.evidence)
    )
    groups = personnel.get("groups") or []
    group_count = len(groups) if groups else len(
        {e.get("chat_id") for e in ctx.relationships if e.get("chat_id")}
    )

    first_seen = (
        personnel.get("first_seen")
        or behavior.get("first_seen")
        or (timeline[0].get("timestamp") if timeline else None)
    )
    last_seen = (
        personnel.get("last_seen")
        or behavior.get("last_seen")
        or (timeline[-1].get("timestamp") if timeline else None)
    )

    return {
        "identity": {
            "telegram_id": subject.get("user_id") or subject.get("chat_id"),
            "username": subject.get("username") or personnel.get("username"),
            "display_name": subject.get("display_name") or personnel.get("display_name"),
            "subject_type": subject.get("subject_type") or (
                "user" if subject.get("user_id") else "chat" if subject.get("chat_id") else "unknown"
            ),
        },
        "activity_summary": {
            "messages_analyzed": message_count,
            "groups_channels_involved": group_count,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "evidence_items": len(ctx.evidence),
        },
    }


def _analyze_evidence_item(item: dict[str, Any], index: int) -> dict[str, Any]:
    text = str(item.get("snippet") or item.get("text") or "")
    keywords = list(item.get("keywords") or [])
    intent, conf, reason = _intent_from_text(text)

    # Boost confidence when keywords align with transaction language.
    if keywords and intent in {"Selling", "Buying", "Distribution", "Coordination"}:
        conf = min(95, conf + 10)

    # Score from keyword weights when available.
    if keywords:
        scored = score_message(keywords=keywords, text=text)
        detection_strength = scored.score
    else:
        detection_strength = 15 if text else 0

    discusses_illegal = intent in {
        "Selling",
        "Buying",
        "Distribution",
        "Recruitment",
        "Coordination",
        "Threatening",
    }
    advertising = intent == "Selling"
    keyword_only = bool(keywords) and intent in {
        "Unknown",
        "Educational/reference",
        "News/reporting",
        "Keyword/test data",
    }

    return {
        "label": item.get("label") or f"[E{index}]",
        "message": text[:500],
        "timestamp": item.get("timestamp"),
        "chat": item.get("group_name") or item.get("chat_id") or item.get("chat_title"),
        "sender": item.get("sender_id") or item.get("sender_display_name"),
        "intent_classification": intent,
        "intent_confidence_pct": conf,
        "intent_reason": reason,
        "context_analysis": {
            "discusses_illegal_activity": discusses_illegal,
            "advertising": advertising,
            "communicating_with_others": bool(item.get("reply_to") or item.get("forward_from")),
            "keyword_match_only": keyword_only,
            "evidence_of_intent": discusses_illegal and conf >= 60,
        },
        "detection_strength": detection_strength,
        "keywords": keywords[:8],
    }


def _false_positive_assessment(
    ctx: InvestigationContext,
    evidence_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    indicators: list[str] = []
    fp_score = 0  # higher = more likely false positive

    edu_count = sum(
        1
        for e in evidence_rows
        if e.get("intent_classification")
        in {"Educational/reference", "News/reporting", "Keyword/test data"}
    )
    keyword_only = sum(
        1 for e in evidence_rows if e.get("context_analysis", {}).get("keyword_match_only")
    )
    operational = sum(
        1 for e in evidence_rows if e.get("context_analysis", {}).get("evidence_of_intent")
    )

    if edu_count and edu_count >= len(evidence_rows) / 2:
        fp_score += 35
        indicators.append("Research or reference content")
    if keyword_only and not operational:
        fp_score += 30
        indicators.append("Keyword list only — no transaction language")
    if len(ctx.evidence) <= 2:
        fp_score += 15
        indicators.append("Very low message volume")
    if not ctx.relationships or len(ctx.relationships) <= 1:
        fp_score += 10
        indicators.append("No coordinated network activity")
    behavior_score = (ctx.behavior or {}).get("behavior_score")
    if behavior_score is not None and int(behavior_score) < 25:
        fp_score += 10
        indicators.append("Low behavioral anomaly score")

    likely_fp = fp_score >= 40 and operational == 0
    summary_parts = []
    if likely_fp:
        summary_parts.append(
            "Keyword detections are present but operational threat indicators are absent."
        )
    elif operational:
        summary_parts.append(
            "Some messages show operational language beyond keyword matching."
        )
    else:
        summary_parts.append(
            "Insufficient evidence to confirm malicious intent; treat as monitoring signal."
        )

    if indicators:
        summary_parts.append(
            "Factors: " + "; ".join(indicators) + "."
        )

    return {
        "likely_false_positive": likely_fp,
        "false_positive_score": min(100, fp_score),
        "adjustment": -min(60, fp_score),
        "indicators": indicators,
        "summary": " ".join(summary_parts),
        "categories": {
            "keyword_list_only": keyword_only > 0 and operational == 0,
            "research_content": edu_count > 0,
            "actual_suspicious_communication": operational > 0,
        },
    }


def _compute_risk_scores(
    ctx: InvestigationContext,
    evidence_rows: list[dict[str, Any]],
    fp: dict[str, Any],
) -> dict[str, Any]:
    risk = dict(ctx.risk or {})
    detection = int(risk.get("risk_score") or 0)
    if not detection and evidence_rows:
        detection = max(int(e.get("detection_strength") or 0) for e in evidence_rows)

    behavior = int((ctx.behavior or {}).get("behavior_score") or 0)
    if not behavior and ctx.behavior:
        behavior = 10

    # Network: edges + suspicious group signals.
    edges = list(ctx.relationships or [])
    suspicious_edges = sum(
        1 for e in edges if int(e.get("suspicious_count") or 0) > 0
    )
    network = min(100, len(edges) * 8 + suspicious_edges * 15)
    if len(edges) <= 1:
        network = min(network, 15)

    # Intent: average malicious intent confidence.
    malicious_intents = {
        "Selling",
        "Buying",
        "Distribution",
        "Recruitment",
        "Coordination",
        "Threatening",
    }
    intent_scores = [
        int(e.get("intent_confidence_pct") or 0)
        for e in evidence_rows
        if e.get("intent_classification") in malicious_intents
    ]
    intent = int(sum(intent_scores) / len(intent_scores)) if intent_scores else 5

    fp_adj = int(fp.get("adjustment") or 0)
    raw = detection + behavior + network + intent + fp_adj
    final = max(0, min(100, raw))
    band = _risk_band(final)

    explanation = (
        f"Detection score reflects keyword/category matches ({detection}). "
        f"Behavior score reflects account activity patterns ({behavior}). "
        f"Network score reflects relationship exposure ({network}). "
        f"Intent score reflects message meaning analysis ({intent}). "
        f"False positive adjustment ({fp_adj}). "
    )
    if band in {"LOW", "MEDIUM"} and detection >= 40:
        explanation += (
            "Keyword detection exists but no strong evidence of criminal intent."
        )
    elif band in {"HIGH", "CRITICAL"}:
        explanation += "Multiple indicators suggest elevated threat requiring analyst review."
    else:
        explanation += "Overall posture is within normal monitoring thresholds."

    return {
        "detection_score": detection,
        "behavior_score": behavior,
        "network_score": network,
        "intent_score": intent,
        "false_positive_adjustment": fp_adj,
        "final_score": final,
        "risk_band": band,
        "risk_level": band.title(),
        "explanation": explanation,
        "calculation": (
            f"{detection} (detection) + {behavior} (behavior) + {network} (network) "
            f"+ {intent} (intent) {fp_adj} (FP adj) = {final} {band}"
        ),
    }


def _behavioral_analysis(ctx: InvestigationContext) -> dict[str, Any]:
    behavior = dict(ctx.behavior or {})
    metrics = dict(behavior.get("metrics") or {})
    findings: list[str] = []

    msg_count = metrics.get("message_count")
    if msg_count is not None:
        findings.append(f"Message volume: {msg_count} flagged message(s) analyzed.")
    elif ctx.evidence:
        findings.append(f"Only {len(ctx.evidence)} evidence item(s) detected.")

    night = metrics.get("night_activity_ratio") or metrics.get("night_activity_percentage")
    if night is not None:
        findings.append(f"Night activity ratio: {night}.")

    forward = metrics.get("forward_rate")
    if forward is None and isinstance(metrics.get("forwarding_rate"), dict):
        forward = metrics["forwarding_rate"].get("forward_ratio")
    if forward is not None:
        findings.append(f"Forwarding rate: {forward}.")

    status = behavior.get("behavior_status") or behavior.get("status")
    if status:
        findings.append(f"Behavior status: {status}.")

    if not ctx.alerts:
        findings.append("No behavioral alerts triggered.")
    else:
        findings.append(f"{len(ctx.alerts)} behavioral alert(s) on record.")

    if len(ctx.evidence) <= 2:
        findings.append("Activity volume is low.")
    if not any(
        e.get("type") == "coordination" for e in (ctx.alerts or [])
    ):
        findings.append("No evidence of coordination patterns in behavioral alerts.")

    trend = behavior.get("trend") or behavior.get("behavior_trend")
    summary = (
        f"Behavior score {behavior.get('behavior_score', '—')} "
        f"({status or 'unknown status'}). "
        + (" ".join(findings[:4]) if findings else "Limited behavioral data available.")
    )

    return {
        "behavior_score": behavior.get("behavior_score"),
        "behavior_status": status,
        "trend": trend,
        "findings": findings,
        "summary": summary.strip(),
    }


def _network_analysis(ctx: InvestigationContext) -> dict[str, Any]:
    edges = list(ctx.relationships or [])
    groups = {e.get("chat_id") for e in edges if e.get("chat_id")}
    suspicious = [e for e in edges if int(e.get("suspicious_count") or 0) > 0]

    if not edges:
        summary = (
            "No relationship edges were retrieved. Network exposure cannot be assessed "
            "from available data."
        )
    elif len(edges) == 1:
        title = edges[0].get("title") or edges[0].get("chat_id") or "one group"
        summary = (
            f"The subject has one relationship edge ({title}) with no additional "
            "suspicious accounts identified. No coordinated activity detected."
        )
    else:
        summary = (
            f"The subject appears in {len(groups)} shared chat(s) with {len(edges)} "
            f"relationship edge(s). "
        )
        if suspicious:
            summary += f"{len(suspicious)} edge(s) include suspicious message counts."
        else:
            summary += "No coordinated suspicious activity detected across edges."

    return {
        "edge_count": len(edges),
        "group_count": len(groups),
        "suspicious_edges": len(suspicious),
        "edges": edges[:12],
        "summary": summary,
    }


def _executive_summary(
    ctx: InvestigationContext,
    overview: dict[str, Any],
    risk: dict[str, Any],
    fp: dict[str, Any],
    evidence_rows: list[dict[str, Any]],
) -> tuple[str, ActivityAssessment, str]:
    identity = overview.get("identity") or {}
    name = (
        identity.get("display_name")
        or (f"@{identity['username']}" if identity.get("username") else None)
        or f"ID {identity.get('telegram_id')}"
    )
    band = risk.get("risk_band", "LOW")
    detection = risk.get("detection_score", 0)

    categories: set[str] = set()
    for row in evidence_rows:
        for cat in _detect_categories(row.get("message", ""), row.get("keywords")):
            categories.add(cat["category"].lower())

    cat_text = ", ".join(sorted(categories)) if categories else "monitored categories"
    detection_reason = f"Triggered {cat_text} keyword detection."

    if fp.get("likely_false_positive"):
        assessment: ActivityAssessment = "informational"
        body = (
            f"The account {name} triggered {cat_text}-related keyword detection. "
            "However, analysis indicates the messages contain reference or monitoring "
            "material rather than evidence of selling, distribution, recruitment, or "
            "coordination. No malicious behavioral patterns were identified."
        )
    elif risk.get("intent_score", 0) >= 60:
        assessment = "suspicious" if band in {"MEDIUM", "HIGH"} else "malicious"
        body = (
            f"The account {name} shows {detection_reason.lower()} "
            "Message analysis identified operational language suggesting "
            f"{assessment} activity. Analyst review is recommended."
        )
    elif detection >= 40:
        assessment = "suspicious"
        body = (
            f"The account {name} triggered keyword detection ({cat_text}). "
            "Intent remains unclear — messages match category terms without confirmed "
            "transaction or coordination language. Continue monitoring."
        )
    else:
        assessment = "unknown"
        body = (
            f"Limited monitored evidence for {name}. "
            "Insufficient data for a definitive threat determination."
        )

    summary = f"{body} Overall assessment: {band} risk ({risk.get('final_score', 0)}/100)."
    return summary, assessment, detection_reason


def _threat_categories(evidence_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in evidence_rows:
        cats = _detect_categories(row.get("message", ""), row.get("keywords"))
        for cat in cats:
            key = f"{cat['category']}:{cat['detection']}"
            if key in seen:
                continue
            seen.add(key)
            out.append(cat)
    return out


def _analyst_recommendation(risk: dict[str, Any], fp: dict[str, Any]) -> dict[str, Any]:
    band = risk.get("risk_band", "LOW")
    priority = _priority_from_band(band)  # type: ignore[arg-type]

    actions = {
        "LOW": "Continue monitoring. No immediate action required.",
        "MEDIUM": "Review future messages and validate keyword context.",
        "HIGH": "Investigate related accounts and expand evidence collection.",
        "CRITICAL": "Immediate escalation to senior analyst and incident response.",
    }
    triggers = [
        "Transaction or sales language appears in new messages",
        "Multiple related suspicious accounts are detected",
        "Repeated suspicious communication or coordination patterns emerge",
        "Behavioral score rises above monitoring baseline",
    ]
    if fp.get("likely_false_positive"):
        triggers.insert(0, "Operational intent language replaces reference-only content")

    return {
        "priority": priority,
        "recommended_action": actions.get(band, actions["LOW"]),
        "escalation_triggers": triggers,
    }


def run_threat_analysis(ctx: InvestigationContext) -> ThreatReport:
    """Build enterprise threat intelligence report from investigation context."""
    overview = _build_subject_overview(ctx)
    evidence_rows = [
        _analyze_evidence_item(item, i + 1) for i, item in enumerate(ctx.evidence or [])
    ]
    fp = _false_positive_assessment(ctx, evidence_rows)
    risk = _compute_risk_scores(ctx, evidence_rows, fp)
    behavior = _behavioral_analysis(ctx)
    network = _network_analysis(ctx)
    exec_summary, assessment, detection_reason = _executive_summary(
        ctx, overview, risk, fp, evidence_rows
    )
    categories = _threat_categories(evidence_rows)
    recommendation = _analyst_recommendation(risk, fp)

    conf_score = min(95, max(15, 30 + len(ctx.evidence) * 8 + (20 if ctx.findings else 0)))
    if fp.get("likely_false_positive"):
        conf_reason = "High confidence that keyword hits are reference/monitoring content."
    elif risk.get("intent_score", 0) >= 60:
        conf_reason = "Intent signals support the threat assessment."
    else:
        conf_reason = "Assessment limited by sparse or ambiguous evidence."

    return ThreatReport(
        subject_overview=overview,
        executive_summary=exec_summary,
        activity_assessment=assessment,
        detection_reason=detection_reason,
        evidence_analysis=evidence_rows,
        false_positive_assessment=fp,
        risk_scores=risk,
        behavioral_analysis=behavior,
        network_analysis=network,
        threat_categories=categories,
        analyst_recommendation=recommendation,
        confidence_level={
            "score_pct": conf_score,
            "label": "high" if conf_score >= 70 else "medium" if conf_score >= 45 else "low",
            "reason": conf_reason,
        },
    )


def format_threat_report_markdown(report: ThreatReport) -> str:
    """Render analyst report as markdown for UI / no-LLM fallback."""
    ov = report.subject_overview
    identity = ov.get("identity") or {}
    activity = ov.get("activity_summary") or {}
    risk = report.risk_scores
    fp = report.false_positive_assessment
    rec = report.analyst_recommendation
    conf = report.confidence_level

    lines = [
        "# Investigation Report",
        "",
        "## Executive Summary",
        report.executive_summary,
        f"Activity assessment: **{report.activity_assessment}**.",
        "",
        "## Subject Information",
        f"- **Telegram ID:** {identity.get('telegram_id') or '—'}",
        f"- **Username:** {identity.get('username') or '—'}",
        f"- **Display name:** {identity.get('display_name') or '—'}",
        f"- **Messages analyzed:** {activity.get('messages_analyzed') or '—'}",
        f"- **Groups/channels:** {activity.get('groups_channels_involved') or '—'}",
        f"- **First seen:** {activity.get('first_seen') or '—'}",
        f"- **Last seen:** {activity.get('last_seen') or '—'}",
        "",
        "## Risk Assessment",
        f"- **Detection Score:** {risk.get('detection_score')}",
        f"- **Behavior Score:** {risk.get('behavior_score')}",
        f"- **Network Score:** {risk.get('network_score')}",
        f"- **Intent Score:** {risk.get('intent_score')}",
        f"- **False Positive Adjustment:** {risk.get('false_positive_adjustment')}",
        f"- **Final Risk Score:** {risk.get('final_score')} ({risk.get('risk_band')})",
        f"- **Explanation:** {risk.get('explanation')}",
        "",
        "## Evidence Analysis",
    ]

    if not report.evidence_analysis:
        lines.append("No message evidence available for intent analysis.")
    else:
        for row in report.evidence_analysis:
            lines.extend(
                [
                    f"### {row.get('label')}",
                    f"- **Timestamp:** {row.get('timestamp') or '—'}",
                    f"- **Chat:** {row.get('chat') or '—'}",
                    f"- **Sender:** {row.get('sender') or '—'}",
                    f"- **Message:** {row.get('message') or '—'}",
                    f"- **Intent:** {row.get('intent_classification')} "
                    f"({row.get('intent_confidence_pct')}%)",
                    f"- **Reason:** {row.get('intent_reason')}",
                    "",
                ]
            )

    lines.extend(
        [
            "## Behavioral Analysis",
            report.behavioral_analysis.get("summary", "No behavioral data."),
            "",
        ]
    )
    for f in report.behavioral_analysis.get("findings") or []:
        lines.append(f"- {f}")
    lines.append("")

    lines.extend(
        [
            "## Network Analysis",
            report.network_analysis.get("summary", "No network data."),
            "",
            "## False Positive Assessment",
            fp.get("summary", "Not evaluated."),
            "",
            "## Threat Classification",
        ]
    )
    if report.threat_categories:
        for cat in report.threat_categories:
            lines.extend(
                [
                    f"**{cat.get('category')}** — {cat.get('detection')}",
                    f"- Threat type: {cat.get('threat_type')}",
                    f"- Intent: {cat.get('intent')}",
                    f"- Confidence: {cat.get('confidence_pct')}%",
                    f"- Evidence: {cat.get('evidence')}",
                    "",
                ]
            )
    else:
        lines.append("No category-specific threat classifications.")

    lines.extend(
        [
            "## Analyst Recommendation",
            f"- **Priority:** {rec.get('priority')}",
            f"- **Action:** {rec.get('recommended_action')}",
            "- **Escalate if:**",
        ]
    )
    for t in rec.get("escalation_triggers") or []:
        lines.append(f"  - {t}")

    lines.extend(
        [
            "",
            "## Confidence Level",
            f"{conf.get('score_pct')}% ({conf.get('label')}) — {conf.get('reason')}",
        ]
    )
    return "\n".join(lines).strip()
