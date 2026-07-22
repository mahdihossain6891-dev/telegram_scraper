/** Client types for the isolated Sébastien investigation UI. */

export type AiMode = "chat" | "investigate" | "search" | "report";

export type ShellView = "investigation" | "cases" | "settings";

export type EntityKind =
  | "username"
  | "group"
  | "channel"
  | "wallet"
  | "phone"
  | "keyword";

export type Confidence = "high" | "medium" | "low" | string;

export type RiskLevel = "high" | "medium" | "low" | "unknown";

/** Soft lifecycle for investigation sessions (never hard-deleted). */
export type CaseStatus = "active" | "dismissed";

export type AiCitation = {
  source_type: string;
  source_id: string;
  label: string;
  snippet: string;
};

export type AiRetrieved = {
  chunk_id: string;
  score: number;
  text: string;
  metadata?: Record<string, unknown>;
};

export type AiHealth = {
  status: string;
  enabled: boolean;
  chat_configured: boolean;
  embeddings_configured: boolean;
  chat_provider?: string;
  embedding_provider?: string;
  vector_backend?: string;
  report_collection?: string;
  session_collection?: string;
};

export type ModelCapabilities = {
  supports_streaming?: boolean;
  supports_json_output?: boolean;
  supports_vision?: boolean;
  supports_reasoning?: boolean;
  supports_tool_calling?: boolean;
};

export type DiscoveredModel = {
  model_id: string;
  display_name: string;
  provider: string;
  context_window?: number | null;
  max_tokens?: number | null;
  status?: string;
  capabilities?: ModelCapabilities;
  family?: string | null;
  size_bytes?: number | null;
  quantization?: string | null;
  modified_at?: string | null;
  pricing?: Record<string, number | null> | null;
  estimated_speed?: string | null;
  raw?: Record<string, unknown>;
};

export type ProviderHealthSnapshot = {
  ok?: boolean;
  status?: string;
  latency_ms?: number | null;
  models_available?: number | null;
  detail?: string | null;
  last_success_at?: number | null;
  last_failure_at?: number | null;
  cached?: boolean;
};

export type ProviderCatalogEntry = {
  id: string;
  label: string;
  kind: string;
  requires_api_key?: boolean;
  default_base_url?: string;
  description?: string;
  configured?: boolean;
  selected?: boolean;
  health?: ProviderHealthSnapshot;
};

export type ProvidersResponse = {
  providers: ProviderCatalogEntry[];
  selected_provider?: string;
  cache?: Record<string, unknown>;
};

export type ModelsResponse = {
  provider: string;
  models: DiscoveredModel[];
  cached?: boolean;
  error?: string | null;
  count?: number;
  latency_ms?: number;
  last_refresh_at?: number | null;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations?: AiCitation[];
  retrieved?: AiRetrieved[];
  confidence?: Confidence;
  intent?: string;
  refused?: boolean;
  model?: string;
  kind?: string;
  createdAt: string;
  /** Entity resolution gate metadata from the investigation assistant. */
  entityResolution?: {
    status?: string;
    message?: string;
    suggestions?: string[];
    reason?: string;
    unmatched_query?: string;
    candidates?: EntityCandidate[];
  };
  /** Phase 5 investigation workflow trace (planner → tools → evidence → LLM). */
  workflow?: Record<string, unknown>;
  observability?: Record<string, unknown>;
  threatReport?: import("@/components/ai/threat-report").ThreatReport;
};

export type EntityCandidate = {
  label?: string;
  display_name?: string;
  username?: string;
  entity_id?: string | number;
  entity_type?: string;
  first_name?: string;
  last_name?: string;
  risk_score?: number | null;
  risk_level?: string | null;
  behavior_score?: number | null;
  last_seen?: string | null;
  chat_type?: string | null;
  match_reason?: string;
  score?: number;
};

export type ConversationSession = {
  id: string;
  title: string;
  mode: AiMode;
  serverSessionId: string | null;
  messages: ChatMessage[];
  updatedAt: string;
  description?: string;
  risk?: RiskLevel;
  /** Soft status — dismissed cases stay stored for future Archived Cases. */
  status?: CaseStatus;
  dismissedAt?: string | null;
};

export type ReportSection = {
  section_id: string;
  title: string;
  body: string;
  citation_labels: string[];
};

export type AiReport = {
  report_id: string;
  report_type: string;
  title: string;
  subject_type: string;
  subject_id: string;
  sections: ReportSection[];
  citations: AiCitation[];
  confidence: Confidence;
  model: string;
  body_markdown: string;
  refused: boolean;
  created_at?: string | null;
  metadata?: Record<string, unknown>;
};

export type InvestigationSectionId =
  | "executive_summary"
  | "subject_information"
  | "risk_assessment"
  | "evidence_analysis"
  | "behavior_analysis"
  | "network_analysis"
  | "false_positive_assessment"
  | "threat_classification"
  | "analyst_recommendation"
  | "confidence_level"
  | "key_findings"
  | "supporting_evidence"
  | "recommended_actions";

export type InvestigationSection = {
  id: InvestigationSectionId;
  title: string;
  body: string;
};

export const REPORT_TYPES = [
  { value: "user_intelligence", label: "User Intelligence" },
  { value: "investigation", label: "Investigation" },
  { value: "case_summary", label: "Case Summary" },
  { value: "behavioral_analysis", label: "Behavioral Analysis" },
] as const;

export const ENTITY_OPTIONS: { value: EntityKind; label: string }[] = [
  { value: "username", label: "Username" },
  { value: "group", label: "Group" },
  { value: "channel", label: "Channel" },
  { value: "wallet", label: "Wallet" },
  { value: "phone", label: "Phone" },
  { value: "keyword", label: "Keyword" },
];

export const SHELL_NAV: { id: ShellView; label: string }[] = [
  { id: "investigation", label: "Investigation" },
  { id: "cases", label: "Saved Cases" },
  { id: "settings", label: "Settings" },
];

export const QUICK_ACTIONS: {
  id: string;
  label: string;
  placeholder: string;
  /** Template used only after a target is entered. `{target}` is replaced. */
  queryTemplate: string;
}[] = [
  {
    id: "investigate_user",
    label: "Investigate User",
    placeholder: "Enter a username, display name, or Telegram ID...",
    queryTemplate:
      "Investigate {target} and summarize risk, activity patterns, and notable evidence.",
  },
  {
    id: "analyze_behavior",
    label: "Analyze Behavior",
    placeholder: "Select a user to analyze behavioral activity...",
    queryTemplate:
      "Analyze behavioral anomalies and unusual activity patterns for {target}.",
  },
  {
    id: "explain_alert",
    label: "Explain Alert",
    placeholder: "Search for an alert ID or user...",
    queryTemplate:
      "Explain this alert for {target}: what triggered it, supporting evidence, and severity.",
  },
  {
    id: "related_users",
    label: "Find Related Users",
    placeholder: "Enter a username, display name, or Telegram ID...",
    queryTemplate:
      "Find related users connected to {target} through shared groups, wallets, or similar activity.",
  },
  {
    id: "generate_report",
    label: "Generate Report",
    placeholder: "Select a completed investigation...",
    queryTemplate: "Generate a concise investigation summary for {target}.",
  },
];

export const DEFAULT_SEARCH_PLACEHOLDER =
  "Investigate a user, group, message, wallet, phone number, or suspicious activity...";

export const SUGGESTED_PROMPTS: {
  id: string;
  label: string;
  actionId: string;
}[] = [
  { id: "s1", label: "Why is this user high risk?", actionId: "investigate_user" },
  { id: "s2", label: "Explain this alert", actionId: "explain_alert" },
  { id: "s3", label: "Show behavioral anomalies", actionId: "analyze_behavior" },
  { id: "s4", label: "Generate investigation summary", actionId: "generate_report" },
  { id: "s5", label: "Find related users", actionId: "related_users" },
];

export const SUGGESTED_NEXT_STEPS: { id: string; label: string; prompt: string }[] = [
  {
    id: "connected",
    label: "Investigate connected users",
    prompt: "Investigate connected users linked to this subject from the evidence.",
  },
  {
    id: "anomalies",
    label: "Analyze behavioral anomalies",
    prompt: "Deep-dive into behavioral anomalies and timing patterns.",
  },
  {
    id: "intel_report",
    label: "Generate intelligence report",
    prompt: "Produce a structured intelligence report with executive summary and citations.",
  },
  {
    id: "graph",
    label: "View relationship graph",
    prompt: "Describe relationship connections between this subject and related entities.",
  },
  {
    id: "similar",
    label: "Search similar activity",
    prompt: "Search for similar activity or messages across indexed evidence.",
  },
];

export const SECTION_META: {
  id: InvestigationSectionId;
  title: string;
  patterns: RegExp[];
}[] = [
  {
    id: "executive_summary",
    title: "Executive Summary",
    patterns: [/executive\s*summary/i, /^summary$/i, /overview/i],
  },
  {
    id: "subject_information",
    title: "Subject Information",
    patterns: [/subject\s*information/i, /^subject$/i, /identity\s*profile/i],
  },
  {
    id: "risk_assessment",
    title: "Risk Assessment",
    patterns: [/risk\s*assessment/i, /^risk$/i, /threat\s*level/i],
  },
  {
    id: "evidence_analysis",
    title: "Evidence Analysis",
    patterns: [/evidence\s*analysis/i, /message[\s-]*by[\s-]*message/i],
  },
  {
    id: "behavior_analysis",
    title: "Behavioral Analysis",
    patterns: [/behaviou?r(al)?\s*analysis/i, /activity\s*pattern/i],
  },
  {
    id: "network_analysis",
    title: "Network Analysis",
    patterns: [/network\s*analysis/i, /relationship\s*intelligence/i],
  },
  {
    id: "false_positive_assessment",
    title: "False Positive Assessment",
    patterns: [/false\s*positive/i, /fp\s*assessment/i],
  },
  {
    id: "threat_classification",
    title: "Threat Classification",
    patterns: [/threat\s*classif/i, /category\s*breakdown/i],
  },
  {
    id: "analyst_recommendation",
    title: "Analyst Recommendation",
    patterns: [/analyst\s*recommendation/i, /recommended\s*action/i],
  },
  {
    id: "confidence_level",
    title: "Confidence Level",
    patterns: [/confidence\s*level/i, /^confidence$/i],
  },
  {
    id: "key_findings",
    title: "Key Findings",
    patterns: [/key\s*findings?/i, /^findings?$/i],
  },
  {
    id: "supporting_evidence",
    title: "Evidence",
    patterns: [/supporting\s*evidence/i, /^evidence$/i],
  },
  {
    id: "recommended_actions",
    title: "Recommendations",
    patterns: [
      /recommended\s*(next\s*)?actions?/i,
      /next\s*steps?/i,
      /recommendations?/i,
    ],
  },
];

export const MODE_META: Record<
  AiMode,
  { label: string; hint: string; endpoint: string }
> = {
  chat: {
    label: "Chat",
    hint: "Multi-turn investigation chat with session memory",
    endpoint: "chat",
  },
  investigate: {
    label: "Investigate",
    hint: "Ask why a subject is high risk, anomalies, timelines…",
    endpoint: "investigate",
  },
  search: {
    label: "Semantic search",
    hint: "RAG query over indexed flagged messages",
    endpoint: "query",
  },
  report: {
    label: "Reports",
    hint: "Generate structured, citation-backed reports",
    endpoint: "report",
  },
};
