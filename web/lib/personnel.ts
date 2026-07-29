import { KEYWORD_ENTITY_TYPES } from "./constants";
import type {
  ExportPayload,
  PersonnelDetail,
  PersonnelMessage,
  PersonnelRow,
  PersonnelSort,
} from "./types";

export type PersonnelFilters = {
  chatId: number | null;
  suspiciousOnly: boolean;
  keyword: string;
  query: string;
  dateFrom: string;
  dateTo: string;
  useDateFilter: boolean;
  sortBy: PersonnelSort;
};

export function defaultPersonnelFilters(): PersonnelFilters {
  return {
    chatId: null,
    suspiciousOnly: false,
    keyword: "",
    query: "",
    dateFrom: "",
    dateTo: "",
    useDateFilter: false,
    sortBy: "suspicious_count",
  };
}

function displayName(
  firstName: string | null | undefined,
  lastName: string | null | undefined,
  username: string | null | undefined,
  userId: number,
): string {
  const parts = [firstName, lastName].filter(Boolean);
  if (parts.length) {
    return parts.join(" ");
  }
  if (username) {
    return `@${username}`;
  }
  return `User ${userId}`;
}

/** Build personnel rows from a full export payload (Vercel / offline fallback). */
export function buildPersonnelFromPayload(payload: ExportPayload): PersonnelRow[] {
  if (payload.personnel?.length) {
    return payload.personnel;
  }

  const users = new Map(payload.users.map((user) => [user.id, user]));
  const chats = new Map(payload.chats.map((chat) => [chat.id, chat]));
  const keywordByMessage = new Map<number, { categories: string[]; keywords: string[] }>();

  for (const entity of payload.entities) {
    if (!KEYWORD_ENTITY_TYPES.has(entity.entity_type)) {
      continue;
    }
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
  }

  type Acc = {
    user_id: number;
    username: string | null;
    first_name: string | null;
    last_name: string | null;
    chat_ids: Set<number>;
    message_count: number;
    suspicious_count: number;
    keywords: Record<string, number>;
    categories: Record<string, number>;
    first_seen: string | null;
    last_seen: string | null;
  };

  const byUser = new Map<number, Acc>();

  for (const message of payload.messages) {
    if (message.sender_id == null) {
      continue;
    }
    const user = users.get(message.sender_id);
    const flags = keywordByMessage.get(message.id) ?? { categories: [], keywords: ["(flagged)"] };
    let acc = byUser.get(message.sender_id);
    if (!acc) {
      acc = {
        user_id: message.sender_id,
        username: user?.username ?? null,
        first_name: user?.first_name ?? null,
        last_name: user?.last_name ?? null,
        chat_ids: new Set(),
        message_count: 0,
        suspicious_count: 0,
        keywords: {},
        categories: {},
        first_seen: null,
        last_seen: null,
      };
      byUser.set(message.sender_id, acc);
    }
    acc.chat_ids.add(message.chat_id);
    acc.message_count += 1;
    acc.suspicious_count += 1;
    for (const keyword of flags.keywords) {
      acc.keywords[keyword] = (acc.keywords[keyword] ?? 0) + 1;
    }
    for (const category of flags.categories) {
      acc.categories[category] = (acc.categories[category] ?? 0) + 1;
    }
    const ts = message.timestamp;
    if (ts) {
      if (!acc.first_seen || ts < acc.first_seen) {
        acc.first_seen = ts;
      }
      if (!acc.last_seen || ts > acc.last_seen) {
        acc.last_seen = ts;
      }
    }
  }

  return Array.from(byUser.values()).map((acc) => {
    const chatIds = Array.from(acc.chat_ids);
    let name = displayName(acc.first_name, acc.last_name, acc.username, acc.user_id);
    if (name.startsWith("User ") && chats.has(acc.user_id)) {
      const chat = chats.get(acc.user_id);
      name = `${chat?.title || chat?.username || `Chat ${acc.user_id}`} (channel)`;
    }
    return {
      user_id: acc.user_id,
      display_name: name,
      username: acc.username,
      first_name: acc.first_name,
      last_name: acc.last_name,
      group_name: chatIds
        .map((id) => chats.get(id)?.title || chats.get(id)?.username || `Chat ${id}`)
        .join(", "),
      chat_ids: chatIds,
      message_count: acc.message_count,
      suspicious_count: acc.suspicious_count,
      keywords: acc.keywords,
      keyword_list: Object.keys(acc.keywords),
      keyword_total: Object.values(acc.keywords).reduce((sum, n) => sum + n, 0),
      categories: acc.categories,
      first_seen: acc.first_seen,
      last_seen: acc.last_seen,
    };
  });
}

export function filterAndSortPersonnel(
  rows: PersonnelRow[],
  filters: PersonnelFilters,
): PersonnelRow[] {
  let result = rows.slice();

  if (filters.chatId != null) {
    result = result.filter((row) => row.chat_ids.includes(filters.chatId as number));
  }
  if (filters.suspiciousOnly) {
    result = result.filter((row) => row.suspicious_count > 0);
  }
  if (filters.keyword.trim()) {
    const needle = filters.keyword.trim().toLowerCase();
    result = result.filter((row) =>
      row.keyword_list.some((keyword) => keyword.toLowerCase().includes(needle)),
    );
  }
  if (filters.query.trim()) {
    const q = filters.query.trim().toLowerCase().replace(/^@/, "");
    result = result.filter((row) => {
      const hay = [
        row.display_name,
        row.username,
        row.first_name,
        row.last_name,
        String(row.user_id),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }
  if (filters.useDateFilter) {
    if (filters.dateFrom) {
      result = result.filter(
        (row) => !row.last_seen || row.last_seen.slice(0, 10) >= filters.dateFrom,
      );
    }
    if (filters.dateTo) {
      result = result.filter(
        (row) => !row.first_seen || row.first_seen.slice(0, 10) <= filters.dateTo,
      );
    }
  }

  const reverse = filters.sortBy !== "display_name";
  result.sort((a, b) => {
    let av: string | number = 0;
    let bv: string | number = 0;
    switch (filters.sortBy) {
      case "message_count":
        av = a.message_count;
        bv = b.message_count;
        break;
      case "last_seen":
        av = a.last_seen || "";
        bv = b.last_seen || "";
        break;
      case "keyword_total":
        av = a.keyword_total;
        bv = b.keyword_total;
        break;
      case "display_name":
        av = a.display_name.toLowerCase();
        bv = b.display_name.toLowerCase();
        break;
      default:
        av = a.suspicious_count;
        bv = b.suspicious_count;
    }
    if (av < bv) {
      return reverse ? 1 : -1;
    }
    if (av > bv) {
      return reverse ? -1 : 1;
    }
    return 0;
  });

  return result;
}

export function buildPersonnelDetailFromPayload(
  payload: ExportPayload,
  userId: number,
): PersonnelDetail | null {
  const rows = buildPersonnelFromPayload(payload);
  const summary = rows.find((row) => row.user_id === userId);
  if (!summary) {
    return null;
  }

  const user = payload.users.find((row) => row.id === userId);
  const chats = new Map(payload.chats.map((chat) => [chat.id, chat]));
  const keywordByMessage = new Map<number, { categories: string[]; keywords: string[] }>();
  for (const entity of payload.entities) {
    if (!KEYWORD_ENTITY_TYPES.has(entity.entity_type)) {
      continue;
    }
    const bucket = keywordByMessage.get(entity.message_row_id) ?? {
      categories: [],
      keywords: [],
    };
    if (!bucket.categories.includes(entity.entity_type)) {
      bucket.categories.push(entity.entity_type);
    }
    bucket.keywords.push(entity.entity_value);
    keywordByMessage.set(entity.message_row_id, bucket);
  }

  const userMessages = payload.messages
    .filter((message) => message.sender_id === userId)
    .slice()
    .sort((a, b) => String(b.timestamp || "").localeCompare(String(a.timestamp || "")));

  const groupStats = new Map<
    number,
    {
      chat_id: number;
      message_count: number;
      suspicious_count: number;
      keywords: Record<string, number>;
      first_seen: string | null;
      last_seen: string | null;
    }
  >();

  const messages: PersonnelMessage[] = userMessages.map((message) => {
    const flags = keywordByMessage.get(message.id) ?? { categories: [], keywords: [] };
    const group = groupStats.get(message.chat_id) ?? {
      chat_id: message.chat_id,
      message_count: 0,
      suspicious_count: 0,
      keywords: {},
      first_seen: null as string | null,
      last_seen: null as string | null,
    };
    group.message_count += 1;
    group.suspicious_count += 1;
    for (const keyword of flags.keywords) {
      group.keywords[keyword] = (group.keywords[keyword] ?? 0) + 1;
    }
    const ts = message.timestamp;
    if (ts) {
      if (!group.first_seen || ts < group.first_seen) {
        group.first_seen = ts;
      }
      if (!group.last_seen || ts > group.last_seen) {
        group.last_seen = ts;
      }
    }
    groupStats.set(message.chat_id, group);

    return {
      id: message.id,
      message_id: message.message_id,
      chat_id: message.chat_id,
      group_name: chats.get(message.chat_id)?.title || `Chat ${message.chat_id}`,
      timestamp: message.timestamp,
      text: message.text,
      media_type: message.media_type,
      views: message.views,
      categories: flags.categories,
      keywords: flags.keywords,
      suspicious: true,
    };
  });

  return {
    user: {
      user_id: userId,
      display_name: summary.display_name,
      username: user?.username ?? summary.username,
      first_name: user?.first_name ?? summary.first_name ?? null,
      last_name: user?.last_name ?? summary.last_name ?? null,
    },
    summary,
    groups: Array.from(groupStats.values())
      .map((group) => ({
        ...group,
        group_name: chats.get(group.chat_id)?.title || `Chat ${group.chat_id}`,
      }))
      .sort((a, b) => b.suspicious_count - a.suspicious_count),
    keyword_frequency: summary.keywords,
    category_frequency: summary.categories || {},
    messages,
  };
}

/** Highlight keyword matches in message text for investigators. */
export function highlightKeywords(text: string, keywords: string[]): string {
  if (!text) {
    return "(no text)";
  }
  if (!keywords.length) {
    return text;
  }
  const unique = Array.from(new Set(keywords.filter(Boolean))).sort(
    (a, b) => b.length - a.length,
  );
  let result = text;
  for (const keyword of unique) {
    const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    result = result.replace(
      new RegExp(`(${escaped})`, "gi"),
      '<mark class="kw-hit">$1</mark>',
    );
  }
  return result;
}
