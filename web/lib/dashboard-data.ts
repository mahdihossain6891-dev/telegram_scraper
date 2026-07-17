import {
  CONTENT_ENTITY_TYPES,
  KEYWORD_ENTITY_TYPES,
  PRIVATE_CHAT_TYPE,
  STOP_WORDS,
} from "./constants";
import type {
  ChatSummaryRow,
  DashboardFilters,
  DashboardInsights,
  EntityDisplayRow,
  ExportDashboardData,
  ExportPayload,
  MessageDisplayRow,
} from "./types";

export function defaultFilters(chatIds: number[]): DashboardFilters {
  return {
    chatIds,
    categories: [],
    includePrivate: true,
    chatType: "All",
    minMessages: 0,
    dateFrom: "",
    dateTo: "",
    useDateFilter: false,
  };
}

function senderLabel(
  users: ExportPayload["users"],
  senderId: number | null,
): string {
  if (!senderId) {
    return "";
  }
  const user = users.find((item) => item.id === senderId);
  if (!user) {
    return `User ${senderId}`;
  }
  if (user.username && user.first_name) {
    return `${user.first_name} (@${user.username})`;
  }
  return user.username || user.first_name || `User ${senderId}`;
}

export function buildExportDashboard(payload: ExportPayload): ExportDashboardData {
  const chats = new Map(payload.chats.map((chat) => [chat.id, chat]));
  const entitiesByMessage = new Map<number, ExportPayload["entities"]>();
  const chatSummaries = new Map<number, ChatSummaryRow>();
  const categoryCounts = new Map<string, number>();

  for (const chat of payload.chats) {
    chatSummaries.set(chat.id, {
      chat_id: chat.id,
      title: chat.title || `Chat ${chat.id}`,
      chat_type: chat.chat_type || "unknown",
      messages: 0,
      entities: 0,
      narcotics: 0,
      human_trafficking: 0,
      firearms: 0,
    });
  }

  for (const entity of payload.entities) {
    const bucket = entitiesByMessage.get(entity.message_row_id) || [];
    bucket.push(entity);
    entitiesByMessage.set(entity.message_row_id, bucket);
    if (!CONTENT_ENTITY_TYPES.has(entity.entity_type)) {
      categoryCounts.set(
        entity.entity_type,
        (categoryCounts.get(entity.entity_type) || 0) + 1,
      );
    }
  }

  const messages: MessageDisplayRow[] = payload.messages.map((message) => {
    const chat = chats.get(message.chat_id);
    const summary = chatSummaries.get(message.chat_id) || {
      chat_id: message.chat_id,
      title: chat?.title || `Chat ${message.chat_id}`,
      chat_type: chat?.chat_type || "unknown",
      messages: 0,
      entities: 0,
      narcotics: 0,
      human_trafficking: 0,
      firearms: 0,
    };
    chatSummaries.set(message.chat_id, summary);
    summary.messages += 1;

    const messageEntities = entitiesByMessage.get(message.id) || [];
    summary.entities += messageEntities.length;

    const keywordEntities = messageEntities.filter(
      (entity) => !CONTENT_ENTITY_TYPES.has(entity.entity_type),
    );
    const categories = [
      ...new Set(keywordEntities.map((entity) => entity.entity_type)),
    ].sort();
    for (const entity of keywordEntities) {
      if (entity.entity_type === "narcotics") {
        summary.narcotics += 1;
      } else if (entity.entity_type === "human_trafficking") {
        summary.human_trafficking += 1;
      } else if (entity.entity_type === "firearms") {
        summary.firearms += 1;
      }
    }

    return {
      chat_id: message.chat_id,
      chat: chat?.title || `Chat ${message.chat_id}`,
      chat_type: chat?.chat_type || "unknown",
      message_id: message.message_id,
      timestamp: message.timestamp || "",
      sender: senderLabel(payload.users, message.sender_id),
      categories: categories.join(", "),
      keywords: keywordEntities.map((entity) => entity.entity_value).join(", "),
      entities: messageEntities.length,
      views: message.views ?? "",
      media_type: message.media_type || "",
      text: message.text || "",
    };
  });

  const entities: EntityDisplayRow[] = payload.entities.map((entity) => {
    const message = payload.messages.find((item) => item.id === entity.message_row_id);
    const chat = message ? chats.get(message.chat_id) : undefined;
    return {
      entity_type: entity.entity_type,
      entity_value: entity.entity_value,
      message_id: message?.message_id ?? "",
      chat_id: message?.chat_id ?? null,
      chat: chat?.title || "",
      chat_type: chat?.chat_type || "",
      timestamp: message?.timestamp || "",
    };
  });

  const summaries = [...chatSummaries.values()]
    .filter((summary) => summary.messages > 0)
    .sort((a, b) => b.messages - a.messages || a.title.localeCompare(b.title));

  const entityTypes = [...new Set(payload.entities.map((entity) => entity.entity_type))].sort();

  return {
    exportedAt: payload.exported_at,
    chatSummaries: summaries,
    messages: messages.sort((a, b) => b.timestamp.localeCompare(a.timestamp)),
    entities,
    categoryCounts: [...categoryCounts.entries()]
      .map(([category, count]) => ({ category, count }))
      .sort((a, b) => b.count - a.count || a.category.localeCompare(b.category)),
    entityTypes,
  };
}

function messageInDateRange(row: MessageDisplayRow, filters: DashboardFilters): boolean {
  if (!filters.useDateFilter) {
    return true;
  }
  const ts = row.timestamp.slice(0, 10);
  if (filters.dateFrom && ts < filters.dateFrom) {
    return false;
  }
  if (filters.dateTo && ts > filters.dateTo) {
    return false;
  }
  return true;
}

export function filterMessages(
  messages: MessageDisplayRow[],
  filters: DashboardFilters,
): MessageDisplayRow[] {
  return messages.filter((row) => {
    if (filters.chatIds.length && !filters.chatIds.includes(row.chat_id)) {
      return false;
    }
    if (!filters.includePrivate && row.chat_type === PRIVATE_CHAT_TYPE) {
      return false;
    }
    if (filters.chatType !== "All" && row.chat_type !== filters.chatType) {
      return false;
    }
    if (filters.categories.length) {
      const rowCategories = row.categories
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
      if (!rowCategories.some((category) => filters.categories.includes(category))) {
        return false;
      }
    }
    if (!messageInDateRange(row, filters)) {
      return false;
    }
    return true;
  });
}

export function filterChatSummaries(
  summaries: ChatSummaryRow[],
  messages: MessageDisplayRow[],
  filters: DashboardFilters,
): ChatSummaryRow[] {
  const counts = new Map<number, number>();
  for (const row of messages) {
    counts.set(row.chat_id, (counts.get(row.chat_id) || 0) + 1);
  }

  return summaries
    .map((summary) => {
      const filteredCount = counts.get(summary.chat_id) || 0;
      return { ...summary, messages: filteredCount };
    })
    .filter((summary) => {
      if (filters.chatIds.length && !filters.chatIds.includes(summary.chat_id)) {
        return false;
      }
      if (!filters.includePrivate && summary.chat_type === PRIVATE_CHAT_TYPE) {
        return false;
      }
      if (filters.chatType !== "All" && summary.chat_type !== filters.chatType) {
        return false;
      }
      if (summary.messages < filters.minMessages) {
        return false;
      }
      return summary.messages > 0;
    });
}

export function filterEntities(
  entities: EntityDisplayRow[],
  messages: MessageDisplayRow[],
  filters: DashboardFilters,
): EntityDisplayRow[] {
  const allowedMessageIds = new Set(messages.map((row) => row.message_id));
  return entities.filter((entity) => {
    if (typeof entity.message_id === "number" && !allowedMessageIds.has(entity.message_id)) {
      return false;
    }
    if (filters.categories.length && !filters.categories.includes(entity.entity_type)) {
      return false;
    }
    if (filters.chatIds.length && entity.chat_id && !filters.chatIds.includes(entity.chat_id)) {
      return false;
    }
    if (!filters.includePrivate && entity.chat_type === PRIVATE_CHAT_TYPE) {
      return false;
    }
    if (filters.chatType !== "All" && entity.chat_type !== filters.chatType) {
      return false;
    }
    return true;
  });
}

export function categoryCountsFromMessages(messages: MessageDisplayRow[]) {
  const counts = new Map<string, number>();
  for (const row of messages) {
    for (const category of row.categories.split(",").map((item) => item.trim()).filter(Boolean)) {
      counts.set(category, (counts.get(category) || 0) + 1);
    }
  }
  return [...counts.entries()]
    .map(([category, count]) => ({ category, count }))
    .sort((a, b) => b.count - a.count);
}

export function timelineFromMessages(messages: MessageDisplayRow[]) {
  const counts = new Map<string, number>();
  for (const row of messages) {
    const day = row.timestamp.slice(0, 10);
    if (!day) {
      continue;
    }
    counts.set(day, (counts.get(day) || 0) + 1);
  }
  return [...counts.entries()]
    .map(([date, count]) => ({ date, messages: count }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

export function messagesPerHour(messages: MessageDisplayRow[]) {
  const counts = new Map<string, number>();
  for (const row of messages) {
    if (!row.timestamp || row.timestamp.length < 13) {
      continue;
    }
    const hour = `${row.timestamp.slice(11, 13)}:00`;
    counts.set(hour, (counts.get(hour) || 0) + 1);
  }
  return [...counts.entries()]
    .map(([hour, count]) => ({ hour, messages: count }))
    .sort((a, b) => a.hour.localeCompare(b.hour));
}

export function topKeywordTerms(entities: EntityDisplayRow[], limit = 20) {
  const counts = new Map<string, { category: string; term: string; count: number }>();
  for (const entity of entities) {
    if (!KEYWORD_ENTITY_TYPES.has(entity.entity_type)) {
      continue;
    }
    const key = `${entity.entity_type}:${entity.entity_value}`;
    const current = counts.get(key) || {
      category: entity.entity_type,
      term: entity.entity_value,
      count: 0,
    };
    current.count += 1;
    counts.set(key, current);
  }
  return [...counts.values()]
    .sort((a, b) => b.count - a.count || a.term.localeCompare(b.term))
    .slice(0, limit);
}

export function chatTypeBreakdown(summaries: ChatSummaryRow[]) {
  const counts = new Map<string, number>();
  for (const summary of summaries) {
    counts.set(summary.chat_type, (counts.get(summary.chat_type) || 0) + summary.messages);
  }
  return [...counts.entries()]
    .map(([chat_type, messages]) => ({ chat_type, messages }))
    .sort((a, b) => b.messages - a.messages);
}

export function senderActivity(messages: MessageDisplayRow[], limit = 15) {
  const counts = new Map<string, number>();
  for (const row of messages) {
    const label = row.sender || "Unknown";
    counts.set(label, (counts.get(label) || 0) + 1);
  }
  return [...counts.entries()]
    .map(([sender, count]) => ({ sender, messages: count }))
    .sort((a, b) => b.messages - a.messages)
    .slice(0, limit);
}

export function mediaTypeBreakdown(messages: MessageDisplayRow[]) {
  const counts = new Map<string, number>();
  for (const row of messages) {
    const label = row.media_type || "text only";
    counts.set(label, (counts.get(label) || 0) + 1);
  }
  return [...counts.entries()]
    .map(([media_type, messages]) => ({ media_type, messages }))
    .sort((a, b) => b.messages - a.messages);
}

export function topEntitiesByType(entities: EntityDisplayRow[], entityType: string, limit = 10) {
  const counts = new Map<string, number>();
  for (const entity of entities) {
    if (entity.entity_type !== entityType) {
      continue;
    }
    counts.set(entity.entity_value, (counts.get(entity.entity_value) || 0) + 1);
  }
  return [...counts.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, limit);
}

export function wordFrequency(messages: MessageDisplayRow[], limit = 20) {
  const counts = new Map<string, number>();
  for (const row of messages) {
    const tokens = (row.text || "").toLowerCase().match(/[a-z0-9']+/g) || [];
    for (const token of tokens) {
      if (token.length < 3 || STOP_WORDS.has(token)) {
        continue;
      }
      counts.set(token, (counts.get(token) || 0) + 1);
    }
  }
  return [...counts.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, limit);
}

export function multiCategoryMessages(messages: MessageDisplayRow[], limit = 50) {
  return messages
    .filter((row) => {
      const categories = row.categories.split(",").map((item) => item.trim()).filter(Boolean);
      return new Set(categories).size > 1;
    })
    .slice(0, limit);
}

export function computeInsights(
  chatSummaries: ChatSummaryRow[],
  messages: MessageDisplayRow[],
  categoryCounts: Array<{ category: string; count: number }>,
  termRows: Array<{ term: string; count: number }>,
): DashboardInsights {
  const busiest = chatSummaries[0];
  const timestamps = messages.map((row) => row.timestamp).filter(Boolean).sort();
  const privateMessages = messages.filter((row) => row.chat_type === PRIVATE_CHAT_TYPE).length;
  const totalMessages = messages.length;

  return {
    busiestChat: busiest?.title ?? null,
    busiestChatMessages: busiest?.messages ?? 0,
    topKeyword: termRows[0]?.term ?? null,
    topKeywordCount: termRows[0]?.count ?? 0,
    topCategory: categoryCounts[0]?.category ?? null,
    topCategoryCount: categoryCounts[0]?.count ?? 0,
    multiFlagMessages: multiCategoryMessages(messages, 10000).length,
    earliestMessage: timestamps[0] ?? null,
    latestMessage: timestamps[timestamps.length - 1] ?? null,
    privateSharePct: totalMessages ? Math.round((privateMessages / totalMessages) * 1000) / 10 : 0,
  };
}

export function timestampBounds(messages: MessageDisplayRow[]) {
  const days = messages.map((row) => row.timestamp.slice(0, 10)).filter(Boolean).sort();
  return { min: days[0] || "", max: days[days.length - 1] || "" };
}
