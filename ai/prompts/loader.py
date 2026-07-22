"""PromptLoader — load versioned Markdown prompts with variable substitution.

Prompt text is never defined in Python. Templates live under::

    <prompts_root>/templates/<prompt_id>/vN.md

Example::

    from ai.prompts import PromptLoader

    loader = PromptLoader()
    rendered = loader.render(
        "rag_answer",
        version="v1",
        question="Who forwarded the most?",
        evidence_chunks="...",
        citation_instructions="Cite source_id values.",
    )
    print(rendered.text)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from ai.config import get_ai_settings
from ai.prompts.errors import (
    PromptNotFoundError,
    PromptParseError,
    PromptRenderError,
)
from ai.prompts.models import PromptTemplate, RenderedPrompt

logger = logging.getLogger("ai.prompts.loader")

# {{variable_name}} — identifiers only (no spaces / dotted paths in Phase 3).
_VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")
_VERSION_FILE = re.compile(r"^v(\d+)\.md$", re.IGNORECASE)

# Well-known prompt ids shipped with the package (documentation / validation aid).
KNOWN_PROMPT_IDS: tuple[str, ...] = (
    "message_classification",
    "investigation_summary",
    "rag_answer",
    "case_report",
    "investigation_assistant",
    "entity_extraction",
    "structured_report",
)


def default_prompts_root() -> Path:
    """Return the package prompts root (``ai/prompts``), honoring ``AI_PROMPTS_DIR``."""
    return Path(get_ai_settings().prompts_dir)


def _parse_front_matter(raw: str) -> tuple[dict[str, Any], str]:
    """Parse optional ``---`` YAML-like front matter without PyYAML."""
    text = raw.replace("\r\n", "\n")
    if not text.startswith("---"):
        return {}, text

    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text

    meta_lines: list[str] = []
    end_index = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_index = idx
            break
        meta_lines.append(lines[idx])

    if end_index is None:
        raise PromptParseError("Unterminated YAML front matter (missing closing ---).")

    body = "\n".join(lines[end_index + 1 :]).lstrip("\n")
    meta = _parse_simple_yaml(meta_lines)
    return meta, body


def _parse_simple_yaml(lines: Iterable[str]) -> dict[str, Any]:
    """Minimal YAML subset: ``key: value`` and ``key:`` + indented ``- item`` lists."""
    result: dict[str, Any] = {}
    current_list_key: str | None = None

    for raw_line in lines:
        if not raw_line.strip() or raw_line.strip().startswith("#"):
            continue

        # List item under a previous key
        list_match = re.match(r"^-\s+(.*)$", raw_line.strip())
        if list_match and current_list_key is not None and raw_line.startswith((" ", "\t")):
            item = list_match.group(1).strip().strip("\"'")
            bucket = result.setdefault(current_list_key, [])
            if not isinstance(bucket, list):
                raise PromptParseError(
                    f"Front matter key {current_list_key!r} is not a list."
                )
            bucket.append(item)
            continue

        # Indented list item without relying on strip for detecting indent
        indented_list = re.match(r"^\s+-\s+(.*)$", raw_line)
        if indented_list and current_list_key is not None:
            item = indented_list.group(1).strip().strip("\"'")
            bucket = result.setdefault(current_list_key, [])
            if not isinstance(bucket, list):
                raise PromptParseError(
                    f"Front matter key {current_list_key!r} is not a list."
                )
            bucket.append(item)
            continue

        kv = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", raw_line.strip())
        if not kv:
            raise PromptParseError(f"Cannot parse front matter line: {raw_line!r}")

        key, value = kv.group(1), kv.group(2).strip()
        if value == "":
            current_list_key = key
            result[key] = []
            continue

        current_list_key = None
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        result[key] = value

    return result


def extract_placeholders(body: str) -> tuple[str, ...]:
    """Return unique ``{{variable}}`` names in appearance order."""
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _VAR_PATTERN.finditer(body):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    return tuple(ordered)


def _version_sort_key(version: str) -> tuple[int, str]:
    match = re.match(r"^v(\d+)$", version.strip(), re.IGNORECASE)
    if match:
        return (int(match.group(1)), version.lower())
    return (-1, version.lower())


def render_template(
    body: str,
    variables: Mapping[str, Any],
    *,
    strict: bool = True,
    template_key: str = "",
) -> str:
    """Substitute ``{{var}}`` placeholders using ``variables``.

    Args:
        body: Template Markdown body.
        variables: Mapping of placeholder names to values (converted via ``str``).
        strict: If True, missing placeholders raise ``PromptRenderError``.
            If False, missing placeholders are left intact.
        template_key: Optional id@version for error messages.
    """
    required = extract_placeholders(body)
    missing = [name for name in required if name not in variables]
    if missing and strict:
        raise PromptRenderError(
            f"Missing prompt variables for {template_key or 'template'}: "
            f"{', '.join(missing)}"
        )

    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in variables:
            return match.group(0)
        value = variables[name]
        if value is None:
            return ""
        return str(value)

    return _VAR_PATTERN.sub(repl, body)


class PromptLoader:
    """Load and render versioned Markdown prompts from disk."""

    def __init__(self, root: Path | str | None = None) -> None:
        """
        Args:
            root: Prompts package root containing a ``templates/`` directory.
                Defaults to ``AI_PROMPTS_DIR`` / package ``ai/prompts``.
        """
        self.root = Path(root) if root is not None else default_prompts_root()
        self.templates_dir = self.root / "templates"
        self._cache: dict[tuple[str, str], PromptTemplate] = {}

    def clear_cache(self) -> None:
        """Drop in-memory template cache."""
        self._cache.clear()

    def list_prompt_ids(self) -> list[str]:
        """Return prompt ids that have at least one version file."""
        if not self.templates_dir.is_dir():
            return []
        ids = [
            path.name
            for path in sorted(self.templates_dir.iterdir())
            if path.is_dir() and self.list_versions(path.name)
        ]
        return ids

    def list_versions(self, prompt_id: str) -> list[str]:
        """Return available versions for ``prompt_id`` (e.g. ``['v1', 'v2']``)."""
        folder = self.templates_dir / prompt_id
        if not folder.is_dir():
            return []
        versions: list[str] = []
        for path in folder.iterdir():
            if path.is_file() and _VERSION_FILE.match(path.name):
                versions.append(path.stem.lower())
        versions.sort(key=_version_sort_key)
        return versions

    def latest_version(self, prompt_id: str) -> str:
        """Return the highest ``vN`` for ``prompt_id``."""
        versions = self.list_versions(prompt_id)
        if not versions:
            raise PromptNotFoundError(
                f"No versions found for prompt {prompt_id!r} under {self.templates_dir}"
            )
        return versions[-1]

    def resolve_version(self, prompt_id: str, version: str | None) -> str:
        """Resolve ``None`` / ``'latest'`` to a concrete version string."""
        if version is None or version.strip().lower() in {"", "latest"}:
            return self.latest_version(prompt_id)
        return version.strip().lower()

    def _path_for(self, prompt_id: str, version: str) -> Path:
        return self.templates_dir / prompt_id / f"{version}.md"

    def load(self, prompt_id: str, version: str | None = "latest") -> PromptTemplate:
        """Load a prompt template from Markdown (cached)."""
        resolved = self.resolve_version(prompt_id, version)
        cache_key = (prompt_id, resolved)
        if cache_key in self._cache:
            return self._cache[cache_key]

        path = self._path_for(prompt_id, resolved)
        if not path.is_file():
            available = self.list_versions(prompt_id)
            raise PromptNotFoundError(
                f"Prompt not found: {prompt_id}@{resolved} (path={path}). "
                f"Available versions: {available or 'none'}"
            )

        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise PromptParseError(f"Could not read prompt file {path}: {exc}") from exc

        meta, body = _parse_front_matter(raw)
        meta_id = str(meta.get("id") or prompt_id).strip()
        meta_version = str(meta.get("version") or resolved).strip().lower()
        description = str(meta.get("description") or "").strip()

        declared = meta.get("variables")
        if declared is None:
            variables = extract_placeholders(body)
        elif isinstance(declared, list):
            variables = tuple(str(item).strip() for item in declared if str(item).strip())
        else:
            raise PromptParseError(
                f"Front matter 'variables' must be a list in {path}"
            )

        # Ensure body placeholders are covered by declared list (union).
        body_vars = extract_placeholders(body)
        merged = tuple(dict.fromkeys([*variables, *body_vars]))

        if meta_id != prompt_id:
            logger.warning(
                "prompt_id_mismatch",
                extra={
                    "ai_prompt_id": prompt_id,
                    "ai_front_matter_id": meta_id,
                    "ai_prompt_path": str(path),
                },
            )
        if meta_version != resolved:
            logger.warning(
                "prompt_version_mismatch",
                extra={
                    "ai_prompt_id": prompt_id,
                    "ai_requested_version": resolved,
                    "ai_front_matter_version": meta_version,
                    "ai_prompt_path": str(path),
                },
            )

        template = PromptTemplate(
            id=prompt_id,
            version=resolved,
            description=description,
            body=body,
            variables=merged,
            path=str(path.resolve()),
        )
        self._cache[cache_key] = template
        logger.debug(
            "prompt_loaded",
            extra={
                "ai_prompt_id": prompt_id,
                "ai_prompt_version": resolved,
                "ai_prompt_variables": list(merged),
            },
        )
        return template

    def render(
        self,
        prompt_id: str,
        version: str | None = "latest",
        *,
        strict: bool = True,
        **variables: Any,
    ) -> RenderedPrompt:
        """Load ``prompt_id`` and substitute ``variables``."""
        template = self.load(prompt_id, version=version)
        text = render_template(
            template.body,
            variables,
            strict=strict,
            template_key=template.key,
        )
        used = tuple(name for name in template.variables if name in variables)
        return RenderedPrompt(
            id=template.id,
            version=template.version,
            text=text,
            variables_used=used,
        )

    def get_raw_body(self, prompt_id: str, version: str | None = "latest") -> str:
        """Return the unrendered Markdown body (no substitution)."""
        return self.load(prompt_id, version=version).body
