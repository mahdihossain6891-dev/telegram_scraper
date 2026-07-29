"""Keyword detection for flagging messages of analytical interest."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Category = Literal["narcotics", "human_trafficking", "firearms"]

# OSINT-oriented terms for analyst review. Extend via future configuration if needed.
# Includes non-English terms so multilingual lab posts can be flagged without Latin keywords.
KEYWORDS_BY_CATEGORY: dict[Category, tuple[str, ...]] = {
    "narcotics": (
        "cocaine",
        "heroin",
        "fentanyl",
        "methamphetamine",
        "meth",
        "opioid",
        "narcotic",
        "narcotics",
        "drug trafficking",
        "drug smuggling",
        "drug deal",
        "drug dealer",
        "smuggling drugs",
        "illicit drugs",
        "synthetic drugs",
        "drug",
        "drugs",
        # Spanish / Portuguese / French / German
        "cocaína",
        "cocaina",
        "heroína",
        "heroina",
        "metanfetamina",
        "fentanilo",
        "fentanil",
        "estupefacientes",
        "narcotráfico",
        "narcotrafico",
        "trafic de drogue",
        "héroïne",
        "méthamphétamine",
        "stupéfiants",
        "drogenhandel",
        "methamphetamin",
        "kokain",
        "cocaïne",
        # Arabic
        "كوكايين",
        "هيروين",
        "فنتانيل",
        "ميثامفيتامين",
        "ميث",
        "مخدرات",
        "اتجار بالمخدرات",
        "شحنة مخدرات",
        # Russian
        "кокаин",
        "героин",
        "фентанил",
        "метамфетамин",
        "наркотики",
        "наркоторговля",
        # Bengali / Hindi
        "কোকেইন",
        "হেরোইন",
        "ফেন্টানিল",
        "মাদক",
        "মাদক পাচার",
        "कोकीन",
        "हेरोइन",
        "फेंटानिल",
        "नशीली दवाएं",
        "नशे का व्यापार",
        # Chinese
        "可卡因",
        "海洛因",
        "芬太尼",
        "冰毒",
        "毒品",
        "贩毒",
    ),
    "human_trafficking": (
        "passport for sale",
        "passports for sale",
        "fake passport",
        "human trafficking",
        "sex trafficking",
        "trafficking victims",
        "trafficking ring",
        "trafficking",
        "forced labor",
        "forced labour",
        "modern slavery",
        "smuggling persons",
        "child exploitation",
        "labor trafficking",
        "labour trafficking",
        "human smuggling",
        # Spanish / Portuguese / French / German
        "trata de personas",
        "tráfico de personas",
        "tráfico humano",
        "explotación sexual",
        "trabalho forçado",
        "tráfico de pessoas",
        "traite des êtres humains",
        "trafic d'êtres humains",
        "exploitation sexuelle",
        "menschenhandel",
        "zwangsarbeit",
        # Arabic
        "الاتجار بالبشر",
        "اتجار بالبشر",
        "تهريب البشر",
        "استغلال جنسي",
        "عمل قسري",
        # Russian
        "торговля людьми",
        "секс-торговля",
        "принудительный труд",
        # Bengali / Hindi
        "মানব পাচার",
        "যৌন পাচার",
        "জোরপূর্বক শ্রম",
        "मानव तस्करी",
        "यौन तस्करी",
        "जबरन मजदूरी",
        # Chinese
        "人口贩运",
        "人口贩卖",
        "强迫劳动",
        "性剥削",
    ),
    "firearms": (
        "illegal gun",
        "illegal guns",
        "firearms trafficking",
        "gun smuggling",
        "weapons trafficking",
        "weapon smuggling",
        "ghost gun",
        "ghost guns",
        "untraceable gun",
        "ammunition deal",
        "illegal weapons",
        "assault rifle sale",
        "ak-47",
        "ak47",
        "arms trafficking",
        "gun running",
        "gun",
        "guns",
        "weapon",
        "weapons",
        "firearm",
        "firearms",
        "smuggling",
        "smuggle",
        # Spanish / Portuguese / French / German
        "arma ilegal",
        "armas ilegales",
        "tráfico de armas",
        "rifle de asalto",
        "arma de fuego",
        "armas de fogo",
        "tráfico de armas",
        "arme illégale",
        "trafic d'armes",
        "fusil d'assaut",
        "illegale waffe",
        "waffenhandel",
        "sturmgewehr",
        # Arabic
        "سلاح غير قانوني",
        "أسلحة غير قانونية",
        "اتجار بالأسلحة",
        "تهريب أسلحة",
        "بندقية هجومية",
        "سلاح ناري",
        "ذخيرة",
        # Russian
        "нелегальное оружие",
        "нелегальный ствол",
        "торговля оружием",
        "контрабанда оружия",
        "штурмовая винтовка",
        # Bengali / Hindi
        "অবৈধ অস্ত্র",
        "অস্ত্র পাচার",
        "আক্রমণাত্মক রাইফেল",
        "অবৈধ বন্দুক",
        "अवैध हथियार",
        "हथियार तस्करी",
        "असॉल्ट राइफल",
        # Chinese
        "非法枪支",
        "武器走私",
        "枪支贩运",
        "突击步枪",
        "弹药交易",
    ),
}


@dataclass(frozen=True)
class KeywordHit:
    """A keyword match within message text."""

    category: Category
    keyword: str


@dataclass(frozen=True)
class KeywordScanResult:
    """All keyword matches found in a message."""

    hits: tuple[KeywordHit, ...]

    @property
    def matched(self) -> bool:
        return bool(self.hits)

    @property
    def categories(self) -> tuple[Category, ...]:
        seen: list[Category] = []
        for hit in self.hits:
            if hit.category not in seen:
                seen.append(hit.category)
        return tuple(seen)


def _keyword_needs_simple_match(keyword: str) -> bool:
    """Non-Latin scripts / spaced phrases should not rely on ASCII word boundaries."""
    if " " in keyword:
        return True
    return any(ord(ch) > 127 for ch in keyword)


def _compile_patterns() -> dict[Category, list[tuple[str, re.Pattern[str]]]]:
    """Build regex patterns for each category keyword."""
    compiled: dict[Category, list[tuple[str, re.Pattern[str]]]] = {}
    for category, keywords in KEYWORDS_BY_CATEGORY.items():
        compiled[category] = []
        for keyword in keywords:
            escaped = re.escape(keyword)
            if _keyword_needs_simple_match(keyword):
                pattern = re.compile(escaped, re.IGNORECASE)
            else:
                pattern = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
            compiled[category].append((keyword, pattern))
    return compiled


_PATTERNS = _compile_patterns()


def scan_message_text(text: str | None) -> KeywordScanResult:
    """Return keyword hits for narcotics, human trafficking, or firearms terms."""
    if not text or not text.strip():
        return KeywordScanResult(hits=())

    normalized = text.replace("\u200b", "").replace("\u2019", "'").replace("\u2018", "'").strip()
    hits: list[KeywordHit] = []
    for category, patterns in _PATTERNS.items():
        for keyword, pattern in patterns:
            if pattern.search(normalized):
                hits.append(KeywordHit(category=category, keyword=keyword))

    return KeywordScanResult(hits=tuple(hits))
