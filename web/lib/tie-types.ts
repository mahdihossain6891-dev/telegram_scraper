export type TieComponentStatus = {
  status: string;
  raw?: string;
  backend?: string;
  mode?: string;
  provider?: string;
};

export type TieHealth = {
  service: string;
  status: string;
  status_display: string;
  version: string;
  server_time?: string;
  components: {
    database: TieComponentStatus;
    redis: TieComponentStatus;
    workers: TieComponentStatus;
    llm_provider: TieComponentStatus;
    threat_console_sync: TieComponentStatus;
  };
};

export type TieStatus = {
  service: string;
  status: string;
  status_display: string;
  version: string;
  uptime_seconds: number;
  uptime_days: number;
  server_time?: string;
  connection: string;
  ai: {
    provider: string;
    provider_raw?: string;
    model: string;
    requests_today: number;
    average_latency_ms: number;
    successful_requests: number;
    failed_requests: number;
    token_usage: number | null;
  };
  sync: { status: string; healthy: boolean };
  system_health: TieHealth["components"];
};

export type TieMetrics = {
  messages_processed: number;
  messages_today: number;
  intelligence_reports_generated: number;
  threats_detected: number;
  active_campaigns: number;
  entities_extracted: number;
  average_processing_time_sec: number;
};

export type TiePipelineStage = {
  id: string;
  name: string;
  status: string;
  last_processed_at: string | null;
  current_workload: string;
};

export type TiePipeline = {
  stages: TiePipelineStage[];
  updated_at?: string;
};

export type TieWorkers = {
  workers: { running: number; total: number; mode?: string };
  active_batches?: number;
  status: string;
};

export type TieQueue = {
  pending_jobs: number;
  processing_jobs: number;
  failed_jobs: number;
  retry_queue: number;
  dead_letter_queue: number;
};

export type TieRecentItem = {
  id: string;
  title: string;
  category: string;
  risk: string;
  confidence: number;
  generated_at: string | null;
};

export type TieCampaignStatus = {
  active_campaigns: number;
  new_campaigns_today: number;
  updated_campaigns: number;
  highest_risk_campaign: {
    campaign_id: string;
    category: string;
    risk_score: number;
    title?: string;
  } | null;
};

export type TieAiModelOption = {
  id: string;
  label: string;
};

export type TieAiConfig = {
  provider: string;
  model: string;
  detection_enabled: boolean;
  api_base_url?: string;
  has_api_key?: boolean;
  providers: Array<{ id: string; label: string }>;
  models: TieAiModelOption[];
  writable?: boolean;
};

export type TieSnapshot = {
  health: TieHealth | null;
  status: TieStatus | null;
  metrics: TieMetrics | null;
  pipeline: TiePipeline | null;
  workers: TieWorkers | null;
  queue: TieQueue | null;
  recent: TieRecentItem[];
  campaigns: TieCampaignStatus | null;
  offline: boolean;
  lastSuccessAt: string | null;
  errors: string[];
};
