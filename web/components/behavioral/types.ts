export type BehaviorStatus = "Normal" | "Unusual" | "Suspicious" | "High Risk";

export type BehaviorBrief = {
  user_id: number;
  display_name?: string | null;
  username?: string | null;
  behavior_score?: number;
  behavior_status?: BehaviorStatus | string;
  behavior_trend?: string;
  forward_ratio?: number;
  non_text_percentage?: number;
  average_messages_per_day?: number;
  last_seen?: string | null;
};

export type BehavioralOverview = {
  total_users: number;
  distribution: Record<string, number>;
  avg_messages_per_day: number;
  avg_active_hour: number | null;
  top_outliers: BehaviorBrief[];
  recent_behavior_changes: BehaviorBrief[];
  highest_forwarding: BehaviorBrief[];
  highest_media: BehaviorBrief[];
  activity_spikes: BehaviorBrief[];
};

export type BehaviorAlert = {
  time?: string | null;
  reason: string;
  impact: number;
  severity: string;
};

export type BehaviorHistoryItem = {
  time?: string | null;
  title: string;
  detail?: string;
};

export type ProfileListRow = {
  user_id: number;
  username?: string | null;
  display_name?: string | null;
  behavior_score?: number;
  behavior_status?: string;
  behavior_trend?: string;
  risk_score?: number;
  first_seen?: string | null;
  last_seen?: string | null;
  groups_joined?: number;
  channels_joined?: number;
  private_chats?: number;
  languages_used?: string[];
  average_messages_per_day?: number;
  most_active_hour?: number | null;
  night_activity_percentage?: number;
  non_text_percentage?: number;
  forward_ratio?: number;
  alert_count?: number;
};

export type BehavioralProfile = ProfileListRow & {
  phone_number?: string | null;
  messages_per_hour_avg?: number;
  messages_per_week_avg?: number;
  peak_daily_messages?: number;
  most_active_weekday?: string | null;
  first_message_hour?: number | null;
  last_message_hour?: number | null;
  active_duration_hours_est?: number | null;
  media_usage?: Record<string, number>;
  forwarding_rate?: {
    forwarded?: number;
    original?: number;
    forward_ratio?: number;
    forward_sources?: Array<{ chat_id: number; count: number }>;
  };
  deletion_rate?: {
    available?: boolean;
    deleted_messages?: number;
    deletion_percentage?: number;
    avg_deletion_delay_seconds?: number | null;
    note?: string;
  };
  language_distribution?: Record<string, number>;
  profile_changes?: Array<{
    time?: string | null;
    field: string;
    from?: string | null;
    to?: string | null;
  }>;
  account_age?: {
    first_monitored?: string | null;
    days_active?: number;
    groups_over_time?: number;
    channels_over_time?: number;
  };
  group_join_pattern?: {
    distinct_sources?: number;
    joins_per_day_est?: number;
    chat_ids?: number[];
  };
  posting_frequency?: {
    total_messages?: number;
    avg_daily?: number;
    peak_daily?: number;
    per_hour_avg?: number;
    per_week_avg?: number;
    daily_series?: Array<{ date: string; messages: number }>;
  };
  online_hours?: {
    first_hour?: number | null;
    last_hour?: number | null;
    most_active_hour?: number | null;
    most_active_weekday?: string | null;
    night_activity_percentage?: number;
    hourly_series?: Array<{ hour: number; messages: number }>;
    weekday_series?: Array<{ weekday: string; messages: number }>;
    heatmap?: Array<{ weekday: string; hour: number; messages: number }>;
  };
  behavior_history?: BehaviorHistoryItem[];
  alerts?: BehaviorAlert[];
  last_updated?: string | null;
  content_risk_level?: string | null;
};
