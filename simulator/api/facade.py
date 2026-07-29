"""Threat Simulation console facade — read-only over simulator, never production."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from simulator.enums import EnvironmentType
from simulator.execution.config import ExecutionConfig
from simulator.execution.engine import SimulationExecutionEngine
from simulator.execution.labels import SessionStatus, TickInterval
from simulator.generation_config import GenerationConfig, english_only_language_distribution
from simulator.manager import SimulationManager
from simulator.scenario.config import ScenarioConfig
from simulator.constants import SIM_TELEGRAM_CHAT_ID_BASE

_SIM_RISK_LEVEL_MAP = {
    "normal": "Low",
    "low": "Low",
    "elevated": "Medium",
    "medium": "Medium",
    "high": "High",
    "critical": "Critical",
}

_KEYWORD_ENTITY_TYPES = frozenset({"narcotics", "firearms", "human_trafficking"})


def _normalize_export_risk(level: str | None, score: float | int | None) -> tuple[int, str]:
    scaled = 0
    if score is not None:
        try:
            numeric = float(score)
        except (TypeError, ValueError):
            numeric = 0.0
        scaled = int(round(numeric * 100)) if numeric <= 1.0 else int(round(numeric))
        scaled = max(0, min(100, scaled))
    if level:
        mapped = _SIM_RISK_LEVEL_MAP.get(str(level).strip().lower())
        if mapped:
            if scaled == 0:
                scaled = {"Low": 10, "Medium": 35, "High": 60, "Critical": 85}[mapped]
            return scaled, mapped
    if scaled == 0:
        return 0, "Low"
    if scaled >= 71:
        return scaled, "Critical"
    if scaled >= 41:
        return scaled, "High"
    if scaled >= 21:
        return scaled, "Medium"
    return scaled, "Low"


def _keyword_entities_for_text(
    text: str | None,
    *,
    message_row_id: int,
    timestamp: Any,
    start_id: int,
) -> tuple[list[dict[str, Any]], int]:
    from keyword_filter import scan_message_text

    entities: list[dict[str, Any]] = []
    entity_id = start_id
    for hit in scan_message_text(text).hits:
        if hit.category not in _KEYWORD_ENTITY_TYPES:
            continue
        entities.append(
            {
                "id": entity_id,
                "message_row_id": message_row_id,
                "entity_type": hit.category,
                "entity_value": hit.keyword,
                "start_offset": None,
                "end_offset": None,
                "created_at": timestamp,
            }
        )
        entity_id += 1
    return entities, entity_id


@dataclass(slots=True)
class ConsoleSessionRecord:
    """In-memory simulation session for the Threat Simulation module."""

    session_id: str
    name: str
    engine: SimulationExecutionEngine
    created_at: datetime
    messages: list[dict[str, Any]] = field(default_factory=list)
    pipeline_inspections: dict[str, dict[str, Any]] = field(default_factory=dict)
    scenario_runs: list[str] = field(default_factory=list)
    status: str = "ready"
    thread: threading.Thread | None = None

    def summary(self) -> dict[str, Any]:
        session = self.engine.session
        metrics = self.engine.metrics.snapshot() if self.engine.session else {}
        return {
            "session_id": self.session_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "started_at": session.start_time.isoformat() if session and session.start_time else None,
            "ended_at": session.end_time.isoformat() if session and session.end_time else None,
            "status": session.status.value if session else self.status,
            "messages": metrics.get("messages_generated", len(self.messages)),
            "messages_processed": metrics.get("messages_processed", 0),
            "conversations": metrics.get("active_conversations", 0),
            "scenarios": len(self.scenario_runs),
            "users": session.user_count if session else 0,
            "groups": session.group_count if session else 0,
            "duration_seconds": metrics.get("session_duration_seconds", 0),
            "current_tick": session.current_tick if session else 0,
            "elapsed_simulated_seconds": session.elapsed_simulated_seconds if session else 0,
            "environment": EnvironmentType.SIMULATION.value,
        }


class SimulationConsoleFacade:
    """API facade for Threat Simulation — isolated from production monitoring."""

    def __init__(self) -> None:
        self._manager = SimulationManager()
        self._sessions: dict[str, ConsoleSessionRecord] = {}
        self._active_session_id: str | None = None
        self._default_config = self._default_generation_config()

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "module": "threat_simulation",
            "environment": EnvironmentType.SIMULATION.value,
            "simulator_enabled": self._manager.enabled,
            "simulator_state": self._manager.state.value,
            "active_session": self._active_session_id,
            "session_count": len(self._sessions),
            "isolated": True,
        }

    def overview(self, session_id: str | None = None) -> dict[str, Any]:
        record = self._resolve_session(session_id)
        if record is None:
            return self._empty_overview()
        snap = record.engine.runtime_snapshot() if record else {}
        metrics = snap.get("metrics") or {}
        resources = record.engine._resources.snapshot(queue_size=0, processing_rate=metrics.get("pipeline_throughput_per_tick", 0)) if record else {}
        session = record.engine.session if record else None
        return {
            "simulation_status": session.status.value if session else "none",
            "environment": EnvironmentType.SIMULATION.value,
            "current_session": record.summary() if record else None,
            "simulation_speed": record.engine.execution_config.simulation_speed if record else 0,
            "current_tick": session.current_tick if session else 0,
            "elapsed_seconds": session.elapsed_simulated_seconds if session else 0,
            "users": session.user_count if session else 0,
            "groups": session.group_count if session else 0,
            "conversations": metrics.get("active_conversations", 0),
            "messages_generated": metrics.get("messages_generated", 0),
            "messages_processed": metrics.get("messages_processed", 0),
            "alerts_generated": metrics.get("alerts_generated", 0),
            "cases_generated": metrics.get("cases_created", 0),
            "sebastian_index_count": 0,
            "pipeline_health": self.pipeline_health(session_id),
            "cpu_percent": resources.get("cpu_usage_percent", 0),
            "memory_mb": resources.get("memory_usage_mb", 0),
        }

    def list_sessions(self) -> list[dict[str, Any]]:
        return [r.summary() for r in sorted(self._sessions.values(), key=lambda r: r.created_at, reverse=True)]

    def create_session(self, *, name: str | None = None, config: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self._manager.enabled:
            self._manager.enable()
        gen_cfg = self._config_from_dict(config or {})
        exec_cfg = ExecutionConfig(
            max_ticks=int((config or {}).get("max_ticks", 20)),
            simulation_speed=float((config or {}).get("simulation_speed", gen_cfg.simulation_speed_multiplier)),
            tick_interval=TickInterval((config or {}).get("tick_interval", TickInterval.ONE_MINUTE.value)),
            max_messages_per_tick=int((config or {}).get("max_messages_per_tick", 5)),
            checkpoint_frequency_ticks=int((config or {}).get("checkpoint_frequency_ticks", 5)),
        )
        engine = SimulationExecutionEngine(
            execution_config=exec_cfg,
            generation_config=gen_cfg,
            scenario_config=self._scenario_config_from_dict(config or {}),
            simulation_name=name or f"sim-{uuid4().hex[:8]}",
        )
        session = engine.initialize_session()
        sid = str(session.session_id)
        record = ConsoleSessionRecord(
            session_id=sid,
            name=session.simulation_name,
            engine=engine,
            created_at=session.creation_time,
            status=session.status.value,
        )
        self._sessions[sid] = record
        self._active_session_id = sid
        self._manager.environment_manager.switch_environment(EnvironmentType.SIMULATION)
        return record.summary()

    def get_session(self, session_id: str) -> dict[str, Any]:
        return self._require_record(session_id).summary()

    def delete_session(self, session_id: str) -> dict[str, Any]:
        record = self._sessions.pop(session_id, None)
        if record is None:
            return {"deleted": False}
        record.engine.shutdown()
        if self._active_session_id == session_id:
            self._active_session_id = None
        return {"deleted": True, "session_id": session_id}

    def duplicate_session(self, session_id: str) -> dict[str, Any]:
        src = self._require_record(session_id)
        cfg = src.engine.generation_config.to_dict()
        cfg["random_seed"] = src.engine.generation_config.random_seed
        return self.create_session(name=f"{src.name}-copy", config=cfg)

    def set_active(self, session_id: str) -> dict[str, Any]:
        self._require_record(session_id)
        self._active_session_id = session_id
        return {"active_session": session_id}

    def start(self, session_id: str | None = None) -> dict[str, Any]:
        record = self._require_session(session_id)
        self._manager.start()

        def _run() -> None:
            try:
                record.engine.start()
            except Exception:
                pass
            finally:
                self._ingest_runtime(record)

        if record.thread and record.thread.is_alive():
            return {"status": "already_running", **record.summary()}
        record.thread = threading.Thread(target=_run, daemon=True)
        record.thread.start()
        return {"status": "started", **record.summary()}

    def pause(self, session_id: str | None = None) -> dict[str, Any]:
        record = self._require_session(session_id)
        record.engine.pause()
        self._manager.pause()
        return {"status": "paused", **record.summary()}

    def resume(self, session_id: str | None = None) -> dict[str, Any]:
        record = self._require_session(session_id)
        record.engine.resume()
        self._manager.resume()
        return {"status": "resumed", **record.summary()}

    def stop(self, session_id: str | None = None) -> dict[str, Any]:
        record = self._require_session(session_id)
        record.engine.stop()
        record.engine.shutdown()
        self._manager.stop()
        self._ingest_runtime(record)
        return {"status": "stopped", **record.summary()}

    def tick(self, session_id: str | None = None) -> dict[str, Any]:
        record = self._require_session(session_id)
        tick = record.engine.run_single_tick()
        self._ingest_runtime(record)
        return {
            "tick": tick.number if tick else 0,
            **record.summary(),
        }

    def scenarios(self) -> list[dict[str, Any]]:
        from simulator.scenario.registry import ScenarioRegistry

        if self._active_session_id and self._active_session_id in self._sessions:
            registry = self._sessions[self._active_session_id].engine._scenario_manager.registry
        else:
            registry = ScenarioRegistry.with_builtins()
        out = []
        for scenario in registry.all():
            gt = scenario.ground_truth.to_dict() if scenario.ground_truth else None
            out.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "name": scenario.name,
                    "category": scenario.category.value,
                    "difficulty": scenario.difficulty.value,
                    "weight": registry.weight_for(scenario.scenario_id),
                    "enabled": registry.is_enabled(scenario.scenario_id),
                    "expected_participants": list(scenario.expected_participants),
                    "expected_messages": scenario.expected_alert_count,
                    "expected_alerts": gt.get("expected_alert") if gt else False,
                    "ground_truth": gt,
                }
            )
        return out

    def update_scenario(self, scenario_id: str, *, enabled: bool | None = None, weight: float | None = None) -> dict[str, Any]:
        record = self._require_session(None)
        mgr = record.engine._scenario_manager
        if enabled is True:
            mgr.enable(scenario_id)
        elif enabled is False:
            mgr.disable(scenario_id)
        if weight is not None:
            mgr.set_weight(scenario_id, weight)
        return {"scenario_id": scenario_id, "enabled": enabled, "weight": weight}

    def personas(self, session_id: str | None = None, *, q: str = "", limit: int = 200) -> list[dict[str, Any]]:
        record = self._resolve_session(session_id)
        if record is None:
            return []
        snap = record.engine.runtime_snapshot()
        rows = []
        for p in snap.get("personas") or []:
            if q:
                hay = f"{p.get('username','')} {p.get('display_name','')}".lower()
                if q.lower() not in hay:
                    continue
            rows.append(
                {
                    "id": p.get("id"),
                    "telegram_id": p.get("telegram_id"),
                    "username": p.get("username"),
                    "display_name": p.get("display_name"),
                    "behavior_profile": p.get("activity_level"),
                    "languages": [p.get("language")],
                    "risk_profile": p.get("risk_profile"),
                    "activity_score": round(1.0 - (p.get("emoji_frequency") or 0), 2),
                    "groups": [],
                }
            )
            if len(rows) >= limit:
                break
        return rows

    def groups(self, session_id: str | None = None, *, q: str = "", limit: int = 100) -> list[dict[str, Any]]:
        record = self._resolve_session(session_id)
        if record is None:
            return []
        snap = record.engine.runtime_snapshot()
        rows = []
        for g in snap.get("groups") or []:
            if q and q.lower() not in str(g.get("name", "")).lower():
                continue
            rows.append(
                {
                    "id": g.get("id"),
                    "name": g.get("name"),
                    "category": g.get("category"),
                    "language": g.get("language"),
                    "members": g.get("current_members"),
                    "topics": g.get("topic_tags") or [],
                    "activity": g.get("activity_level"),
                    "messages": 0,
                    "creation_date": g.get("creation_date"),
                }
            )
            if len(rows) >= limit:
                break
        return rows

    def activity(self, session_id: str | None = None, *, q: str = "", limit: int = 500) -> list[dict[str, Any]]:
        record = self._resolve_session(session_id)
        if record is None:
            return []
        self._ingest_runtime(record)
        rows = list(record.messages)
        if q:
            rows = [m for m in rows if q.lower() in str(m.get("text", "")).lower()]
        return rows[-limit:]

    def to_export_payload(
        self,
        session_id: str,
        *,
        scenario: str | None = None,
    ) -> dict[str, Any]:
        """Map an in-memory simulation session to ExportPayload for the main console."""
        from collections import defaultdict
        from datetime import datetime, timezone

        record = self._require_record(session_id)
        self._ingest_runtime(record)
        snap = record.engine.runtime_snapshot()
        personas = list(snap.get("personas") or [])
        groups = list(snap.get("groups") or [])

        users: list[dict[str, Any]] = []
        personnel: list[dict[str, Any]] = []
        user_msg_counts: dict[int, int] = defaultdict(int)
        user_suspicious: dict[int, int] = defaultdict(int)
        user_keywords: dict[int, set[str]] = defaultdict(set)
        user_chats: dict[int, set[int]] = defaultdict(set)

        for i, p in enumerate(personas):
            uid = int(p.get("telegram_id") or p.get("id") or (9_000_000 + i))
            display = p.get("display_name") or p.get("username") or f"Sim User {uid}"
            users.append(
                {
                    "id": uid,
                    "username": p.get("username"),
                    "first_name": str(display).split()[0] if display else None,
                    "last_name": None,
                    "created_at": None,
                    "updated_at": None,
                }
            )
            personnel.append(
                {
                    "user_id": uid,
                    "display_name": display,
                    "username": p.get("username"),
                    "first_name": str(display).split()[0] if display else None,
                    "last_name": None,
                    "message_count": 0,
                    "suspicious_count": 0,
                    "keyword_total": 0,
                    "keyword_list": [],
                    "chat_ids": [],
                    "risk_score": _normalize_export_risk(p.get("risk_profile"), None)[0],
                    "risk_level": _normalize_export_risk(p.get("risk_profile"), None)[1],
                    "first_seen": None,
                    "last_seen": None,
                }
            )

        chats: list[dict[str, Any]] = []
        for i, g in enumerate(groups):
            raw_id = g.get("id") or g.get("group_id")
            try:
                cid = int(raw_id) if raw_id is not None else 8_000_000 + i
            except (ValueError, TypeError):
                cid = int(SIM_TELEGRAM_CHAT_ID_BASE) - i
            chats.append(
                {
                    "id": cid,
                    "title": g.get("name") or f"Group {cid}",
                    "username": None,
                    "chat_type": g.get("category") or "group",
                    "created_at": g.get("creation_date"),
                    "updated_at": None,
                    "risk_score": 0,
                    "risk_level": "Low",
                    "risk_factors": [],
                }
            )

        messages: list[dict[str, Any]] = []
        entities: list[dict[str, Any]] = []
        entity_id = 1

        for i, m in enumerate(record.messages):
            msg_key = str(m.get("message_id") or i + 1)
            inspection = record.pipeline_inspections.get(msg_key) or {}
            ctx = inspection.get("context") or {}
            keywords = list(ctx.get("keywords") or [])
            if not keywords:
                from simulator.keywords import scan_simulation_text

                keywords, _ = scan_simulation_text(m.get("text"))
            risk_score, risk_level = _normalize_export_risk(
                ctx.get("risk_level"),
                ctx.get("risk_score"),
            )
            sender_id = m.get("sender_id")
            chat_id = m.get("chat_id")
            if sender_id is not None:
                sid = int(sender_id)
                user_msg_counts[sid] += 1
                if chat_id is not None:
                    user_chats[sid].add(int(chat_id))
                if keywords:
                    user_suspicious[sid] += 1
                    user_keywords[sid].update(str(k) for k in keywords)

            messages.append(
                {
                    "id": i + 1,
                    "message_id": int(msg_key) if str(msg_key).isdigit() else i + 1,
                    "chat_id": chat_id,
                    "sender_id": sender_id,
                    "timestamp": m.get("timestamp"),
                    "text": m.get("text"),
                    "media_type": "photo" if m.get("media") else None,
                    "reply_to_message_id": m.get("reply_to"),
                    "forward_from_chat_id": None,
                    "forward_from_message_id": None,
                    "views": None,
                    "scraped_at": m.get("timestamp"),
                    "risk_score": risk_score,
                    "risk_level": risk_level,
                    "risk_factors": keywords,
                    "keywords": keywords,
                }
            )

            for ent in ctx.get("entities") or []:
                if isinstance(ent, dict):
                    entities.append(
                        {
                            "id": entity_id,
                            "message_row_id": i + 1,
                            "entity_type": ent.get("type") or ent.get("entity_type") or "unknown",
                            "entity_value": ent.get("value") or ent.get("entity_value") or "",
                            "start_offset": ent.get("start"),
                            "end_offset": ent.get("end"),
                            "created_at": m.get("timestamp"),
                        }
                    )
                    entity_id += 1

            keyword_entities, entity_id = _keyword_entities_for_text(
                m.get("text"),
                message_row_id=i + 1,
                timestamp=m.get("timestamp"),
                start_id=entity_id,
            )
            entities.extend(keyword_entities)

        for row in personnel:
            uid = int(row["user_id"])
            row["message_count"] = user_msg_counts.get(uid, 0)
            row["suspicious_count"] = user_suspicious.get(uid, 0)
            row["keyword_total"] = len(user_keywords.get(uid, set()))
            row["keyword_list"] = sorted(user_keywords.get(uid, set()))
            row["chat_ids"] = sorted(user_chats.get(uid, set()))
            if row["suspicious_count"] > 0:
                row["risk_score"] = min(100, 20 + row["suspicious_count"] * 15)
                row["risk_level"] = (
                    "Critical"
                    if row["risk_score"] >= 71
                    else "High"
                    if row["risk_score"] >= 41
                    else "Medium"
                    if row["risk_score"] >= 21
                    else "Low"
                )

        scenario_name = scenario
        if not scenario_name and record.scenario_runs:
            scenario_name = record.scenario_runs[-1]
        if not scenario_name:
            weights = record.engine._scenario_config.scenario_weights or {}
            scenario_name = next(iter(weights.keys()), None) if weights else None

        return {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "counts": {
                "chats": len(chats),
                "users": len(users),
                "messages": len(messages),
                "entities": len(entities),
                "personnel": len(personnel),
            },
            "chats": chats,
            "users": users,
            "messages": messages,
            "entities": entities,
            "personnel": personnel,
            "simulation": {
                "session_id": session_id,
                "session_name": record.name,
                "scenario": scenario_name,
                "environment": EnvironmentType.SIMULATION.value,
                "isolated": True,
            },
        }

    def pipeline_inspect(self, session_id: str, message_id: str) -> dict[str, Any]:
        record = self._require_record(session_id)
        inspection = record.pipeline_inspections.get(str(message_id))
        if inspection:
            return inspection
        return {"message_id": message_id, "stages": [], "error": "Not found"}

    def benchmark(self, session_id: str | None = None) -> dict[str, Any]:
        record = self._resolve_session(session_id)
        if record is None:
            return {
                "precision": 0.0,
                "recall": 0.0,
                "false_positives": 0,
                "false_negatives": 0,
                "detection_rate": 0.0,
                "expected_alerts": 0,
                "actual_alerts": 0,
                "keyword_accuracy": 0.0,
                "messages_evaluated": 0,
                "trend": [],
            }
        expected_alerts = 0
        actual_alerts = 0
        tp = fp = fn = tn = 0
        keyword_hits = 0
        keyword_expected = 0
        for msg_id, inspection in record.pipeline_inspections.items():
            ctx = inspection.get("context") or {}
            expected = inspection.get("ground_truth") or {}
            if expected.get("expected_alert"):
                expected_alerts += 1
                keyword_expected += len(expected.get("expected_keywords") or [])
            if ctx.get("alert"):
                actual_alerts += 1
            exp_alert = bool(expected.get("expected_alert"))
            got_alert = bool(ctx.get("alert"))
            if exp_alert and got_alert:
                tp += 1
            elif not exp_alert and got_alert:
                fp += 1
            elif exp_alert and not got_alert:
                fn += 1
            else:
                tn += 1
            for kw in expected.get("expected_keywords") or []:
                if kw in (ctx.get("keywords") or []):
                    keyword_hits += 1
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        return {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "false_positives": fp,
            "false_negatives": fn,
            "detection_rate": round(recall, 3),
            "expected_alerts": expected_alerts,
            "actual_alerts": actual_alerts,
            "keyword_accuracy": round(keyword_hits / keyword_expected, 3) if keyword_expected else 0.0,
            "messages_evaluated": len(record.pipeline_inspections),
            "trend": [],
        }

    def reports(self, session_id: str | None = None) -> list[dict[str, Any]]:
        record = self._resolve_session(session_id)
        if record is None:
            return []
        stats = record.engine.get_statistics()
        return [
            {"id": "simulation_summary", "title": "Simulation Summary", "format": "json", "data": stats},
            {"id": "detection_accuracy", "title": "Detection Accuracy", "format": "json", "data": self.benchmark(record.session_id)},
            {"id": "pipeline_performance", "title": "Pipeline Performance", "format": "json", "data": self.pipeline_health(record.session_id)},
        ]

    def get_config(self, session_id: str | None = None) -> dict[str, Any]:
        record = self._resolve_session(session_id)
        if record is None:
            g = self._default_generation_config()
            return {
                "simulation_speed": g.simulation_speed_multiplier,
                "tick_interval": "one_minute",
                "scenario_distribution": {},
                "random_seed": g.random_seed,
                "users": g.user_count,
                "groups": g.group_count,
                "max_conversations": g.maximum_concurrent_conversations,
                "max_active_users": 10,
                "checkpoint_frequency": 5,
                "retry_count": 0,
                "pipeline_timeout": 30,
                "max_ticks": 20,
            }
        g = record.engine.generation_config
        e = record.engine.execution_config
        return {
            "simulation_speed": e.simulation_speed,
            "tick_interval": e.tick_interval.value,
            "scenario_distribution": dict(record.engine._scenario_config.scenario_weights),
            "random_seed": g.random_seed,
            "users": g.user_count,
            "groups": g.group_count,
            "max_conversations": g.maximum_concurrent_conversations,
            "max_active_users": e.max_active_users,
            "checkpoint_frequency": e.checkpoint_frequency_ticks,
            "retry_count": e.retry_count,
            "pipeline_timeout": e.pipeline_timeout_seconds,
            "max_ticks": e.max_ticks,
        }

    def update_config(self, session_id: str | None, config: dict[str, Any]) -> dict[str, Any]:
        errors = self._validate_config(config)
        if errors:
            return {"ok": False, "errors": errors}
        return {"ok": True, "message": "Configuration validated. Create a new session to apply changes.", "config": config}

    def metrics(self, session_id: str | None = None) -> dict[str, Any]:
        record = self._resolve_session(session_id)
        if record is None:
            return {
                "messages_per_sec": 0,
                "pipeline_throughput_per_tick": 0,
                "pipeline_latency_ms": 0,
                "messages_processed": 0,
                "alerts_generated": 0,
                "retry_count": 0,
                "event_bus_events": 0,
                "dropped_events": 0,
            }
        m = record.engine.metrics.snapshot()
        bus = record.engine.event_bus.history
        return {
            **m,
            "messages_per_sec": round(m.get("messages_processed", 0) / max(m.get("session_duration_seconds", 1), 0.1), 2),
            "queue_length": 0,
            "pipeline_latency_ms": m.get("total_processing_time_ms", 0),
            "event_bus_events": len(bus),
            "subscribers": 0,
            "dropped_events": m.get("dropped_messages", 0),
        }

    def pipeline_health(self, session_id: str | None = None) -> dict[str, Any]:
        record = self._resolve_session(session_id)
        if record is None:
            return {"stages": [], "overall": "idle"}
        stages = record.engine.pipeline.stage_names
        metrics = record.engine.metrics.snapshot()
        avg = metrics.get("average_stage_duration_ms") or {}
        out = []
        for stage in stages:
            latency = avg.get(stage, 0)
            status = "healthy"
            if latency > 500:
                status = "warning"
            if record.engine.metrics.processing_errors > 0 and stage == "validation":
                status = "error"
            out.append(
                {
                    "stage": stage,
                    "status": status,
                    "average_latency_ms": latency,
                    "messages_processed": metrics.get("messages_processed", 0),
                    "queue_length": 0,
                    "failures": record.engine.metrics.processing_errors,
                    "retry_count": metrics.get("retry_count", 0),
                }
            )
        return {"stages": out, "overall": "healthy" if not record.engine.metrics.processing_errors else "warning"}

    def architecture(self, session_id: str | None = None) -> dict[str, Any]:
        record = self._resolve_session(session_id)
        if record is None:
            return {"components": [], "environment": EnvironmentType.SIMULATION.value}
        session = record.engine.session
        health = self.pipeline_health(record.session_id)
        components = [
            {"name": "Environment Manager", "status": self._manager.state.value, "health": "healthy"},
            {"name": "Execution Engine", "status": session.status.value if session else "idle", "health": "healthy"},
            {"name": "Scheduler", "status": "active", "health": "healthy", "latency_ms": 0},
            {"name": "Scenario Engine", "status": "active", "health": "healthy"},
            {"name": "Conversation Engine", "status": "active", "health": "healthy"},
            {"name": "Pipeline Controller", "status": "active", "health": health.get("overall", "healthy")},
            {"name": "Event Bus", "status": "active", "health": "healthy", "messages": len(record.engine.event_bus.history)},
        ]
        for stage in health.get("stages") or []:
            components.append(
                {
                    "name": f"Stage: {stage['stage']}",
                    "status": stage["status"],
                    "health": stage["status"],
                    "latency_ms": stage["average_latency_ms"],
                    "messages": stage["messages_processed"],
                    "errors": stage["failures"],
                }
            )
        return {"components": components, "environment": EnvironmentType.SIMULATION.value}

    def export_session(self, session_id: str, fmt: str = "json") -> str:
        record = self._require_record(session_id)
        payload = {
            "session": record.summary(),
            "messages": record.messages,
            "benchmark": self.benchmark(session_id),
            "statistics": record.engine.get_statistics(),
        }
        if fmt == "json":
            return json.dumps(payload, indent=2, default=str)
        if fmt == "csv":
            bench = payload["benchmark"]
            lines = ["metric,value"] + [f"{k},{v}" for k, v in bench.items()]
            return "\n".join(lines)
        if fmt == "md":
            return (
                f"# Simulation Export: {record.name}\n\n"
                f"## Benchmark\n```json\n{json.dumps(payload['benchmark'], indent=2)}\n```\n"
            )
        return json.dumps(payload, default=str)

    def _ingest_runtime(self, record: ConsoleSessionRecord) -> None:
        snap = record.engine.runtime_snapshot()
        seen = {
            (str(m.get("chat_id") or ""), str(m.get("message_id") or ""))
            for m in record.messages
        }
        for event in snap.get("message_events") or []:
            msg_id = str(event.get("message_id"))
            chat_id = str(event.get("chat_id") or "")
            key = (chat_id, msg_id)
            if key in seen:
                continue
            seen.add(key)
            record.messages.append(
                {
                    "message_id": msg_id,
                    "chat_id": event.get("chat_id"),
                    "sender_id": event.get("sender_id"),
                    "text": event.get("text"),
                    "timestamp": event.get("timestamp"),
                    "reply_to": event.get("reply_to_message_id"),
                    "is_forward": event.get("is_forward"),
                    "is_edited": event.get("is_edited"),
                    "is_deleted": event.get("is_deleted"),
                    "media": bool(event.get("media_metadata")),
                }
            )
        for result in snap.get("pipeline_results") or []:
            ctx = result.get("context") or {}
            msg_id = str(ctx.get("message_id") or "")
            if not msg_id:
                continue
            stages = []
            durations = ctx.get("stage_durations_ms") or {}
            errors = ctx.get("stage_errors") or {}
            for stage_name, duration in durations.items():
                stages.append(
                    {
                        "stage": stage_name,
                        "latency_ms": duration,
                        "result": "error" if stage_name in errors else "ok",
                        "error": errors.get(stage_name),
                        "warnings": [],
                        "data": {
                            "keywords": ctx.get("keywords"),
                            "risk_level": ctx.get("risk_level"),
                            "entities": ctx.get("entities"),
                        }
                        if stage_name in {"keyword", "risk", "entity_extraction"}
                        else {},
                    }
                )
            record.pipeline_inspections[msg_id] = {
                "message_id": msg_id,
                "context": ctx,
                "stages": stages,
                "final_context": ctx,
                "ground_truth": self._ground_truth_for_context(record, ctx),
            }
        stats = record.engine._scenario_manager.get_statistics()
        if stats.total_runs:
            record.scenario_runs.append(stats.most_active_scenario or "unknown")

    def _ground_truth_for_context(self, record: ConsoleSessionRecord, ctx: dict[str, Any]) -> dict[str, Any]:
        text = str(ctx.get("normalized_text") or "")
        keywords = ctx.get("keywords") or []
        mgr = record.engine._scenario_manager
        for scenario in mgr.registry.all():
            gt = scenario.ground_truth
            if gt is None or not gt.synthetic_evaluation:
                continue
            gt_dict = gt.to_dict()
            expected_kws = gt_dict.get("expected_keywords") or []
            if any(kw in text or kw in keywords for kw in expected_kws):
                return gt_dict
            if gt_dict.get("expected_alert") and ctx.get("alert"):
                return gt_dict
        return {}

    def _empty_overview(self) -> dict[str, Any]:
        return {
            "simulation_status": "none",
            "environment": EnvironmentType.SIMULATION.value,
            "current_session": None,
            "simulation_speed": 0,
            "current_tick": 0,
            "elapsed_seconds": 0,
            "users": 0,
            "groups": 0,
            "conversations": 0,
            "messages_generated": 0,
            "messages_processed": 0,
            "alerts_generated": 0,
            "cases_generated": 0,
            "sebastian_index_count": 0,
            "pipeline_health": {"stages": [], "overall": "idle"},
            "cpu_percent": 0,
            "memory_mb": 0,
        }

    def _resolve_session(self, session_id: str | None) -> ConsoleSessionRecord | None:
        """Resolve session for read endpoints — never auto-create."""
        sid = session_id or self._active_session_id
        if sid:
            record = self._sessions.get(sid)
            if record is not None:
                return record
            if session_id:
                self._active_session_id = None
        if self._active_session_id:
            record = self._sessions.get(self._active_session_id)
            if record is not None:
                return record
        if self._sessions:
            sid = next(iter(self._sessions.keys()))
            self._active_session_id = sid
            return self._sessions[sid]
        return None

    def _require_session(self, session_id: str | None) -> ConsoleSessionRecord:
        record = self._resolve_session(session_id)
        if record is None:
            raise KeyError("No active simulation session")
        return record

    def _resolve_session_or_raise(self, session_id: str) -> ConsoleSessionRecord:
        record = self._sessions.get(session_id)
        if record is None:
            raise KeyError(f"Session {session_id} not found")
        return record

    def create_session_and_return(self) -> ConsoleSessionRecord:
        summary = self.create_session()
        return self._require_record(summary["session_id"])

    def _require_record(self, session_id: str) -> ConsoleSessionRecord:
        record = self._sessions.get(session_id)
        if record is None:
            raise KeyError(f"Session {session_id} not found")
        return record

    def _default_generation_config(self) -> GenerationConfig:
        return GenerationConfig(
            user_count=40,
            group_count=6,
            random_seed=42,
            language_distribution=english_only_language_distribution(),
        )

    def _config_from_dict(self, config: dict[str, Any]) -> GenerationConfig:
        base = self._default_generation_config()
        from simulator.keywords import category_for_filter

        filt = config.get("scenario_filter") or config.get("scenario")
        category = category_for_filter(str(filt) if filt else None)
        language_distribution = config.get("language_distribution")
        if language_distribution is None:
            language_distribution = english_only_language_distribution()
        return GenerationConfig(
            user_count=int(config.get("users", base.user_count)),
            group_count=int(config.get("groups", base.group_count)),
            random_seed=config.get("random_seed", base.random_seed),
            language_distribution=dict(language_distribution),
            maximum_concurrent_conversations=int(config.get("max_conversations", base.maximum_concurrent_conversations)),
            simulation_speed_multiplier=float(config.get("simulation_speed", base.simulation_speed_multiplier)),
            keyword_category=category,
        )

    def _scenario_config_from_dict(self, config: dict[str, Any]) -> ScenarioConfig:
        from simulator.keywords import scenario_for_filter
        from simulator.scenario.config import _default_scenario_weights

        seed = config.get("random_seed", 42)
        filt = config.get("scenario_filter") or config.get("scenario")
        scenario_id = scenario_for_filter(str(filt) if filt else None)
        languages = tuple(config.get("languages") or ("english",))
        weights = dict(_default_scenario_weights())
        if scenario_id:
            weights[scenario_id] = max(weights.get(scenario_id, 0.0), 0.35)
        return ScenarioConfig(
            random_seed=seed,
            languages=languages,
            scenario_weights=weights,
            include_synthetic_threat_evaluation=True,
        )

    def _validate_config(self, config: dict[str, Any]) -> list[str]:
        errors = []
        if "users" in config and int(config["users"]) < 2:
            errors.append("users must be at least 2")
        if "groups" in config and int(config["groups"]) < 1:
            errors.append("groups must be at least 1")
        if "simulation_speed" in config and float(config["simulation_speed"]) <= 0:
            errors.append("simulation_speed must be positive")
        return errors
