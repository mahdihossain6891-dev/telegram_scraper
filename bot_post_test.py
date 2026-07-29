"""Post demo keyword test messages to a monitored Telegram channel via Bot API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass

from dotenv import dotenv_values

from utils import get_logger, setup_logging

logger = get_logger("bot_post_test")

# Language codes supported for demo posts.
SUPPORTED_LANGS: tuple[str, ...] = (
    "en",
    "es",
    "fr",
    "ar",
    "ru",
    "bn",
    "zh",
    "hi",
    "pt",
    "de",
)

# Lab-only demo chatter. Non-English sets must contain ZERO English vocabulary
# (no TEST/QA/dashboard/cocaine/etc). Native terms must match keyword_filter.
TEST_MESSAGES_BY_LANG: dict[str, tuple[str, ...]] = {
    "en": (
        "[TEST] Demo alert: cocaine shipment update for monitoring dashboard.",
        "[TEST] Sample post mentioning ghost gun for firearms keyword detection.",
        "[TEST] Exercise message about human trafficking ring (demo only).",
        "[TEST] Keyword check: meth distribution chatter — not real intelligence.",
        "[TEST] Firearms flag test: illegal gun sale mention for scraper lab.",
        "[TEST] Narcotics flag test: fentanyl shipment phrase for dashboard QA.",
    ),
    "es": (
        "Alerta de laboratorio: actualización de envío de cocaína para el monitoreo.",
        "Publicación de prueba que menciona un arma ilegal para detección de armas.",
        "Mensaje de ejercicio sobre una red de trata de personas (solo laboratorio).",
        "Revisión: conversación sobre metanfetamina — no es inteligencia real.",
        "Prueba de armas: mención de tráfico de armas para el laboratorio.",
        "Prueba de estupefacientes: frase de envío de fentanilo para control de calidad.",
    ),
    "fr": (
        "Alerte de laboratoire : mise à jour d’envoi de cocaïne pour la surveillance.",
        "Message d’essai mentionnant une arme illégale pour la détection d’armes.",
        "Exercice sur la traite des êtres humains (laboratoire uniquement).",
        "Contrôle : discussion sur la méthamphétamine — pas de renseignement réel.",
        "Essai armes : mention de trafic d’armes pour le laboratoire.",
        "Essai stupéfiants : nouvelle cargaison d’héroïne pour le contrôle qualité.",
    ),
    "ar": (
        "تنبيه مختبري: تحديث شحنة كوكايين لأغراض المراقبة.",
        "منشور تجريبي يذكر سلاح غير قانوني لاكتشاف الأسلحة.",
        "رسالة تمرين عن شبكة الاتجار بالبشر (للمختبر فقط).",
        "فحص: حديث عن ميثامفيتامين — ليست معلومات استخباراتية حقيقية.",
        "اختبار أسلحة: ذكر اتجار بالأسلحة لمختبر المراقبة.",
        "اختبار مخدرات: عبارة شحنة فنتانيل لفحص الجودة.",
    ),
    "ru": (
        "Лабораторное оповещение: обновление поставки кокаина для мониторинга.",
        "Тестовый пост с упоминанием нелегальное оружие для детекции.",
        "Учебное сообщение о торговля людьми (только лаборатория).",
        "Проверка: разговор о метамфетамине — не реальная разведка.",
        "Тест оружия: упоминание торговля оружием для лаборатории.",
        "Тест наркотиков: фраза о поставке фентанила для контроля качества.",
    ),
    "bn": (
        "ল্যাব সতর্কতা: নজরদারির জন্য কোকেইন চালানের হালনাগাদ।",
        "পরীক্ষা পোস্টে অবৈধ অস্ত্রের উল্লেখ — অস্ত্র সনাক্তকরণের জন্য।",
        "অনুশীলন বার্তা: মানব পাচার চক্র (শুধু ল্যাব)।",
        "পরীক্ষা: মাদক পাচার নিয়ে আলোচনা — আসল গোয়েন্দা নয়।",
        "অস্ত্র পরীক্ষা: অস্ত্র পাচারের উল্লেখ ল্যাবের জন্য।",
        "মাদক পরীক্ষা: ফেন্টানিল চালানের বাক্য মান নিয়ন্ত্রণের জন্য।",
    ),
    "zh": (
        "实验室警报：用于监控的可卡因货运更新。",
        "测试帖文提及非法枪支，用于武器检测。",
        "演练消息：人口贩运网络（仅限实验室）。",
        "检查：冰毒分销讨论——非真实情报。",
        "武器测试：提及武器走私，供实验室使用。",
        "毒品测试：芬太尼货运用语，供质量检查。",
    ),
    "hi": (
        "प्रयोगशाला चेतावनी: निगरानी के लिए कोकीन खेप का अद्यतन।",
        "परीक्षण पोस्ट में अवैध हथियार का उल्लेख — हथियार पहचान के लिए।",
        "अभ्यास संदेश: मानव तस्करी नेटवर्क (केवल प्रयोगशाला)।",
        "जाँच: नशे का व्यापार चर्चा — असली खुफिया नहीं।",
        "हथियार परीक्षण: हथियार तस्करी का उल्लेख प्रयोगशाला के लिए।",
        "नशा परीक्षण: फेंटानिल खेप वाक्यांश गुणवत्ता नियंत्रण के लिए।",
    ),
    "pt": (
        "Alerta de laboratório: atualização de remessa de cocaína para monitoramento.",
        "Post de teste mencionando arma ilegal para detecção de armas.",
        "Mensagem de exercício sobre rede de tráfico de pessoas (somente laboratório).",
        "Verificação: conversa sobre metanfetamina — não é inteligência real.",
        "Teste de armas: menção a tráfico de armas para o laboratório.",
        "Teste de entorpecentes: frase de remessa de fentanil para controle de qualidade.",
    ),
    "de": (
        "Laboralarm: Kokain-Lieferungsupdate für die Überwachung.",
        "Testbeitrag mit Erwähnung einer illegale Waffe zur Waffenerkennung.",
        "Übungsnachricht über Menschenhandel (nur Labor).",
        "Prüfung: Gespräch über Methamphetamin — keine echte Aufklärung.",
        "Waffentest: Erwähnung von Waffenhandel für das Labor.",
        "Betäubungsmitteltest: frischer Drogenhandel für die Qualitätskontrolle.",
    ),
}

# Backward-compatible default = English set.
DEFAULT_TEST_MESSAGES: tuple[str, ...] = TEST_MESSAGES_BY_LANG["en"]


@dataclass(frozen=True)
class BotPostConfig:
    """Settings required to post through the Telegram Bot API."""

    bot_token: str
    channel: str


@dataclass(frozen=True)
class PostResult:
    """Outcome of a single Bot API sendMessage call."""

    message_text: str
    message_id: int | None
    ok: bool
    error: str | None = None


class BotPostError(Exception):
    """Raised when bot posting cannot proceed."""


def load_bot_post_config() -> BotPostConfig:
    """Load bot token and target channel from environment variables."""
    values = {**dotenv_values(".env"), **os.environ}
    token = str(values.get("TELEGRAM_BOT_TOKEN", "")).strip()
    channel = str(values.get("TEST_CHANNEL_USERNAME", "")).strip()

    if not token:
        raise BotPostError(
            "TELEGRAM_BOT_TOKEN is missing. Create a bot with @BotFather and add the token to .env"
        )
    if not channel:
        raise BotPostError(
            "TEST_CHANNEL_USERNAME is missing. Set it to your public channel username, e.g. osint_test_lab"
        )

    if channel.startswith("https://t.me/"):
        channel = channel.removeprefix("https://t.me/").strip("/")
    channel = channel.removeprefix("@")

    return BotPostConfig(bot_token=token, channel=f"@{channel}")


def send_channel_message(config: BotPostConfig, text: str) -> PostResult:
    """Send one message to the configured channel using Telegram Bot API."""
    url = f"https://api.telegram.org/bot{config.bot_token}/sendMessage"
    payload = json.dumps(
        {
            "chat_id": config.channel,
            "text": text,
            "disable_web_page_preview": True,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return PostResult(message_text=text, message_id=None, ok=False, error=detail or str(exc))
    except urllib.error.URLError as exc:
        return PostResult(message_text=text, message_id=None, ok=False, error=str(exc))

    if not body.get("ok"):
        return PostResult(
            message_text=text,
            message_id=None,
            ok=False,
            error=str(body.get("description", "Unknown Bot API error")),
        )

    message_id = body.get("result", {}).get("message_id")
    return PostResult(message_text=text, message_id=int(message_id) if message_id else None, ok=True)


def post_test_messages(
    config: BotPostConfig,
    messages: tuple[str, ...],
) -> list[PostResult]:
    """Post each message in order."""
    results: list[PostResult] = []
    for text in messages:
        logger.info("Posting test message to %s", config.channel)
        result = send_channel_message(config, text)
        results.append(result)
        if not result.ok:
            logger.error("Failed to post message: %s", result.error)
        else:
            logger.info("Posted message_id=%s", result.message_id)
    return results


def parse_lang_codes(raw: str | None) -> list[str]:
    """Parse comma-separated language codes; ``mix`` / ``all`` expands to every language."""
    if not raw or not str(raw).strip():
        return ["en"]
    parts = [p.strip().lower() for p in str(raw).split(",") if p.strip()]
    if not parts:
        return ["en"]
    if any(p in {"mix", "all", "*"} for p in parts):
        return list(SUPPORTED_LANGS)
    unknown = [p for p in parts if p not in TEST_MESSAGES_BY_LANG]
    if unknown:
        raise BotPostError(
            f"Unknown language code(s): {', '.join(unknown)}. "
            f"Use: {', '.join(SUPPORTED_LANGS)}, or mix"
        )
    # Preserve order, unique
    seen: set[str] = set()
    out: list[str] = []
    for code in parts:
        if code not in seen:
            seen.add(code)
            out.append(code)
    return out


def messages_for_langs(langs: list[str]) -> tuple[str, ...]:
    """Flatten demo messages for the selected languages (interleaved by index)."""
    pools = [TEST_MESSAGES_BY_LANG[code] for code in langs]
    if len(pools) == 1:
        return pools[0]
    # Interleave so the channel gets language variety, not one block per language.
    interleaved: list[str] = []
    max_len = max(len(p) for p in pools)
    for i in range(max_len):
        for pool in pools:
            if i < len(pool):
                interleaved.append(pool[i])
    return tuple(interleaved)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI options."""
    parser = argparse.ArgumentParser(
        description=(
            "Post demo suspicious keyword messages to a Telegram test channel "
            "(supports multiple languages)."
        ),
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Send all built-in demo messages for the selected language(s).",
    )
    parser.add_argument(
        "--lang",
        "-l",
        default="en",
        help=(
            "Language code(s): en, es, fr, ar, ru, bn, zh, hi, pt, de. "
            "Comma-separate for several, or use mix/all for every language. Default: en"
        ),
    )
    parser.add_argument(
        "--index",
        type=int,
        help="Send one built-in message by 1-based index (within the selected language set).",
    )
    parser.add_argument(
        "--message",
        "-m",
        help="Send a custom message (wrap in quotes).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List built-in demo messages (for --lang) and exit.",
    )
    parser.add_argument(
        "--list-langs",
        action="store_true",
        help="List supported language codes and exit.",
    )
    return parser.parse_args(argv)


def select_messages(args: argparse.Namespace) -> tuple[str, ...]:
    """Return the message batch selected on the command line."""
    if args.list or getattr(args, "list_langs", False):
        return ()

    if args.message:
        return (args.message.strip(),)

    langs = parse_lang_codes(getattr(args, "lang", None))
    pool = messages_for_langs(langs)

    if args.index is not None:
        if args.index < 1 or args.index > len(pool):
            raise BotPostError(f"--index must be between 1 and {len(pool)}")
        return (pool[args.index - 1],)

    if args.all:
        return pool

    # Default: first message of the selected language set.
    return (pool[0],)


def print_message_list(langs: list[str] | None = None) -> None:
    """Print numbered demo messages for the selected languages."""
    codes = langs or ["en"]
    pool = messages_for_langs(codes)
    print(f"Built-in demo test messages ({', '.join(codes)}):")
    for index, message in enumerate(pool, start=1):
        print(f"  {index}. {message}")


def print_lang_list() -> None:
    """Print supported language codes."""
    print("Supported languages:")
    for code in SUPPORTED_LANGS:
        count = len(TEST_MESSAGES_BY_LANG[code])
        print(f"  {code}  ({count} messages)")
    print("  mix / all  (every language, interleaved)")


def print_results(config: BotPostConfig, results: list[PostResult]) -> None:
    """Print a human-readable summary."""
    print(f"\nTarget channel: {config.channel}")
    success_count = sum(1 for item in results if item.ok)
    print(f"Posted {success_count}/{len(results)} message(s)")
    for result in results:
        status = "OK" if result.ok else "FAILED"
        preview = result.message_text[:80].replace("\n", " ")
        if result.ok:
            print(f"  [{status}] message_id={result.message_id} :: {preview}")
        else:
            print(f"  [{status}] {preview}")
            print(f"         {result.error}")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    setup_logging()
    args = parse_args(argv)

    if args.list_langs:
        print_lang_list()
        return 0

    if args.list:
        try:
            langs = parse_lang_codes(args.lang)
        except BotPostError as exc:
            print(f"Error: {exc}")
            return 1
        print_message_list(langs)
        return 0

    try:
        config = load_bot_post_config()
        messages = select_messages(args)
    except BotPostError as exc:
        print(f"Error: {exc}")
        print("\nSetup checklist:")
        print("  1. Message @BotFather -> /newbot -> copy token to TELEGRAM_BOT_TOKEN in .env")
        print("  2. Open your channel -> Manage -> Administrators -> Add bot -> allow Post messages")
        print("  3. Set TEST_CHANNEL_USERNAME=osint_test_lab in .env (no @ needed)")
        return 1

    if not messages:
        print("No messages selected.")
        return 1

    results = post_test_messages(config, messages)
    print_results(config, results)

    if not all(item.ok for item in results):
        print(
            "\nIf posting failed, confirm the bot is an admin in the channel "
            "with permission to post messages."
        )
        return 1

    print("\nNext steps:")
    print("  1. Run scrape on the test channel")
    print("  2. Run .\\dashboard.bat for live local Next.js (Mongo via FastAPI)")
    print("  3. Or run export.bat + vercel_export.bat and push for Vercel")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
