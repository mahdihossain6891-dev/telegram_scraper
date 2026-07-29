import { CONTENT_ENTITY_TYPES, KEYWORD_ENTITY_TYPES } from "./constants";
import {
  buildPersonnelFromPayload,
  filterAndSortPersonnel,
  type PersonnelFilters,
} from "./personnel";
import { enrichPersonnelRisk, keywordWeight } from "./risk";
import type { ExportPayload, PersonnelRow } from "./types";

export type TimelineEventKind =
  | "joined"
  | "keyword"
  | "media"
  | "contact"
  | "flagged";

export type TimelineEvent = {
  id: string;
  user_id: number;
  timestamp: string | null;
  date_key: string;
  kind: TimelineEventKind;
  title: string;
  detail: string;
  group_name: string;
  chat_id: number;
  categories: string[];
  keywords: string[];
  media_type?: string | null;
  risk_score: number;
  risk_level: string;
  message_row_id: number;
  text: string | null;
};

export type TimelineDayGroup = {
  date_key: string;
  label: string;
  events: TimelineEvent[];
};

export type SuspectTimeline = {
  suspect: PersonnelRow;
  events: TimelineEvent[];
  days: TimelineDayGroup[];
};

const GENERIC_KEYWORDS = new Set([
  "drug",
  "drugs",
  "narcotic",
  "narcotics",
  "gun",
  "guns",
  "weapon",
  "weapons",
  "firearm",
  "firearms",
  "trafficking",
  "smuggling",
  "smuggle",
]);

const IMAGE_MEDIA = new Set(["photo", "image", "sticker", "animation", "gif"]);

function dateKey(timestamp: string | null | undefined): string {
  if (!timestamp) {
    return "unknown";
  }
  return timestamp.slice(0, 10);
}

function formatDayLabel(key: string): string {
  if (key === "unknown") {
    return "Unknown date";
  }
  const date = new Date(`${key}T12:00:00`);
  if (Number.isNaN(date.getTime())) {
    return key;
  }
  return date.toLocaleDateString(undefined, {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

function pickPrimaryKeyword(keywords: string[]): string | null {
  if (!keywords.length) {
    return null;
  }
  const ranked = keywords
    .slice()
    .sort((a, b) => {
      const genericPenalty = (kw: string) => (GENERIC_KEYWORDS.has(kw.toLowerCase()) ? -50 : 0);
      return keywordWeight(b) + genericPenalty(b) - (keywordWeight(a) + genericPenalty(a));
    });
  return ranked[0] || null;
}

function mediaLabel(mediaType: string | null | undefined): string {
  const raw = (mediaType || "").toLowerCase();
  if (IMAGE_MEDIA.has(raw) || raw.includes("photo") || raw.includes("image")) {
    return "image";
  }
  if (raw.includes("video")) {
    return "video";
  }
  if (raw.includes("document") || raw.includes("file")) {
    return "document";
  }
  if (raw) {
    return raw;
  }
  return "media";
}

function contactTitle(entityType: string, value: string): string {
  switch (entityType) {
    case "phone":
      return "Shared phone number";
    case "email":
      return "Shared email address";
    case "url":
    case "domain":
      return "Shared link";
    case "mention":
      return `Mentioned ${value.startsWith("@") ? value : `@${value}`}`;
    case "hashtag":
      return `Used hashtag ${value.startsWith("#") ? value : `#${value}`}`;
    default:
      return `Shared ${entityType}`;
  }
}

function excerpt(text: string | null | undefined, max = 140): string {
  const cleaned = (text || "").replace(/\s+/g, " ").trim();
  if (!cleaned) {
    return "";
  }
  if (cleaned.length <= max) {
    return cleaned;
  }
  return `${cleaned.slice(0, max - 1)}…`;
}

/** Build a chronological criminal activity timeline for one suspect. */
export function buildSuspectTimeline(
  payload: ExportPayload,
  userId: number,
): SuspectTimeline | null {
  const suspects = buildPersonnelFromPayload(payload).map(enrichPersonnelRisk);
  const suspect = suspects.find((row) => row.user_id === userId);
  if (!suspect) {
    return null;
  }

  const chats = new Map(payload.chats.map((chat) => [chat.id, chat]));
  const keywordByMessage = new Map<number, { categories: string[]; keywords: string[] }>();
  const contentByMessage = new Map<number, Array<{ type: string; value: string }>>();

  for (const entity of payload.entities) {
    if (KEYWORD_ENTITY_TYPES.has(entity.entity_type)) {
      const bucket = keywordByMessage.get(entity.message_row_id) ?? {
        categories: [],
        keywords: [],
      };
      if (!bucket.categories.includes(entity.entity_type)) {
        bucket.categories.push(entity.entity_type);
      }
      if (!bucket.keywords.includes(entity.entity_value)) {
        bucket.keywords.push(entity.entity_value);
      }
      keywordByMessage.set(entity.message_row_id, bucket);
      continue;
    }
    if (CONTENT_ENTITY_TYPES.has(entity.entity_type)) {
      const bucket = contentByMessage.get(entity.message_row_id) ?? [];
      bucket.push({ type: entity.entity_type, value: entity.entity_value });
      contentByMessage.set(entity.message_row_id, bucket);
    }
  }

  const userMessages = payload.messages
    .filter((message) => message.sender_id === userId)
    .slice()
    .sort((a, b) => String(a.timestamp || "").localeCompare(String(b.timestamp || "")));

  const seenChats = new Set<number>();
  const events: TimelineEvent[] = [];

  for (const message of userMessages) {
    const flags = keywordByMessage.get(message.id) ?? { categories: [], keywords: [] };
    const content = contentByMessage.get(message.id) ?? [];
    const groupName =
      chats.get(message.chat_id)?.title ||
      chats.get(message.chat_id)?.username ||
      `Chat ${message.chat_id}`;
    const riskScore = message.risk_score ?? 0;
    const riskLevel = message.risk_level || "Low";
    const ts = message.timestamp;
    const day = dateKey(ts);
    const textExcerpt = excerpt(message.text);

    if (!seenChats.has(message.chat_id)) {
      seenChats.add(message.chat_id);
      events.push({
        id: `joined-${userId}-${message.chat_id}-${message.id}`,
        user_id: userId,
        timestamp: ts,
        date_key: day,
        kind: "joined",
        title: `Joined ${groupName}`,
        detail: "First observed activity in this group or channel",
        group_name: groupName,
        chat_id: message.chat_id,
        categories: [],
        keywords: [],
        media_type: message.media_type,
        risk_score: riskScore,
        risk_level: riskLevel,
        message_row_id: message.id,
        text: message.text,
      });
    }

    const primaryKeyword = pickPrimaryKeyword(flags.keywords);
    const hasFirearms = flags.categories.includes("firearms");
    const media = mediaLabel(message.media_type);
    const hasMedia = Boolean(message.media_type);

    if (hasMedia && hasFirearms) {
      events.push({
        id: `media-${message.id}`,
        user_id: userId,
        timestamp: ts,
        date_key: day,
        kind: "media",
        title: `Posted weapon ${media}`,
        detail: textExcerpt || `Weapon-related ${media} in ${groupName}`,
        group_name: groupName,
        chat_id: message.chat_id,
        categories: flags.categories,
        keywords: flags.keywords,
        media_type: message.media_type,
        risk_score: riskScore,
        risk_level: riskLevel,
        message_row_id: message.id,
        text: message.text,
      });
    } else if (primaryKeyword) {
      events.push({
        id: `keyword-${message.id}-${primaryKeyword}`,
        user_id: userId,
        timestamp: ts,
        date_key: day,
        kind: "keyword",
        title: `Mentioned ${primaryKeyword}`,
        detail: textExcerpt || `Flagged in ${groupName}`,
        group_name: groupName,
        chat_id: message.chat_id,
        categories: flags.categories,
        keywords: flags.keywords,
        media_type: message.media_type,
        risk_score: riskScore,
        risk_level: riskLevel,
        message_row_id: message.id,
        text: message.text,
      });
    } else if (flags.keywords.length || flags.categories.length) {
      events.push({
        id: `flagged-${message.id}`,
        user_id: userId,
        timestamp: ts,
        date_key: day,
        kind: "flagged",
        title: "Flagged activity",
        detail: textExcerpt || `Suspicious message in ${groupName}`,
        group_name: groupName,
        chat_id: message.chat_id,
        categories: flags.categories,
        keywords: flags.keywords,
        media_type: message.media_type,
        risk_score: riskScore,
        risk_level: riskLevel,
        message_row_id: message.id,
        text: message.text,
      });
    }

    const seenContacts = new Set<string>();
    for (const item of content) {
      const key = `${item.type}:${item.value}`;
      if (seenContacts.has(key)) {
        continue;
      }
      seenContacts.add(key);
      events.push({
        id: `contact-${message.id}-${item.type}-${item.value}`,
        user_id: userId,
        timestamp: ts,
        date_key: day,
        kind: "contact",
        title: contactTitle(item.type, item.value),
        detail: item.value,
        group_name: groupName,
        chat_id: message.chat_id,
        categories: flags.categories,
        keywords: flags.keywords,
        media_type: message.media_type,
        risk_score: riskScore,
        risk_level: riskLevel,
        message_row_id: message.id,
        text: message.text,
      });
    }
  }

  events.sort((a, b) => {
    const byTime = String(a.timestamp || "").localeCompare(String(b.timestamp || ""));
    if (byTime !== 0) {
      return byTime;
    }
    const kindOrder: Record<TimelineEventKind, number> = {
      joined: 0,
      keyword: 1,
      media: 1,
      contact: 2,
      flagged: 3,
    };
    return kindOrder[a.kind] - kindOrder[b.kind];
  });

  const dayMap = new Map<string, TimelineEvent[]>();
  for (const event of events) {
    const bucket = dayMap.get(event.date_key) ?? [];
    bucket.push(event);
    dayMap.set(event.date_key, bucket);
  }

  const days: TimelineDayGroup[] = Array.from(dayMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, dayEvents]) => ({
      date_key: key,
      label: formatDayLabel(key),
      events: dayEvents,
    }));

  return { suspect, events, days };
}

export function listSuspects(
  payload: ExportPayload,
  filters?: Partial<PersonnelFilters>,
): PersonnelRow[] {
  const base = buildPersonnelFromPayload(payload).map(enrichPersonnelRisk);
  const merged: PersonnelFilters = {
    chatId: null,
    suspiciousOnly: true,
    keyword: "",
    query: "",
    dateFrom: "",
    dateTo: "",
    useDateFilter: false,
    sortBy: "suspicious_count",
    ...filters,
  };
  const rows = filterAndSortPersonnel(base, merged);
  return rows.sort((a, b) => {
    const scoreDiff = (b.risk_score ?? 0) - (a.risk_score ?? 0);
    if (scoreDiff !== 0) {
      return scoreDiff;
    }
    return b.suspicious_count - a.suspicious_count;
  });
}

export function eventKindLabel(kind: TimelineEventKind): string {
  switch (kind) {
    case "joined":
      return "Joined group";
    case "keyword":
      return "Keyword hit";
    case "media":
      return "Media";
    case "contact":
      return "Contact / link";
    default:
      return "Flagged";
  }
}
