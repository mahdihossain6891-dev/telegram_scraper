import {
  CONTENT_ENTITY_TYPES,
  type ChatRow,
  type EntityRow,
  type ExportPayload,
  type MessageRow,
} from "./types";

export type ChatSummary = {
  chatId: number;
  title: string;
  chatType: string;
  messageCount: number;
  narcotics: number;
  humanTrafficking: number;
  firearms: number;
};

export type DashboardStats = {
  exportedAt: string;
  totalMessages: number;
  totalChats: number;
  flaggedChats: number;
  keywordFlags: number;
  categoryCounts: Record<string, number>;
  chatSummaries: ChatSummary[];
  messages: Array<MessageRow & { chatTitle: string; keywords: string[] }>;
};

function chatTitle(chats: ChatRow[], chatId: number): string {
  const chat = chats.find((item) => item.id === chatId);
  return chat?.title || `Chat ${chatId}`;
}

export function buildDashboardStats(payload: ExportPayload): DashboardStats {
  const messagesById = new Map(payload.messages.map((message) => [message.id, message]));
  const entitiesByMessage = new Map<number, EntityRow[]>();

  for (const entity of payload.entities) {
    const bucket = entitiesByMessage.get(entity.message_row_id) || [];
    bucket.push(entity);
    entitiesByMessage.set(entity.message_row_id, bucket);
  }

  const chatStats = new Map<number, ChatSummary>();
  for (const chat of payload.chats) {
    chatStats.set(chat.id, {
      chatId: chat.id,
      title: chat.title || `Chat ${chat.id}`,
      chatType: chat.chat_type || "unknown",
      messageCount: 0,
      narcotics: 0,
      humanTrafficking: 0,
      firearms: 0,
    });
  }

  let keywordFlags = 0;
  const categoryCounts: Record<string, number> = {};

  for (const entity of payload.entities) {
    if (CONTENT_ENTITY_TYPES.has(entity.entity_type)) {
      continue;
    }
    keywordFlags += 1;
    categoryCounts[entity.entity_type] = (categoryCounts[entity.entity_type] || 0) + 1;

    const message = messagesById.get(entity.message_row_id);
    if (!message) {
      continue;
    }
    const summary = chatStats.get(message.chat_id);
    if (!summary) {
      continue;
    }
    if (entity.entity_type === "narcotics") {
      summary.narcotics += 1;
    } else if (entity.entity_type === "human_trafficking") {
      summary.humanTrafficking += 1;
    } else if (entity.entity_type === "firearms") {
      summary.firearms += 1;
    }
  }

  for (const message of payload.messages) {
    const summary = chatStats.get(message.chat_id);
    if (summary) {
      summary.messageCount += 1;
    }
  }

  const chatSummaries = [...chatStats.values()]
    .filter((item) => item.messageCount > 0)
    .sort((a, b) => b.messageCount - a.messageCount);

  const messages = payload.messages
    .map((message) => {
      const keywords = (entitiesByMessage.get(message.id) || [])
        .filter((entity) => !CONTENT_ENTITY_TYPES.has(entity.entity_type))
        .map((entity) => entity.entity_value);
      return {
        ...message,
        chatTitle: chatTitle(payload.chats, message.chat_id),
        keywords,
      };
    })
    .sort((a, b) => (b.timestamp || "").localeCompare(a.timestamp || ""));

  return {
    exportedAt: payload.exported_at,
    totalMessages: payload.messages.length,
    totalChats: payload.chats.length,
    flaggedChats: chatSummaries.length,
    keywordFlags,
    categoryCounts,
    chatSummaries,
    messages,
  };
}
