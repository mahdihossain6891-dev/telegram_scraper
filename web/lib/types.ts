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
