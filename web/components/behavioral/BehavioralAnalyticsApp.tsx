"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { EChart } from "@/components/EChart";
import { ConsoleJumpNav } from "@/components/layout/ConsoleJumpNav";
import {
  distributionBarOption,
  heatmapOption,
  hourlyBarOption,
  languageBarOption,
  mediaPieOption,
  postingLineOption,
  scoreTrendOption,
  statusClass,
} from "@/components/behavioral/charts";
import type {
  BehavioralOverview,
  BehavioralProfile,
  ProfileListRow,
} from "@/components/behavioral/types";

const BEHAVIOR_TYPES = [
  "",
  "Activity spike",
  "night activity",
  "Forward",
  "Media",
  "Language",
  "group",
  "Username",
  "Deletion",
];

const RISK_LEVELS = ["", "Normal", "Unusual", "Suspicious", "High Risk"];

function fmtHour(h: number | null | undefined): string {
  if (h === null || h === undefined) return "—";
  return `${String(h).padStart(2, "0")}:00`;
}

function fmtPct(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return `${n}%`;
}

function fmtDate(s: string | null | undefined): string {
  if (!s) return "—";
  try {
    return new Date(s).toLocaleString();
  } catch {
    return s;
  }
}

function BriefTable({
  title,
  rows,
  onSelect,
}: {
  title: string;
  rows: Array<{
    user_id: number;
    display_name?: string | null;
    username?: string | null;
    behavior_score?: number;
    behavior_status?: string;
  }>;
  onSelect: (id: number) => void;
}) {
  return (
    <section className="panel ba-panel">
      <div className="panel-head">
        <h3>{title}</h3>
      </div>
      {rows.length === 0 ? (
        <p className="caption ba-empty">No matching profiles yet.</p>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Score</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.user_id} className="ba-row-click" onClick={() => onSelect(r.user_id)}>
                  <td>
                    <strong>{r.display_name || `User ${r.user_id}`}</strong>
                    <div className="caption">{r.username ? `@${r.username}` : r.user_id}</div>
                  </td>
                  <td>{r.behavior_score ?? 0}</td>
                  <td>
                    <span className={statusClass(r.behavior_status)}>{r.behavior_status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function BehavioralAnalyticsApp() {
  const [overview, setOverview] = useState<BehavioralOverview | null>(null);
  const [profiles, setProfiles] = useState<ProfileListRow[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [profile, setProfile] = useState<BehavioralProfile | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);

  const [q, setQ] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [maxScore, setMaxScore] = useState(100);
  const [status, setStatus] = useState("");
  const [language, setLanguage] = useState("");
  const [behaviorType, setBehaviorType] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const loadOverview = useCallback(async () => {
    const res = await fetch("/api/behavioral/overview", { cache: "no-store" });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error || body.detail || "Overview failed");
    setOverview(body.overview as BehavioralOverview);
  }, []);

  const loadProfiles = useCallback(async () => {
    const params = new URLSearchParams();
    if (q.trim()) params.set("q", q.trim());
    params.set("min_score", String(minScore));
    params.set("max_score", String(maxScore));
    if (status) params.set("status", status);
    if (language.trim()) params.set("language", language.trim());
    if (behaviorType) params.set("behavior_type", behaviorType);
    params.set("limit", "300");
    const res = await fetch(`/api/behavioral/profiles?${params}`, { cache: "no-store" });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error || body.detail || "Profiles failed");
    let rows = (body.profiles || []) as ProfileListRow[];
    if (dateFrom || dateTo) {
      rows = rows.filter((r) => {
        const seen = r.last_seen ? new Date(r.last_seen).getTime() : 0;
        if (dateFrom && seen < new Date(dateFrom).getTime()) return false;
        if (dateTo && seen > new Date(dateTo).getTime() + 86400000) return false;
        return true;
      });
    }
    setProfiles(rows);
  }, [q, minScore, maxScore, status, language, behaviorType, dateFrom, dateTo]);

  const loadProfile = useCallback(async (userId: number) => {
    const res = await fetch(`/api/behavioral/profiles/${userId}`, { cache: "no-store" });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error || body.detail || "Profile failed");
    setProfile(body.profile as BehavioralProfile);
    setSelectedId(userId);
  }, []);

  const refreshAll = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      await Promise.all([loadOverview(), loadProfiles()]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load behavioral data");
    } finally {
      setBusy(false);
    }
  }, [loadOverview, loadProfiles]);

  useEffect(() => {
    void refreshAll();
  }, [refreshAll]);

  const onRebuild = async () => {
    setRebuilding(true);
    setError("");
    try {
      const res = await fetch("/api/behavioral/rebuild", { method: "POST" });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || body.detail || "Rebuild failed");
      await refreshAll();
      if (selectedId) await loadProfile(selectedId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Rebuild failed");
    } finally {
      setRebuilding(false);
    }
  };

  const languages = useMemo(() => {
    const set = new Set<string>();
    for (const p of profiles) {
      for (const lang of p.languages_used || []) set.add(lang);
    }
    return Array.from(set).sort();
  }, [profiles]);

  const distOption = useMemo(
    () => distributionBarOption(overview?.distribution || {}),
    [overview],
  );

  return (
    <div className="ba-shell">
      <ConsoleJumpNav active="behavioral" className="ba-sidebar" />

      <main className="ba-main">
        <header className="ba-header">
          <div>
            <h1>{selectedId ? "User Behavior Profile" : "Behavioral Analytics"}</h1>
            <p>
              How users behave over time — frequency, hours, forwards, media, language, and
              expansion patterns. Not keyword content analysis.
            </p>
            {selectedId ? (
              <button
                type="button"
                className="btn ghost ba-back-overview"
                onClick={() => {
                  setSelectedId(null);
                  setProfile(null);
                }}
              >
                ← Back to overview
              </button>
            ) : null}
          </div>
          <div className="ba-header-actions">
            <button
              type="button"
              className="btn primary"
              onClick={() => void onRebuild()}
              disabled={rebuilding}
            >
              {rebuilding ? "Rebuilding…" : "Rebuild profiles"}
            </button>
            <button type="button" className="btn" onClick={() => void refreshAll()} disabled={busy}>
              {busy ? "Refreshing…" : "Refresh"}
            </button>
          </div>
        </header>

        {error ? <div className="error">{error}</div> : null}

        {!selectedId ? (
          <>
            <section className="metric-grid ba-metrics">
              <div className="metric-card">
                <div className="metric-label">Total Monitored Users</div>
                <div className="metric-value">{overview?.total_users ?? "—"}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">Avg Messages / Day</div>
                <div className="metric-value">{overview?.avg_messages_per_day ?? "—"}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">Avg Active Hour</div>
                <div className="metric-value">{fmtHour(overview?.avg_active_hour ?? null)}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">High Risk</div>
                <div className="metric-value">{overview?.distribution?.["High Risk"] ?? 0}</div>
              </div>
            </section>

            <section className="panel ba-panel">
              <div className="panel-head">
                <h3>Behavioral Risk Distribution</h3>
              </div>
              <EChart option={distOption} height={240} ariaLabel="Risk distribution" />
            </section>

            <div className="ba-grid-2">
              <BriefTable
                title="Top Behavioral Outliers"
                rows={overview?.top_outliers || []}
                onSelect={(id) => void loadProfile(id)}
              />
              <BriefTable
                title="Recently Changed Behaviors"
                rows={overview?.recent_behavior_changes || []}
                onSelect={(id) => void loadProfile(id)}
              />
              <BriefTable
                title="Highest Forwarding Rate"
                rows={overview?.highest_forwarding || []}
                onSelect={(id) => void loadProfile(id)}
              />
              <BriefTable
                title="Highest Media Usage"
                rows={overview?.highest_media || []}
                onSelect={(id) => void loadProfile(id)}
              />
              <BriefTable
                title="Sudden Activity Spike"
                rows={overview?.activity_spikes || []}
                onSelect={(id) => void loadProfile(id)}
              />
            </div>

            <section className="panel ba-panel">
              <div className="panel-head">
                <h3>Search &amp; Filters</h3>
              </div>
              <div className="ba-filters">
                <label>
                  Search
                  <input
                    value={q}
                    onChange={(e) => setQ(e.target.value)}
                    placeholder="Username, user ID, display name, phone"
                  />
                </label>
                <label>
                  Min score
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={minScore}
                    onChange={(e) => setMinScore(Number(e.target.value) || 0)}
                  />
                </label>
                <label>
                  Max score
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={maxScore}
                    onChange={(e) => setMaxScore(Number(e.target.value) || 100)}
                  />
                </label>
                <label>
                  Risk level
                  <select value={status} onChange={(e) => setStatus(e.target.value)}>
                    {RISK_LEVELS.map((s) => (
                      <option key={s || "all"} value={s}>
                        {s || "All"}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Language
                  <select value={language} onChange={(e) => setLanguage(e.target.value)}>
                    <option value="">All</option>
                    {languages.map((l) => (
                      <option key={l} value={l}>
                        {l}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Behavior type
                  <select value={behaviorType} onChange={(e) => setBehaviorType(e.target.value)}>
                    {BEHAVIOR_TYPES.map((t) => (
                      <option key={t || "all"} value={t}>
                        {t || "All"}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Last seen from
                  <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
                </label>
                <label>
                  Last seen to
                  <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
                </label>
              </div>
              <p className="caption">Country filter reserved — not present in current Telegram snapshots.</p>
            </section>

            <section className="panel ba-panel">
              <div className="panel-head">
                <h3>Monitored Users ({profiles.length})</h3>
              </div>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>User</th>
                      <th>Score</th>
                      <th>Status</th>
                      <th>Trend</th>
                      <th>Msgs/day</th>
                      <th>Forward %</th>
                      <th>Media %</th>
                      <th>Night %</th>
                      <th>Alerts</th>
                      <th>Last seen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {profiles.map((r) => (
                      <tr
                        key={r.user_id}
                        className="ba-row-click"
                        onClick={() => void loadProfile(r.user_id)}
                      >
                        <td>
                          <strong>{r.display_name || `User ${r.user_id}`}</strong>
                          <div className="caption">
                            {r.username ? `@${r.username}` : ""} · {r.user_id}
                          </div>
                        </td>
                        <td>{r.behavior_score ?? 0}</td>
                        <td>
                          <span className={statusClass(r.behavior_status)}>{r.behavior_status}</span>
                        </td>
                        <td>{r.behavior_trend || "—"}</td>
                        <td>{r.average_messages_per_day ?? "—"}</td>
                        <td>
                          {r.forward_ratio != null
                            ? `${Math.round(r.forward_ratio * 100)}%`
                            : "—"}
                        </td>
                        <td>{fmtPct(r.non_text_percentage)}</td>
                        <td>{fmtPct(r.night_activity_percentage)}</td>
                        <td>{r.alert_count ?? 0}</td>
                        <td>{fmtDate(r.last_seen)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {profiles.length === 0 ? (
                <p className="caption ba-empty">
                  No profiles yet. Click <strong>Rebuild profiles</strong> to compute from stored
                  messages.
                </p>
              ) : null}
            </section>
          </>
        ) : profile ? (
          <ProfileDetail
            profile={profile}
            onBack={() => {
              setSelectedId(null);
              setProfile(null);
            }}
          />
        ) : (
          <p className="caption">Loading profile…</p>
        )}
      </main>
    </div>
  );
}

function ProfileDetail({
  profile,
  onBack,
}: {
  profile: BehavioralProfile;
  onBack: () => void;
}) {
  const daily = profile.posting_frequency?.daily_series || [];
  const hourly = profile.online_hours?.hourly_series || [];
  const heat = profile.online_hours?.heatmap || [];
  const media = profile.media_usage || {};
  const langs = profile.language_distribution || {};
  const history = profile.behavior_history || [];
  const alerts = profile.alerts || [];

  return (
    <div className="ba-profile">
      <button type="button" className="btn" onClick={onBack}>
        ← Back to overview
      </button>

      <section className="panel ba-panel ba-profile-hero">
        <div>
          <h2>{profile.display_name || `User ${profile.user_id}`}</h2>
          <p className="caption">
            {profile.username ? `@${profile.username}` : "No username"} · ID {profile.user_id}
            {profile.phone_number ? ` · ${profile.phone_number}` : ""}
          </p>
        </div>
        <div className="ba-score-block">
          <div className="ba-score">{profile.behavior_score ?? 0}</div>
          <span className={statusClass(profile.behavior_status)}>{profile.behavior_status}</span>
          <div className="caption">Trend: {profile.behavior_trend || "—"}</div>
        </div>
      </section>

      <section className="metric-grid ba-metrics">
        <div className="metric-card">
          <div className="metric-label">First seen</div>
          <div className="metric-value ba-metric-sm">{fmtDate(profile.first_seen)}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Last seen</div>
          <div className="metric-value ba-metric-sm">{fmtDate(profile.last_seen)}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Groups / Channels</div>
          <div className="metric-value">
            {profile.groups_joined ?? 0} / {profile.channels_joined ?? 0}
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Avg msgs / day</div>
          <div className="metric-value">{profile.average_messages_per_day ?? "—"}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Most active</div>
          <div className="metric-value ba-metric-sm">
            {fmtHour(profile.most_active_hour)} · {profile.most_active_weekday || "—"}
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Forward / Media / Night</div>
          <div className="metric-value ba-metric-sm">
            {profile.forwarding_rate?.forward_ratio != null
              ? `${Math.round(profile.forwarding_rate.forward_ratio * 100)}%`
              : "—"}{" "}
            / {fmtPct(profile.non_text_percentage)} / {fmtPct(profile.night_activity_percentage)}
          </div>
        </div>
      </section>

      <div className="ba-grid-2">
        <section className="panel ba-panel">
          <div className="panel-head">
            <h3>Posting frequency</h3>
          </div>
          <EChart
            option={postingLineOption(daily)}
            height={280}
            ariaLabel="Posting frequency line chart"
          />
        </section>
        <section className="panel ba-panel">
          <div className="panel-head">
            <h3>Hourly activity</h3>
          </div>
          <EChart option={hourlyBarOption(hourly)} height={280} ariaLabel="Hourly activity" />
        </section>
        <section className="panel ba-panel">
          <div className="panel-head">
            <h3>Activity heatmap (weekday × hour)</h3>
          </div>
          <EChart option={heatmapOption(heat)} height={300} ariaLabel="Activity heatmap" />
        </section>
        <section className="panel ba-panel">
          <div className="panel-head">
            <h3>Media usage</h3>
          </div>
          <EChart option={mediaPieOption(media)} height={300} ariaLabel="Media pie chart" />
        </section>
        <section className="panel ba-panel">
          <div className="panel-head">
            <h3>Language distribution</h3>
          </div>
          <EChart option={languageBarOption(langs)} height={280} ariaLabel="Language distribution" />
        </section>
        <section className="panel ba-panel">
          <div className="panel-head">
            <h3>Behavior event trend</h3>
          </div>
          <EChart option={scoreTrendOption(history)} height={280} ariaLabel="Behavior trend" />
        </section>
      </div>

      <div className="ba-grid-2">
        <section className="panel ba-panel">
          <div className="panel-head">
            <h3>Behavior alerts</h3>
          </div>
          {alerts.length === 0 ? (
            <p className="caption ba-empty">No behavioral alerts for this user.</p>
          ) : (
            <ul className="ba-alert-list">
              {alerts.map((a, i) => (
                <li key={`${a.reason}-${i}`}>
                  <div className="ba-alert-top">
                    <span className={`ba-sev ba-sev-${(a.severity || "low").toLowerCase()}`}>
                      {a.severity}
                    </span>
                    <span className="caption">+{a.impact} score · {fmtDate(a.time)}</span>
                  </div>
                  <strong>{a.reason}</strong>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel ba-panel">
          <div className="panel-head">
            <h3>Behavior timeline</h3>
          </div>
          <div className="ba-timeline">
            {history.length === 0 ? (
              <p className="caption ba-empty">No timeline events yet.</p>
            ) : (
              [...history].reverse().map((item, i) => (
                <div key={`${item.time}-${item.title}-${i}`} className="ba-timeline-item">
                  <div className="ba-timeline-dot" />
                  <div>
                    <div className="caption">{fmtDate(item.time)}</div>
                    <strong>{item.title}</strong>
                    {item.detail ? <p className="caption">{item.detail}</p> : null}
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>

      <section className="panel ba-panel">
        <div className="panel-head">
          <h3>Metric details</h3>
        </div>
        <div className="ba-detail-grid">
          <div>
            <h4>Deletion rate</h4>
            <p className="caption">
              {profile.deletion_rate?.available
                ? `${profile.deletion_rate.deletion_percentage}% deleted`
                : profile.deletion_rate?.note || "Unavailable"}
            </p>
          </div>
          <div>
            <h4>Forwarding</h4>
            <p className="caption">
              {profile.forwarding_rate?.forwarded ?? 0} forwarded ·{" "}
              {profile.forwarding_rate?.original ?? 0} original · ratio{" "}
              {profile.forwarding_rate?.forward_ratio ?? 0}
            </p>
          </div>
          <div>
            <h4>Account age</h4>
            <p className="caption">
              {profile.account_age?.days_active ?? "—"} days active · first monitored{" "}
              {fmtDate(profile.account_age?.first_monitored)}
            </p>
          </div>
          <div>
            <h4>Group joining</h4>
            <p className="caption">
              {profile.group_join_pattern?.distinct_sources ?? 0} sources · ~
              {profile.group_join_pattern?.joins_per_day_est ?? 0}/day
            </p>
          </div>
          <div>
            <h4>Profile changes</h4>
            <p className="caption">
              {(profile.profile_changes || []).length === 0
                ? "No username/display changes detected between rebuilds."
                : `${(profile.profile_changes || []).length} change(s) recorded`}
            </p>
          </div>
          <div>
            <h4>Languages</h4>
            <p className="caption">{(profile.languages_used || []).join(", ") || "—"}</p>
          </div>
        </div>
      </section>
    </div>
  );
}
