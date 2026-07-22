import type {
  ChatMessage,
  Confidence,
  ConversationSession,
  EntityKind,
  InvestigationSection,
  InvestigationSectionId,
  RiskLevel,
} from "./types";
import { SECTION_META } from "./types";

export function uid(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function confidenceClass(level: Confidence | undefined): string {
  const v = (level || "low").toLowerCase();
  if (v === "high") return "ai-conf ai-conf-high";
  if (v === "medium") return "ai-conf ai-conf-medium";
  return "ai-conf ai-conf-low";
}

export function riskFromConfidence(
  confidence: Confidence | undefined,
  refused?: boolean,
): RiskLevel {
  if (refused) return "unknown";
  const v = (confidence || "").toLowerCase();
  if (v === "high") return "high";
  if (v === "medium") return "medium";
  if (v === "low") return "low";
  return "unknown";
}

export function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const diff = Date.now() - then;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function caseDescription(session: ConversationSession): string {
  if (session.description?.trim()) return session.description;
  const firstUser = session.messages.find((m) => m.role === "user");
  if (firstUser?.content) {
    const t = firstUser.content.trim();
    return t.length > 90 ? `${t.slice(0, 87)}…` : t;
  }
  return "No activity yet";
}

export function caseRisk(session: ConversationSession): RiskLevel {
  if (session.risk) return session.risk;
  const last = [...session.messages].reverse().find((m) => m.role === "assistant");
  return riskFromConfidence(last?.confidence, last?.refused);
}

export function buildInvestigationQuery(
  text: string,
  entityKind: EntityKind | null,
  entityValue: string,
): string {
  const q = text.trim();
  const entity = entityValue.trim();
  if (!entity || !entityKind) return q;
  const labels: Record<EntityKind, string> = {
    username: "Username",
    group: "Group",
    channel: "Channel",
    wallet: "Wallet",
    phone: "Phone",
    keyword: "Keyword",
  };
  return `[${labels[entityKind]}: ${entity}] ${q}`;
}

/** Prefer numeric user IDs only — matches existing optional subject filter. */
export function extractNumericSubject(
  entityKind: EntityKind | null,
  entityValue: string,
): { user_id: number } | undefined {
  if (entityKind !== "username" && entityKind !== "keyword") return undefined;
  const raw = entityValue.trim();
  if (/^\d+$/.test(raw)) return { user_id: Number(raw) };
  return undefined;
}

/** True when the query looks like a deictic / template with no concrete target. */
export function isTargetlessInvestigationQuery(text: string): boolean {
  const q = (text || "").trim();
  if (!q) return true;
  const patterns = [
    /^investigate this user\b/i,
    /^analyze behavioral anomalies\b/i,
    /^explain this alert\b/i,
    /^find related users\b/i,
    /^generate (a )?(concise )?investigation summary\b/i,
    /^why is this user high risk\??$/i,
    /^show behavioral anomalies\b/i,
    /^produce a structured intelligence report\b/i,
    /^deep-dive into behavioral anomalies\b/i,
    /^investigate connected users linked to this subject\b/i,
    /^describe relationship connections between this subject\b/i,
    /^search for similar activity\b/i,
  ];
  if (patterns.some((re) => re.test(q))) return true;
  // Pronoun-only / no identifiable handle, ID, or proper name token.
  const hasHandle = /@[A-Za-z0-9_]{3,}/.test(q);
  const hasId = /(?:^|[^\w])-?\d{5,}(?:$|[^\w])/.test(q);
  const hasQuoted = /["'“”][^"'“”]{2,}["'“”]/.test(q);
  const hasProper = /\b[A-Z][a-zA-Z'`-]{1,30}(?:\s+[A-Z][a-zA-Z'`-]{1,30}){0,3}\b/.test(
    q.replace(/^(Investigate|Analyze|Explain|Find|Generate|Show|Why)\b/i, ""),
  );
  if (hasHandle || hasId || hasQuoted || hasProper) return false;
  // Short generic verbs without a target noun phrase.
  if (
    /^(investigate|analyze|explain|find|generate|summarize|search)\b/i.test(q) &&
    q.split(/\s+/).length <= 6
  ) {
    return true;
  }
  return false;
}

export function composeActionQuery(
  actionId: string | null | undefined,
  target: string,
  queryTemplate?: string,
): string {
  const t = target.trim();
  if (!t) return "";
  if (queryTemplate) return queryTemplate.replace(/\{target\}/g, t);
  if (!actionId) return t;
  return t;
}

function matchSectionHeader(line: string): InvestigationSectionId | null {
  const cleaned = line
    .replace(/^#{1,6}\s*/, "")
    .replace(/^\*\*|^\*|^\d+[\.\)]\s*/, "")
    .replace(/\*\*$|\*$/g, "")
    .replace(/:$/, "")
    .trim();
  if (!cleaned || cleaned.length > 60) return null;
  for (const meta of SECTION_META) {
    if (meta.patterns.some((re) => re.test(cleaned))) return meta.id;
  }
  return null;
}

/**
 * Split free-form assistant text into investigation sections when headings exist.
 * Falls back to a single Executive Summary card.
 */
export function parseInvestigationSections(content: string): InvestigationSection[] {
  const text = (content || "").trim();
  if (!text) return [];

  const lines = text.split(/\r?\n/);
  const buckets = new Map<InvestigationSectionId, string[]>();
  let current: InvestigationSectionId | null = null;
  let preamble: string[] = [];

  for (const line of lines) {
    const matched = matchSectionHeader(line.trim());
    if (matched) {
      current = matched;
      if (!buckets.has(matched)) buckets.set(matched, []);
      continue;
    }
    if (current) {
      buckets.get(current)!.push(line);
    } else {
      preamble.push(line);
    }
  }

  const sections: InvestigationSection[] = [];
  for (const meta of SECTION_META) {
    const body = (buckets.get(meta.id) || []).join("\n").trim();
    if (body) sections.push({ id: meta.id, title: meta.title, body });
  }

  const intro = preamble.join("\n").trim();
  if (sections.length === 0) {
    return [{ id: "executive_summary", title: "Summary", body: text }];
  }
  if (intro) {
    const existing = sections.find((s) => s.id === "executive_summary");
    if (existing) {
      existing.body = `${intro}\n\n${existing.body}`.trim();
    } else {
      sections.unshift({
        id: "executive_summary",
        title: "Summary",
        body: intro,
      });
    }
  }
  return sections;
}

export function lastAssistant(session: ConversationSession | null): ChatMessage | null {
  if (!session) return null;
  return [...session.messages].reverse().find((m) => m.role === "assistant") || null;
}

export function formatLatency(ms: number | null): string {
  if (ms == null || ms < 0) return "—";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

/** Collapse entity cards that share the same Telegram identity. */
export function dedupeEntityCandidates<
  T extends {
    entity_id?: string | number;
    entity_type?: string;
    display_name?: string;
    username?: string;
    risk_score?: number | null;
    last_seen?: string | null;
    score?: number;
  },
>(candidates: T[]): T[] {
  const best = new Map<string, T>();
  for (const c of candidates) {
    if (c.entity_id == null || c.entity_id === "") continue;
    const idText = String(c.entity_id).trim();
    const numeric = Number(idText);
    const normalizedId = Number.isFinite(numeric) && idText !== "" ? String(numeric) : idText;
    const kind = c.entity_type === "user" || !c.entity_type ? "user" : "chat";
    const key = `${kind}:${normalizedId}`;
    const prev = best.get(key);
    if (!prev) {
      best.set(key, c);
      continue;
    }
    const prevScore = typeof prev.score === "number" ? prev.score : 0;
    const nextScore = typeof c.score === "number" ? c.score : 0;
    const richer =
      nextScore > prevScore
        ? c
        : {
            ...prev,
            display_name: prev.display_name || c.display_name,
            username: prev.username || c.username,
            risk_score: prev.risk_score ?? c.risk_score,
            last_seen: prev.last_seen || c.last_seen,
          };
    best.set(key, richer as T);
  }
  return Array.from(best.values());
}

