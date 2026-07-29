"""AI-assisted synthetic message generation for simulation dummy scrapes."""

from __future__ import annotations

import logging
import random
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from keyword_filter import scan_message_text
from simulator.generation.scenarios import parse_console_scenarios, scenario_focus_phrase
from simulator.keywords import category_for_filter, keywords_for_category

logger = logging.getLogger("simulator.generation.ai_content")

_SIM_CHAT_ID_BASE = 8_100_000
_SIM_USER_ID_BASE = 9_100_000

_MEDIA_TYPES = ("MessageMediaPhoto", "MessageMediaDocument", "MessageMediaWebPage")


@dataclass(frozen=True, slots=True)
class SimulatedChatDraft:
    """Synthetic Telegram chat metadata."""

    chat_id: int
    title: str
    username: str | None
    chat_type: str


@dataclass(frozen=True, slots=True)
class SimulatedMessageDraft:
    """Normalized message ready for Mongo persistence — mirrors scraped Telegram fields."""

    chat_id: int
    chat_title: str
    chat_username: str | None
    chat_type: str
    message_id: int
    sender_id: int
    sender_username: str
    sender_first_name: str
    sender_last_name: str | None
    text: str
    timestamp: datetime
    media_type: str | None = None
    reply_to_message_id: int | None = None
    forward_from_chat_id: int | None = None
    forward_from_message_id: int | None = None
    views: int | None = None


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "", value.lower().replace(" ", "_"))
    return cleaned[:24] or "sim_chat"


def _build_chats(rng: random.Random) -> list[SimulatedChatDraft]:
    return [
        SimulatedChatDraft(
            _SIM_CHAT_ID_BASE - 1,
            "Black Market Logistics",
            "blackmarket_logistics",
            "supergroup",
        ),
        SimulatedChatDraft(
            _SIM_CHAT_ID_BASE - 2,
            "Ghost Arms Exchange",
            "ghostarms_exchange",
            "group",
        ),
        SimulatedChatDraft(
            _SIM_CHAT_ID_BASE - 3,
            "Border Runner Network",
            "border_runner_net",
            "channel",
        ),
        SimulatedChatDraft(
            _SIM_CHAT_ID_BASE - 4,
            "DM · Viktor K",
            None,
            "private chat",
        ),
        SimulatedChatDraft(
            _SIM_CHAT_ID_BASE - 5,
            "DM · courier_09",
            None,
            "private chat",
        ),
        SimulatedChatDraft(
            _SIM_CHAT_ID_BASE - 6,
            "Night Route Coordinators",
            "night_route_ops",
            "group",
        ),
    ]


def _personas(rng: random.Random) -> list[tuple[int, str, str, str | None, str]]:
    pool = [
        (_SIM_USER_ID_BASE + 1, "viktor_k", "Viktor", "Koval", "Supplier — no small talk"),
        (_SIM_USER_ID_BASE + 2, "ghostrunner09", "Mira", "Santos", "Courier coordinator"),
        (_SIM_USER_ID_BASE + 3, "ironbroker", "Derek", "Hale", "Arms broker"),
        (_SIM_USER_ID_BASE + 4, "nightshift_ops", "Lena", "Okafor", "Route planner"),
        (_SIM_USER_ID_BASE + 5, "coldcontact77", "Unknown", "Buyer", "Repeat offender profile"),
    ]
    rng.shuffle(pool)
    return pool


def _malicious_templates(category: str) -> tuple[str, ...]:
    common = {
        "narcotics": (
            "Need {kw} tonight. Call {phone} — no delays. Cash ready at {addr}.",
            "Bulk {kw} moving cross-border. Wire {wallet} then pickup at {addr}.",
            "Stop asking questions. {kw} price is fixed. Meet at {addr}.",
            "If you snitch on the {kw} run I'll make sure you regret it. Contact {phone}.",
            "Forwarded from supplier: {kw} batch is clean. Drop {wallet} to this wallet first.",
        ),
        "firearms": (
            "Untraceable {kw} available. Pickup {addr}. No paperwork.",
            "Need {kw} before Friday. Pay {wallet} — serious buyers only.",
            "Stop posting in open channels. DM {phone} for {kw} deals only.",
            "New {kw} shipment landed. Meet {addr} — first come.",
            "Re: {kw} — same route as last month. Call {phone} when close.",
        ),
        "human_trafficking": (
            "Transport for {kw} victims scheduled. Safehouse: {addr}.",
            "Client wants {kw} pipeline cleared tonight. Contact {phone}.",
            "If border patrol stops the van, you know nothing about {kw}.",
            "Payment after delivery to {wallet}. {kw} handlers stay off the grid.",
            "Forwarded intel: {kw} ring expanding — rendezvous {addr}.",
        ),
    }
    return common.get(category, common["narcotics"])


def _fallback_messages(
    *,
    scenarios: list[str],
    count: int,
    rng: random.Random,
) -> list[SimulatedMessageDraft]:
    selected = parse_console_scenarios(",".join(scenarios))
    chats = _build_chats(rng)
    personas = _personas(rng)
    drafts: list[SimulatedMessageDraft] = []
    now = datetime.now(timezone.utc)
    per_chat_counter: dict[int, int] = {}
    last_message_id: dict[int, int] = {}
    sample_phones = ("+1-555-014-8821", "+44 7700 900123", "+49 151 23456789")
    sample_addrs = ("214 Harbor Wharf Rd", "88 Industrial Park Dr", "19 Back Alley Lane")
    sample_wallets = (
        "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0",
        "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
    )

    for index in range(count):
        category = str(category_for_filter(rng.choice(selected)) or "narcotics")
        keywords = keywords_for_category(category, rng) or ("cocaine", "heroin", "ghost gun", "fentanyl")
        templates = _malicious_templates(category)
        chat = chats[index % len(chats)]
        persona = personas[index % len(personas)]
        sender_id, username, first, last, _ = persona
        per_chat_counter[chat.chat_id] = per_chat_counter.get(chat.chat_id, 0) + 1
        message_id = 100 + per_chat_counter[chat.chat_id]
        kw = rng.choice(keywords)
        text = rng.choice(templates).format(
            kw=kw,
            phone=rng.choice(sample_phones),
            addr=rng.choice(sample_addrs),
            wallet=rng.choice(sample_wallets),
        )
        minutes_ago = rng.randint(20, 60 * 24 * 10)
        timestamp = now - timedelta(minutes=minutes_ago)

        reply_to = None
        if chat.chat_id in last_message_id and rng.random() < 0.35:
            reply_to = last_message_id[chat.chat_id]

        forward_chat = None
        forward_msg = None
        if rng.random() < 0.18 and chat.chat_type != "private chat":
            forward_chat = chats[(index + 2) % len(chats)].chat_id
            forward_msg = rng.randint(40, 90)

        media_type = None
        if rng.random() < 0.22:
            media_type = rng.choice(_MEDIA_TYPES)

        views = None
        if chat.chat_type == "channel":
            views = rng.randint(120, 18_000)

        drafts.append(
            SimulatedMessageDraft(
                chat_id=chat.chat_id,
                chat_title=chat.title,
                chat_username=chat.username,
                chat_type=chat.chat_type,
                message_id=message_id,
                sender_id=sender_id,
                sender_username=username,
                sender_first_name=first,
                sender_last_name=last if last != "Buyer" else None,
                text=text,
                timestamp=timestamp,
                media_type=media_type,
                reply_to_message_id=reply_to,
                forward_from_chat_id=forward_chat,
                forward_from_message_id=forward_msg,
                views=views,
            )
        )
        last_message_id[chat.chat_id] = message_id

    return drafts


def _parse_ai_payload(raw: dict, *, count: int, rng: random.Random) -> list[SimulatedMessageDraft]:
    rows = raw.get("messages") or raw.get("items") or []
    if not isinstance(rows, list):
        return []
    now = datetime.now(timezone.utc)
    drafts: list[SimulatedMessageDraft] = []
    for index, row in enumerate(rows[:count]):
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        if not scan_message_text(text).matched:
            continue
        chat_title = str(row.get("chat_title") or row.get("channel") or f"Sim Channel {index + 1}")
        chat_type = str(row.get("chat_type") or "group")
        chat_id = int(row.get("chat_id") or (_SIM_CHAT_ID_BASE - index))
        chat_username = row.get("chat_username") or row.get("username")
        sender_id = int(row.get("sender_id") or (_SIM_USER_ID_BASE + index))
        display = str(row.get("sender_display_name") or row.get("sender") or f"User {sender_id}")
        parts = display.split()
        first = parts[0] if parts else "User"
        last = parts[-1] if len(parts) > 1 else None
        username = str(row.get("sender_username") or f"sim_user_{sender_id}")
        minutes_ago = int(row.get("minutes_ago") or rng.randint(30, 10_080))
        ts_raw = row.get("timestamp")
        if ts_raw:
            try:
                timestamp = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
            except ValueError:
                timestamp = now - timedelta(minutes=minutes_ago)
        else:
            timestamp = now - timedelta(minutes=minutes_ago)
        drafts.append(
            SimulatedMessageDraft(
                chat_id=chat_id,
                chat_title=chat_title,
                chat_username=str(chat_username).lstrip("@") if chat_username else None,
                chat_type=chat_type,
                message_id=int(row.get("message_id") or (20_000 + index)),
                sender_id=sender_id,
                sender_username=username.lstrip("@"),
                sender_first_name=first,
                sender_last_name=last,
                text=text,
                timestamp=timestamp,
                media_type=row.get("media_type"),
                reply_to_message_id=row.get("reply_to_message_id"),
                forward_from_chat_id=row.get("forward_from_chat_id"),
                forward_from_message_id=row.get("forward_from_message_id"),
                views=row.get("views"),
            )
        )
    return drafts


def generate_ai_simulation_messages(
    *,
    scenario: str | None = None,
    count: int = 24,
    seed: int | None = None,
    model: str | None = None,
) -> list[SimulatedMessageDraft]:
    """Generate flagged training messages via LLM, with malicious-tone template fallback."""
    rng = random.Random(seed or 42)
    count = max(12, min(count, 80))
    selected = parse_console_scenarios(scenario)
    focus = scenario_focus_phrase(selected)

    try:
        from ai.config import get_ai_settings
        from ai.llm.client import create_llm_client
        from ai.llm.json_mode import parse_json_object
        from ai.providers.base import ChatMessage

        settings = get_ai_settings()
        if settings.enabled and settings.is_configured_for_chat:
            resolved_model = (model or settings.chat_model or "").strip() or None
            client = create_llm_client(
                settings,
                model=resolved_model,
                temperature=0.55,
            )
            prompt = (
                f"Generate {count} realistic English Telegram messages for SOC training. "
                f"Threat focus (mix across messages): {focus}. "
                "Tone: criminal, covert, malicious intent — dealers, traffickers, smugglers coordinating illegal activity. "
                "Each message MUST include explicit OSINT keywords matching its threat type "
                "(narcotics, firearms, or human trafficking terms). "
                "Mix chat_type values: group, supergroup, channel, private chat. "
                "Include some replies (reply_to_message_id), forwards (forward_from_chat_id, forward_from_message_id), "
                "channel views, and occasional media_type (MessageMediaPhoto, MessageMediaDocument). "
                'Return JSON only: {"messages": [{"chat_title":"...","chat_username":"...","chat_type":"group",'
                '"sender_display_name":"First Last","sender_username":"handle","text":"...",'
                '"minutes_ago":120,"message_id":101,"reply_to_message_id":null,"forward_from_chat_id":null,'
                '"forward_from_message_id":null,"views":null,"media_type":null}]}'
            )
            completion = client.complete(
                [
                    ChatMessage(
                        role="system",
                        content=(
                            "You produce synthetic criminal Telegram traffic for law-enforcement training. "
                            "Messages sound like real illicit coordination. Output valid JSON only."
                        ),
                    ),
                    ChatMessage(role="user", content=prompt),
                ],
                max_tokens=min(6000, count * 140),
                model=resolved_model,
            )
            parsed = parse_json_object(completion.content or "")
            drafts = _parse_ai_payload(parsed, count=count, rng=rng)
            if len(drafts) >= max(6, count // 3):
                logger.info(
                    "ai_simulation_generated count=%d scenarios=%s model=%s",
                    len(drafts),
                    ",".join(selected),
                    resolved_model or settings.chat_model,
                )
                return drafts
    except Exception as exc:
        logger.warning("ai_simulation_fallback reason=%s", exc)

    return _fallback_messages(scenarios=selected, count=count, rng=rng)
