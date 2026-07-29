export type ExportPayload = {
  exported_at: string;
  counts: {
    chats: number;
    users: number;
    messages: number;
    entities: number;
    personnel?: number;
  };
  chats: ChatRow[];
  users: UserRow[];
  messages: MessageRow[];
  entities: EntityRow[];
  personnel?: PersonnelRow[];
};

export type ChatRow = {
  id: number;
  title: string | null;
  username: string | null;
  chat_type: string | null;
  risk_score?: number;
  risk_level?: string;
  risk_factors?: string[];
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
  reply_to_message_id?: number | null;
  forward_from_chat_id?: number | null;
  forward_from_message_id?: number | null;
  views?: number | null;
  risk_score?: number;
  risk_level?: string;
  risk_factors?: string[];
};

export type EntityRow = {
  id: number;
  message_row_id: number;
  entity_type: string;
  entity_value: string;
};

export type PersonnelRow = {
  user_id: number;
  display_name: string;
  username: string | null;
  first_name?: string | null;
  last_name?: string | null;
  group_name: string;
  chat_ids: number[];
  message_count: number;
  suspicious_count: number;
  keywords: Record<string, number>;
  keyword_list: string[];
  keyword_total: number;
  categories?: Record<string, number>;
  first_seen: string | null;
  last_seen: string | null;
  risk_score?: number;
  risk_level?: string;
  risk_factors?: string[];
};

export type PersonnelGroupStat = {
  chat_id: number;
  group_name: string;
  message_count: number;
  suspicious_count: number;
  keywords: Record<string, number>;
  first_seen: string | null;
  last_seen: string | null;
};

export type PersonnelMessage = {
  id: number;
  message_id: number;
  chat_id: number;
  group_name: string;
  timestamp: string | null;
  text: string | null;
  media_type?: string | null;
  views?: number | null;
  categories: string[];
  keywords: string[];
  suspicious: boolean;
};

export type PersonnelDetail = {
  user: {
    user_id: number;
    display_name: string;
    username: string | null;
    first_name: string | null;
    last_name: string | null;
  };
  summary: PersonnelRow;
  groups: PersonnelGroupStat[];
  keyword_frequency: Record<string, number>;
  category_frequency: Record<string, number>;
  messages: PersonnelMessage[];
};

export type PersonnelSort =
  | "suspicious_count"
  | "message_count"
  | "last_seen"
  | "keyword_total"
  | "display_name";

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
  reply_to_message_id?: number | null;
  forward_from_chat_id?: number | null;
  forward_from_message_id?: number | null;
  text: string;
  risk_score: number;
  risk_level: string;
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
  risk_score: number;
  risk_level: string;
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
