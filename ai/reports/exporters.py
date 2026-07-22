"""Export generated AI reports to Markdown / HTML (PDF reserved for later)."""

from __future__ import annotations

import html
from pathlib import Path

from ai.models.schemas import InsightRecord
from ai.reports.models import GeneratedReport


class ReportExporter:
    """Serialize report artifacts for analyst export workflows.

    Markdown and HTML are supported now. PDF is reserved for a future phase
    (API stable; implementation not bundled).
    """

    def to_markdown(self, report: GeneratedReport) -> str:
        """Return Markdown text for ``report``."""
        if report.body_markdown.strip():
            return report.body_markdown
        lines = [f"# {report.title}", ""]
        for section in report.sections:
            lines.append(f"## {section.title}")
            lines.append("")
            lines.append(section.body.strip() or "_(No content)_")
            lines.append("")
        lines.append("## Citations")
        lines.append("")
        if report.citations:
            for cite in report.citations:
                label = cite.label or f"{cite.source_type}:{cite.source_id}"
                snippet = (cite.snippet or "").replace("\n", " ").strip()
                lines.append(f"- **{label}** — {snippet}")
        else:
            lines.append("- _(No citations)_")
        lines.append("")
        lines.append(f"**Confidence:** {report.confidence}")
        lines.append("")
        return "\n".join(lines)

    def to_html(self, report: GeneratedReport) -> str:
        """Return a simple standalone HTML document for ``report``."""
        parts: list[str] = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8"/>',
            f"<title>{html.escape(report.title)}</title>",
            "<style>",
            "body{font-family:Georgia,serif;max-width:48rem;margin:2rem auto;padding:0 1rem;line-height:1.5;color:#1a1a1a;}",
            "h1,h2{font-family:system-ui,sans-serif;}",
            "h2{margin-top:1.75rem;border-bottom:1px solid #ddd;padding-bottom:.25rem;}",
            "pre,code{font-family:ui-monospace,monospace;}",
            ".meta{color:#555;font-size:.9rem;}",
            ".cite{margin:.35rem 0;}",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>{html.escape(report.title)}</h1>",
            (
                f'<p class="meta">Type: {html.escape(report.report_type)} · '
                f"Subject: {html.escape(report.subject_type)}/"
                f"{html.escape(report.subject_id)} · "
                f"Confidence: {html.escape(report.confidence)}</p>"
            ),
        ]
        for section in report.sections:
            parts.append(f"<h2>{html.escape(section.title)}</h2>")
            body = html.escape(section.body or "").replace("\n", "<br/>\n")
            parts.append(f"<p>{body}</p>")
        parts.append("<h2>Citations</h2>")
        if report.citations:
            parts.append("<ul>")
            for cite in report.citations:
                label = cite.label or f"{cite.source_type}:{cite.source_id}"
                snippet = (cite.snippet or "").replace("\n", " ").strip()
                parts.append(
                    f'<li class="cite"><strong>{html.escape(label)}</strong> — '
                    f"{html.escape(snippet)}</li>"
                )
            parts.append("</ul>")
        else:
            parts.append("<p><em>No citations</em></p>")
        parts.extend(["</body>", "</html>", ""])
        return "\n".join(parts)

    def export_markdown(self, report: GeneratedReport, destination: Path) -> Path:
        """Write Markdown to ``destination`` (creates parent dirs)."""
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_markdown(report), encoding="utf-8")
        return path

    def export_html(self, report: GeneratedReport, destination: Path) -> Path:
        """Write HTML to ``destination`` (creates parent dirs)."""
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_html(report), encoding="utf-8")
        return path

    def export_pdf(self, report: GeneratedReport, destination: Path) -> Path:
        """Reserved for a future PDF renderer.

        Raises:
            NotImplementedError: PDF export is not bundled in Phase 9.
        """
        raise NotImplementedError(
            "PDF export is reserved for a future phase. "
            "Use export_markdown() or export_html() for now. "
            f"(requested path: {destination})"
        )

    # --- InsightRecord compatibility (legacy stub API) ---

    def export_markdown_insight(
        self, insight: InsightRecord, destination: Path
    ) -> Path:
        """Export an ``InsightRecord`` body as Markdown."""
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"# {insight.title}", "", insight.body or "", ""]
        if insight.citations:
            lines.append("## Citations")
            lines.append("")
            for cite in insight.citations:
                label = cite.label or f"{cite.source_type}:{cite.source_id}"
                lines.append(f"- {label}: {(cite.snippet or '')[:200]}")
            lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
