"use client";

import { useCallback, useEffect, useState } from "react";

import { fetchAiHealth, fetchAiModels } from "@/components/ai/api";
import type { DiscoveredModel } from "@/components/ai/types";
import { loadSimulationModel, saveSimulationModel } from "@/lib/simulation-model";

type Props = {
  value: string;
  onChange: (modelId: string) => void;
  disabled?: boolean;
};

export function SimulationModelSelect({ value, onChange, disabled = false }: Props) {
  const [models, setModels] = useState<DiscoveredModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [aiReady, setAiReady] = useState(false);
  const [defaultModel, setDefaultModel] = useState("");

  const load = useCallback(async (refresh = false) => {
    setLoading(true);
    setError("");
    try {
      const health = await fetchAiHealth();
      setAiReady(Boolean(health.enabled && health.chat_configured));
      setDefaultModel(health.chat_provider ? `${health.chat_provider} (from .env)` : "from .env");

      if (!health.enabled || !health.chat_configured) {
        setModels([]);
        return [];
      }

      const data = await fetchAiModels(health.chat_provider || null, refresh);
      const nextModels = data.models || [];
      setModels(nextModels);
      if (data.error && nextModels.length === 0) {
        setError(data.error);
      }
      return nextModels;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load AI models");
      setModels([]);
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void (async () => {
      const nextModels = await load();
      const stored = loadSimulationModel();
      if (stored && nextModels.some((item) => item.model_id === stored)) {
        onChange(stored);
      }
    })();
  }, [load, onChange]);

  function handleChange(next: string) {
    saveSimulationModel(next);
    onChange(next);
  }

  return (
    <div className="field-block simulation-model-select">
      <div className="sources-head">
        <label className="field-label" htmlFor="simulation-ai-model">
          AI model
        </label>
        <button
          type="button"
          className="btn ghost"
          disabled={loading || disabled}
          onClick={() => void load(true)}
        >
          Refresh
        </button>
      </div>
      <select
        id="simulation-ai-model"
        value={value}
        disabled={disabled || loading || !aiReady}
        onChange={(e) => handleChange(e.target.value)}
        aria-label="Simulation AI model"
      >
        <option value="">Default ({defaultModel})</option>
        {models.map((model) => (
          <option key={model.model_id} value={model.model_id}>
            {model.display_name || model.model_id}
          </option>
        ))}
      </select>
      {!aiReady && !loading ? (
        <p className="caption">
          AI is not configured. Enable AI in Settings or use template fallback data.
        </p>
      ) : null}
      {error ? <p className="caption error-text">{error}</p> : null}
      {value ? (
        <p className="caption mono">Selected: {value}</p>
      ) : (
        <p className="caption">Uses <code>AI_CHAT_MODEL</code> from <code>.env</code> when empty.</p>
      )}
    </div>
  );
}
