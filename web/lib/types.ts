export type ExportPayload = {
  exported_at: string;
  counts: {
    chats: number;
    users: number;
    messages: number;
    entities: number;
  };
  chats: ChatRow[];
  users: UserRow[];
  messages: MessageRow[];
  entities: EntityRow[];
};

export type ChatRow = {
  id: number;
  title: string | null;
  username: string | null;
  chat_type: string | null;
};

export type UserRow = {
  id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
};

export type MessageRow = {
  id: number;
  message_id: number;
  chat_id: number;
  sender_id: number | null;
  timestamp: string | null;
  text: string | null;
  media_type?: string | null;
  views?: number | null;
};

export type EntityRow = {
  id: number;
  message_row_id: number;
  entity_type: string;
  entity_value: string;
};

export const CONTENT_ENTITY_TYPES = new Set([
  "url",
  "domain",
  "email",
  "phone",
  "mention",
  "hashtag",
]);

export type DashboardFilters = {
  chatIds: number[];
  categories: string[];
  includePrivate: boolean;
  chatType: string;
  minMessages: number;
  dateFrom: string;
  dateTo: string;
  useDateFilter: boolean;
};

export type ChatSummaryRow = {
  chat_id: number;
  title: string;
  chat_type: string;
  messages: number;
  entities: number;
  narcotics: number;
  human_trafficking: number;
  firearms: number;
};

export type MessageDisplayRow = {
  chat_id: number;
  chat: string;
  chat_type: string;
  message_id: number;
  timestamp: string;
  sender: string;
  categories: string;
  keywords: string;
  entities: number;
  views: string | number;
  media_type: string;
  text: string;
};

export type EntityDisplayRow = {
  entity_type: string;
  entity_value: string;
  message_id: number | string;
  chat_id: number | null;
  chat: string;
  chat_type: string;
  timestamp: string;
};

export type DashboardInsights = {
  busiestChat: string | null;
  busiestChatMessages: number;
  topKeyword: string | null;
  topKeywordCount: number;
  topCategory: string | null;
  topCategoryCount: number;
  multiFlagMessages: number;
  earliestMessage: string | null;
  latestMessage: string | null;
  privateSharePct: number;
};

export type ExportDashboardData = {
  exportedAt: string;
  chatSummaries: ChatSummaryRow[];
  messages: MessageDisplayRow[];
  entities: EntityDisplayRow[];
  categoryCounts: Array<{ category: string; count: number }>;
  entityTypes: string[];
};
