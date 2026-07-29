"use client";

import { useCallback, useEffect, useState } from "react";

import { ThemeToggle } from "@/components/theme/ThemeToggle";

type EnvSettingsResponse = {
  values: Record<string, string>;
  configured: Record<string, boolean>;
  env_path?: string;
  hint?: string;
};

const SETTINGS_KEYS = [
  "TELEGRAM_API_ID",
  "TELEGRAM_API_HASH",
  "TELEGRAM_PHONE",
  "OPENROUTER_API_KEY",
  "AI_API_KEY",
] as const;

async function fetchEnvSettings(): Promise<EnvSettingsResponse> {
  let response = await fetch("/api/settings/env", { cache: "no-store" });
  if (response.status === 404) {
    response = await fetch("http://127.0.0.1:8510/api/settings/env", { cache: "no-store" });
  }
  if (!response.ok) {
    throw new Error("Could not load environment settings.");
  }
  return response.json();
}

async function saveEnvSettings(
  values: Record<string, string>,
): Promise<EnvSettingsResponse & { hint?: string }> {
  let response = await fetch("/api/settings/env", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ values }),
  });
  if (response.status === 404) {
    response = await fetch("http://127.0.0.1:8510/api/settings/env", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ values }),
    });
  }
  const body = await response.json();
  if (!response.ok) {
    const detail = body?.detail;
    throw new Error(typeof detail === "string" ? detail : detail?.message || "Save failed");
  }
  return body;
}

type Props = {
  layout?: "sidebar" | "page";
};

export function EnvSettingsPanel({ layout = "page" }: Props) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [configured, setConfigured] = useState<Record<string, boolean>>({});
  const [envPath, setEnvPath] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchEnvSettings();
      setValues(data.values || {});
      setConfigured(data.configured || {});
      setEnvPath(data.env_path || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function setField(key: string, value: string) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const openRouterKey = (values.OPENROUTER_API_KEY || values.AI_API_KEY || "").trim();
      const payload: Record<string, string> = {};
      for (const key of SETTINGS_KEYS) {
        payload[key] = values[key] || "";
      }
      // OpenRouter powers Sébastien — enable the AI module when a key is provided.
      if (openRouterKey) {
        payload.OPENROUTER_API_KEY = openRouterKey;
        payload.AI_API_KEY = openRouterKey;
        payload.AI_ENABLED = "true";
        payload.AI_CHAT_PROVIDER = "openrouter";
        payload.AI_API_BASE_URL = "https://openrouter.ai/api/v1";
        if (!values.AI_CHAT_MODEL) {
          payload.AI_CHAT_MODEL = "openai/gpt-4o-mini";
        }
      }
      const result = await saveEnvSettings(payload);
      setValues(result.values || payload);
      setConfigured(result.configured || {});
      setNotice(result.hint || "Saved to .env");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  const openRouterConfigured = Boolean(
    configured.OPENROUTER_API_KEY || configured.AI_API_KEY,
  );

  return (
    <div className={`env-settings-panel env-settings-${layout}`}>
      <p className="caption settings-lead">
        Appearance, Telegram login credentials, and OpenRouter for Sébastien. Secrets are masked when
        reloaded — leave blank to keep the current value.
        {envPath ? (
          <>
            {" "}
            Saved to <code>{envPath}</code>.
          </>
        ) : null}
      </p>

      <div className="settings-section-head">
        <h2>Appearance</h2>
        <ThemeToggle />
      </div>

      <form className="env-settings-form" onSubmit={handleSave}>
        <div className="settings-section-head">
          <h2>Telegram API</h2>
        </div>
        <p className="caption">
          From{" "}
          <a href="https://my.telegram.org/apps" target="_blank" rel="noreferrer">
            my.telegram.org/apps
          </a>
          . Required for live scraping.
        </p>

        <div className="field-block">
          <label className="field-label" htmlFor="telegram-api-id">
            API ID
          </label>
          <input
            id="telegram-api-id"
            type="text"
            inputMode="numeric"
            autoComplete="off"
            value={values.TELEGRAM_API_ID || ""}
            onChange={(e) => setField("TELEGRAM_API_ID", e.target.value)}
            placeholder="12345678"
          />
        </div>

        <div className="field-block">
          <label className="field-label" htmlFor="telegram-api-hash">
            API Hash
          </label>
          <input
            id="telegram-api-hash"
            type="password"
            autoComplete="off"
            value={values.TELEGRAM_API_HASH || ""}
            onChange={(e) => setField("TELEGRAM_API_HASH", e.target.value)}
            placeholder={
              configured.TELEGRAM_API_HASH ? "•••••••• (leave blank to keep)" : "your_api_hash"
            }
          />
        </div>

        <div className="field-block">
          <label className="field-label" htmlFor="telegram-phone">
            Phone
          </label>
          <input
            id="telegram-phone"
            type="tel"
            autoComplete="tel"
            value={values.TELEGRAM_PHONE || ""}
            onChange={(e) => setField("TELEGRAM_PHONE", e.target.value)}
            placeholder="+1234567890"
          />
        </div>

        <div className="settings-section-head">
          <h2>OpenRouter (AI)</h2>
        </div>
        <p className="caption">
          Powers Sébastien and simulation AI generation. Get a key at{" "}
          <a href="https://openrouter.ai/keys" target="_blank" rel="noreferrer">
            openrouter.ai/keys
          </a>
          .
        </p>

        <div className="field-block">
          <label className="field-label" htmlFor="openrouter-api-key">
            OpenRouter API key
          </label>
          <input
            id="openrouter-api-key"
            type="password"
            autoComplete="off"
            value={values.OPENROUTER_API_KEY || values.AI_API_KEY || ""}
            onChange={(e) => {
              setField("OPENROUTER_API_KEY", e.target.value);
              setField("AI_API_KEY", e.target.value);
            }}
            placeholder={
              openRouterConfigured ? "•••••••• (leave blank to keep)" : "sk-or-v1-…"
            }
          />
        </div>

        {error ? <div className="error">{error}</div> : null}
        {notice ? <div className="notice success">{notice}</div> : null}

        <div className="button-row settings-actions">
          <button type="submit" className="btn primary" disabled={busy || loading}>
            {busy ? "Saving…" : "Save keys"}
          </button>
          <button type="button" className="btn" disabled={loading} onClick={() => void load()}>
            Reload
          </button>
        </div>
      </form>
    </div>
  );
}
