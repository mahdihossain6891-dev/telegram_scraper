export const KEYWORD_ENTITY_TYPES = new Set([
  "narcotics",
  "human_trafficking",
  "firearms",
]);

export const LINK_ENTITY_TYPES = new Set(["url", "domain", "email", "phone"]);

export const PRIVATE_CHAT_TYPE = "private chat";

export const PAGE_NAMES = [
  "Overview",
  "Chats",
  "Messages",
  "Keywords",
  "Analytics",
  "Entities",
  "Search",
  "Export",
] as const;

export type PageName = (typeof PAGE_NAMES)[number];

export const STOP_WORDS = new Set([
  "the",
  "and",
  "for",
  "are",
  "but",
  "not",
  "you",
  "all",
  "can",
  "with",
  "this",
  "that",
  "from",
  "have",
  "was",
  "were",
  "will",
  "your",
  "about",
  "into",
  "https",
  "http",
]);
