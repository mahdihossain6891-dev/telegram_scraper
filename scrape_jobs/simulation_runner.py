"""AI-powered dummy scrape for simulation mode — writes to isolated MongoDB."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Callable

from behavioral_analytics import rebuild_behavioral_analytics
from personnel import rebuild_user_activity
from config import Settings, ensure_directories, load_settings
from database import (
    clear_simulation_database,
    database_available,
    get_session_for_database,
    get_simulation_database_name,
    message_exists,
)
from message_scraper import ParsedMessage, ensure_chat_record, store_parsed_message
from scrape_jobs.store import ScrapeJobStore, get_scrape_job_store
from simulator.generation.ai_content import SimulatedMessageDraft, generate_ai_simulation_messages

logger = logging.getLogger("scrape_jobs.simulation_runner")


@dataclass(frozen=True, slots=True)
class SimulationScrapeResult:
    messages_analyzed: int
    threats_detected: int
    channels_scanned: int


def _chat_discovery_from_draft(draft: SimulatedMessageDraft):
    from chat_discovery import DiscoveredChat

    return DiscoveredChat(
        chat_id=draft.chat_id,
        name=draft.chat_title,
        username=draft.chat_username,
        chat_type=draft.chat_type,
        index=0,
    )


def _parsed_from_draft(draft: SimulatedMessageDraft) -> ParsedMessage:
    return ParsedMessage(
        message_id=draft.message_id,
        chat_id=draft.chat_id,
        sender_id=draft.sender_id,
        timestamp=draft.timestamp,
        text=draft.text,
        media_type=draft.media_type,
        reply_to_message_id=draft.reply_to_message_id,
        forward_from_chat_id=draft.forward_from_chat_id,
        forward_from_message_id=draft.forward_from_message_id,
        views=draft.views,
        sender_username=draft.sender_username,
        sender_first_name=draft.sender_first_name,
        sender_last_name=draft.sender_last_name,
    )


def run_simulation_scrape(
    settings: Settings,
    store: ScrapeJobStore,
    *,
    scenario: str | None = None,
    limit: int = 24,
    model: str | None = None,
    reset_database: bool = True,
    on_progress: Callable[[int, int, int, str | None], None] | None = None,
) -> SimulationScrapeResult:
    """Generate AI (or fallback) messages and persist them to the simulation database."""
    if not database_available(settings):
        raise RuntimeError("MongoDB unavailable")

    sim_db = get_simulation_database_name()
    # Generate first so a failed/slow AI run never leaves an empty DB mid-job.
    drafts = generate_ai_simulation_messages(scenario=scenario, count=limit, model=model)
    if not drafts:
        raise RuntimeError("Simulation generator returned no messages")

    if reset_database:
        clear_simulation_database(settings)

    channels = {draft.chat_id: draft.chat_title for draft in drafts}
    store.set_plan(
        channels_total=len(channels),
        scope="simulation",
        limit_per_chat=limit,
    )

    threats = 0
    analyzed = 0
    scanned_channels: set[int] = set()
    # Unique per run so a second generate never collides with leftover IDs.
    id_offset = int(datetime.now(timezone.utc).timestamp()) % 1_000_000

    with get_session_for_database(sim_db, settings) as session:
        for index, draft in enumerate(drafts):
            analyzed += 1
            scanned_channels.add(draft.chat_id)
            chat = _chat_discovery_from_draft(draft)
            parsed = replace(
                _parsed_from_draft(draft),
                message_id=int(draft.message_id) + id_offset + index,
            )
            from keyword_filter import scan_message_text

            keyword_scan = scan_message_text(parsed.text)
            if not keyword_scan.matched:
                continue
            if message_exists(session, parsed.chat_id, parsed.message_id):
                continue
            ensure_chat_record(session, chat)
            if store_parsed_message(session, parsed, keyword_scan):
                threats += 1
            if on_progress:
                on_progress(
                    len(scanned_channels),
                    analyzed,
                    threats,
                    draft.chat_title,
                )

        if threats == 0:
            raise RuntimeError(
                "No keyword-flagged messages were stored. Try again or change scenarios."
            )

        rebuild_user_activity(session)
        rebuild_behavioral_analytics(session)

    return SimulationScrapeResult(
        messages_analyzed=analyzed,
        threats_detected=threats,
        channels_scanned=len(scanned_channels),
    )


def _maybe_index_simulation_database(settings: Settings, database_name: str) -> None:
    try:
        from ai.config import get_ai_settings
        from ai.jobs.indexer import IndexerJob
        from database import get_db_by_name

        ai_settings = get_ai_settings()
        if not ai_settings.enabled or not ai_settings.is_configured_for_embeddings:
            return
        db = get_db_by_name(database_name, settings)
        IndexerJob(db, settings=ai_settings).run(full_rebuild=True)
    except Exception as exc:
        logger.info("simulation_index_skipped reason=%s", exc)


def _run_simulation_scrape_thread(
    settings: Settings,
    store: ScrapeJobStore,
    *,
    scenario: str | None,
    limit: int,
    model: str | None = None,
    reset_database: bool = True,
) -> None:
    sim_db = get_simulation_database_name()
    try:
        def _progress(channels_scanned: int, analyzed: int, threats: int, channel: str | None) -> None:
            store.update_progress(
                channels_scanned=channels_scanned,
                messages_analyzed=analyzed,
                threats_detected=threats,
                current_channel=channel,
            )

        result = run_simulation_scrape(
            settings,
            store,
            scenario=scenario,
            limit=limit,
            model=model,
            reset_database=reset_database,
            on_progress=_progress,
        )
        # Mark complete before optional AI indexing so Generate unlocks immediately.
        store.complete(
            messages_analyzed=result.messages_analyzed,
            threats_detected=result.threats_detected,
        )
    except Exception as exc:
        logger.exception("simulation_scrape_failed")
        store.fail(str(exc))
        return

    try:
        _maybe_index_simulation_database(settings, sim_db)
    except Exception as exc:
        logger.info("simulation_index_after_complete_skipped reason=%s", exc)


def start_simulation_scrape_in_background(
    settings: Settings | None = None,
    *,
    scenario: str | None = None,
    limit: int = 24,
    model: str | None = None,
    reset_database: bool = True,
) -> bool:
    """Start an AI dummy scrape into the simulation Mongo database."""
    cfg = ensure_directories(settings or load_settings())
    store = get_scrape_job_store()
    if not store.try_begin():
        return False

    thread = threading.Thread(
        target=_run_simulation_scrape_thread,
        args=(cfg, store),
        kwargs={
            "scenario": scenario,
            "limit": limit,
            "model": model,
            "reset_database": reset_database,
        },
        daemon=True,
        name="simulation-scrape-job",
    )
    thread.start()
    return True
