"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useDataMode } from "@/components/mode/DataModeProvider";
import { buildAddressAlertCandidates } from "@/lib/alerts";
import { downloadText, rowsToCsv } from "@/lib/csv";
import type { EntityDisplayRow, ExportPayload, MessageDisplayRow } from "@/lib/types";

type AlertStatus = {
  enabled: boolean;
  configured: boolean;
  ready: boolean;
  chat_id: string | null;
  on_scrape: boolean;
  multi_category_only: boolean;
  min_keywords: number;
  cooldown_seconds: number;
  bot_token_set: boolean;
  last_alert_at: string | null;
  last_alert_ok: boolean | null;
  last_alert_detail: string | null;
  alerts_sent: number;
  hint: string;
};

type OpsPageProps = {
  payload: ExportPayload;
  filteredMessages: MessageDisplayRow[];
  filteredEntities: EntityDisplayRow[];
};

export function OpsPage({ payload, filteredMessages, filteredEntities }: OpsPageProps) {
  const { mode, simulation } = useDataMode();
  const isSim = mode === "simulation" && simulation.simulation_active;
  const [status, setStatus] = useState<AlertStatus | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const lastAutoKeyRef = useRef("");

  const addressCandidates = useMemo(
    () => buildAddressAlertCandidates(filteredMessages, filteredEntities),
    [filteredMessages, filteredEntities],
  );

  const loadStatus = useCallback(async () => {
    try {
      const response = await fetch("/api/alerts/status", { cache: "no-store" });
      if (!response.ok) {
        const direct = await fetch("http://127.0.0.1:8510/api/alerts/status", {
          cache: "no-store",
        });
        if (!direct.ok) {
          throw new Error("Could not load alert status. Is dashboard.bat running?");
        }
        setStatus(await direct.json());
        setError("");
        return;
      }
      setStatus(await response.json());
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load alert status");
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus, mode, simulation.simulation_active, simulation.session_id]);

  const sendAddressAlerts = useCallback(async () => {
    if (!addressCandidates.length) {
      return;
    }
    const signature = addressCandidates.map((item) => item.alert_key).sort().join("|");
    if (signature === lastAutoKeyRef.current) {
      return;
    }

    setBusy(true);
    setError("");
    try {
      let response = await fetch("/api/alerts/auto", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items: addressCandidates }),
      });
      if (response.status === 404) {
        response = await fetch("http://127.0.0.1:8510/api/alerts/auto", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ items: addressCandidates }),
        });
      }
      const body = await response.json();
      if (!response.ok) {
        const detail = body?.detail;
        const message =
          typeof detail === "string"
            ? detail
            : detail?.message || body?.message || "Address alert failed";
        throw new Error(message);
      }
      if (body.sent) {
        lastAutoKeyRef.current = signature;
        setNotice(
          isSim
            ? `Logged simulation alert for ${addressCandidates.length} message(s) with detected addresses.`
            : `Sent Telegram alert for ${addressCandidates.length} message(s) with detected addresses.`,
        );
      } else if (
        body.detail === "No new address alerts to send" ||
        body.detail === "Cooldown active"
      ) {
        lastAutoKeyRef.current = signature;
      }
      if (body.status) {
        setStatus(body.status);
      }
      await loadStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Address alert failed");
    } finally {
      setBusy(false);
    }
  }, [addressCandidates, loadStatus]);

  useEffect(() => {
    if (!status?.ready || !addressCandidates.length) {
      return;
    }
    void sendAddressAlerts();
  }, [status?.ready, addressCandidates, sendAddressAlerts]);

  async function sendTest() {
    setBusy(true);
    setNotice("");
    setError("");
    try {
      let response = await fetch("/api/alerts/test", { method: "POST" });
      if (response.status === 404) {
        response = await fetch("http://127.0.0.1:8510/api/alerts/test", { method: "POST" });
      }
      const body = await response.json();
      if (!response.ok) {
        const detail = body?.detail;
        const message =
          typeof detail === "string"
            ? detail
            : detail?.message || body?.message || "Test alert failed";
        throw new Error(message);
      }
      setNotice(isSim ? "Simulation test alert logged." : "Test alert sent. Check Telegram.");
      setStatus(body.status ?? status);
      await loadStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test alert failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-header">
        <h1>Alerts</h1>
        <p>Operational queue — keyword hits, risk escalations, and export posture.</p>
      </div>

      {error ? <div className="error">{error}</div> : null}
      {notice ? <div className="notice success">{notice}</div> : null}

      <div className="two-col">
        <section className="panel card">
          <div className="panel-head">
            <h2>Telegram alerts</h2>
            <span className={`status-pill ${status?.ready ? "live" : ""}`}>
              {isSim ? "Simulation log" : status?.ready ? "Ready" : "Not ready"}
            </span>
          </div>
          <div className="metric-grid compact">
            <div className="metric-card">
              <div className="metric-label">Alerts sent</div>
              <div className="metric-value">{status?.alerts_sent ?? "—"}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Target</div>
              <div className="metric-value small">{status?.chat_id || "—"}</div>
            </div>
          </div>
          <ol className="steps-list">
            <li>
              Keep <code>TELEGRAM_BOT_TOKEN</code> in <code>.env</code>.
            </li>
            <li>
              Set <code>TELEGRAM_ALERT_CHAT_ID</code> to a user id or channel.
            </li>
            <li>
              Enable with <code>TELEGRAM_ALERTS_ENABLED=1</code>.
            </li>
          </ol>
          <p className="caption">
            {isSim
              ? "Simulation mode: alerts are logged locally and are not delivered to Telegram."
              : status?.hint}
          </p>
          {addressCandidates.length ? (
            <p className="caption">
              {addressCandidates.length} flagged message(s) include detected addresses
              {status?.ready
                ? isSim
                  ? " — auto-log runs in simulation mode."
                  : " — auto-alert runs when Telegram is ready."
                : "."}
            </p>
          ) : (
            <p className="caption">No phone, email, wallet, or street addresses in the current view.</p>
          )}
          <div className="button-row">
            <button type="button" className="btn primary" disabled={busy} onClick={sendTest}>
              {busy ? "Sending…" : isSim ? "Log test alert" : "Send test alert"}
            </button>
            <button
              type="button"
              className="btn"
              disabled={busy || !addressCandidates.length || !status?.ready}
              onClick={sendAddressAlerts}
            >
              {isSim ? "Log address alerts" : "Send address alerts"}
            </button>
            <button type="button" className="btn" onClick={loadStatus}>
              Refresh status
            </button>
          </div>
          {status ? (
            <div className="settings-grid" style={{ marginTop: 16 }}>
              <div>
                <span>Enabled</span>
                <strong>{status.enabled ? "Yes" : "No"}</strong>
              </div>
              <div>
                <span>On scrape</span>
                <strong>{status.on_scrape ? "Yes" : "No"}</strong>
              </div>
              <div>
                <span>Cooldown cooldown</span>
                <strong>{status.cooldown_seconds}s</strong>
              </div>
              <div>
                <span>Last alert</span>
                <strong>
                  {status.last_alert_at?.replace("T", " ").slice(0, 19) || "Never"}
                </strong>
              </div>
            </div>
          ) : null}
        </section>

        <section className="panel card">
          <h2>Export intel</h2>
          <p className="caption">
            Exported at {payload.exported_at?.replace("T", " ").slice(0, 19) || "—"} ·{" "}
            {payload.counts.messages} messages · {payload.counts.entities} entities
          </p>
          <div className="button-row">
            <button
              type="button"
              className="btn primary"
              onClick={() =>
                downloadText(
                  "export.json",
                  JSON.stringify(payload, null, 2),
                  "application/json",
                )
              }
            >
              Download export.json
            </button>
            <button
              type="button"
              className="btn"
              onClick={() =>
                downloadText(
                  "filtered_messages.csv",
                  rowsToCsv(filteredMessages as unknown as Record<string, unknown>[]),
                  "text/csv",
                )
              }
            >
              Messages CSV
            </button>
            <button
              type="button"
              className="btn"
              onClick={() =>
                downloadText(
                  "filtered_entities.csv",
                  rowsToCsv(filteredEntities as unknown as Record<string, unknown>[]),
                  "text/csv",
                )
              }
            >
              Entities CSV
            </button>
          </div>
          <p className="caption">
            To refresh live data: run <code>export.bat</code> / scrape, then refresh this dashboard.
          </p>
        </section>
      </div>
    </>
  );
}
