export const KEYWORD_ENTITY_TYPES = new Set([
  "narcotics",
  "human_trafficking",
  "firearms",
]);

export const CONTENT_ENTITY_TYPES = new Set([
  "url",
  "domain",
  "email",
  "phone",
  "mention",
  "hashtag",
  "wallet",
  "address",
]);

export const ADDRESS_ENTITY_TYPES = new Set(["phone", "email", "wallet", "address"]);

export const LINK_ENTITY_TYPES = new Set([
  "url",
  "domain",
  "email",
  "phone",
  "wallet",
  "address",
]);

export const PRIVATE_CHAT_TYPE = "private chat";

export const PAGE_NAMES = [
  "Command",
  "Cases",
  "Intel",
  "Sources",
  "Analytics",
  "Ops",
  "ThreatIntelligence",
] as const;

export type PageName = (typeof PAGE_NAMES)[number];

export const NAV_GROUPS: Array<{ label: string; pages: PageName[] }> = [
  { label: "Monitor", pages: ["Command", "Intel", "Ops"] },
  { label: "Entities", pages: ["Sources", "Cases"] },
  { label: "Analyze", pages: ["Analytics", "ThreatIntelligence"] },
];

/** SOC display labels — internal PageName keys stay unchanged. */
export const PAGE_LABELS: Record<PageName, string> = {
  Command: "Dashboard",
  Intel: "Threat Monitoring",
  Ops: "Alerts",
  Sources: "Channels",
  Cases: "Users",
  Analytics: "Analytics",
  ThreatIntelligence: "Threat Intelligence",
};

export function pageLabel(name: PageName): string {
  return PAGE_LABELS[name] ?? name;
}

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

/** Human label for API provenance `source`. */
export function dataSourceLabel(source: string): string {
  switch (source) {
    case "mongodb":
      return "Live MongoDB";
    case "exports":
    case "local":
      return "Export file";
    case "remote":
      return "Remote export";
    case "demo":
    case "sample":
      return "Demo sample";
    case "simulation":
      return "Simulation mode";
    case "empty":
      return "Empty";
    default:
      return source || "Unknown";
  }
}
