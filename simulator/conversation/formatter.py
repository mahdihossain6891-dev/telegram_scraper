"""Persona-aware text formatting."""

from __future__ import annotations

import random

from simulator.personas.profiles import Persona


def format_message_text(
    persona: Persona,
    base_text: str,
    *,
    topic: str,
    rng: random.Random,
    length_multiplier: float = 1.0,
    vocabulary_terms: tuple[str, ...] = (),
) -> str:
    """Render text in a style that roughly matches the persona."""
    style = persona.writing_style
    text = base_text

    if style == "technical":
        text = f"{base_text} In practice, {topic} usually depends on the exact setup."
    elif style == "formal":
        text = f"{base_text} I believe the context around {topic} matters here."
    elif style == "professional":
        text = f"{base_text} From my side, {topic} seems manageable with a clear process."
    elif style == "very_short":
        text = rng.choice([f"Yes, {topic}.", f"Not really.", f"Maybe later.", f"Depends on {topic}."])
    elif style == "verbose":
        text = (
            f"{base_text} I've seen a few different approaches to {topic}, and the best one "
            "usually depends on whether people care more about speed, simplicity, or maintenance."
        )
    elif style == "emoji_heavy":
        text = f"{base_text} {rng.choice(['😂', '🔥', '🚀', '✨'])}"
    elif style == "emoji_free":
        text = base_text.replace("!", ".")
    elif style == "uses_slang":
        text = f"{base_text} kinda feels like {topic} is the move tbh."
    elif style == "uses_abbreviations":
        text = f"{base_text} IMO {topic} is still solid rn."
    elif style == "grammar_mistakes":
        text = f"{base_text} {topic} not easy but can do."
    elif style == "mixes_english_bengali":
        text = f"{base_text} {topic} niye amar mone hoy eta bhalo option."
    elif style == "mixes_english_hindi":
        text = f"{base_text} {topic} pe honestly ye kaafi useful lagta hai."
    elif style == "mixes_english_urdu":
        text = f"{base_text} {topic} ke hawalay se ye theek lag raha hai."
    elif style == "mixes_english_malay":
        text = f"{base_text} pasal {topic}, saya rasa memang practical."
    elif style == "unusual_punctuation":
        text = f"{base_text} ... {topic}? maybe??"

    if vocabulary_terms and rng.random() < 0.35:
        term = rng.choice(vocabulary_terms)
        text = f"{text} ({term})"
    if persona.emoji_frequency > 0.25 and style not in {"emoji_heavy", "emoji_free"}:
        text = f"{text} {rng.choice(['🙂', '👍', '😅'])}"
    return text[: max(24, int(persona.average_message_length * 2 * length_multiplier))]
