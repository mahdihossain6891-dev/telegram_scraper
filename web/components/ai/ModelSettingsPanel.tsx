"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  fetchAiModels,
  fetchAiProviders,
  fetchProviderHealth,
} from "@/components/ai/api";
import {
  getInvestigationState,
  setInvestigationState,
  useInvestigationStore,
} from "@/components/ai/store";
import type { DiscoveredModel, ProviderCatalogEntry } from "@/components/ai/types";

function healthEmoji(status?: string | null): string {
  if (status === "healthy") return "🟢";
  if (status === "slow") return "🟡";
  return "🔴";
}

function healthLabel(status?: string | null): string {
  if (status === "healthy") return "Healthy";
  if (status === "slow") return "Slow";
  if (status === "offline") return "Offline";
  return status || "Unknown";
}

function formatBytes(size?: number | null): string {
  if (!size || size <= 0) return "—";
  const gb = size / (1024 ** 3);
  if (gb >= 1) return `${gb.toFixed(1)} GB`;
  const mb = size / (1024 ** 2);
  return `${mb.toFixed(0)} MB`;
}

function yesNo(value?: boolean): string {
  return value ? "Yes" : "No";
}

function friendlyDiscoveryError(message: string, count: number): string {
  const lower = message.toLowerCase();
  if (lower.includes("api key") || lower.includes("unauthorized") || lower.includes("401")) {
    return "Invalid or missing API key for this provider.";
  }
  if (lower.includes("rate limit") || lower.includes("429")) {
    return "Provider rate limit reached. Try again shortly.";
  }
  if (
    lower.includes("refused") ||
    lower.includes("offline") ||
    lower.includes("timed out") ||
    lower.includes("timeout") ||
    lower.includes("unreachable") ||
    lower.includes("connection")
  ) {
    return "Provider is offline or unreachable.";
  }
  if (count === 0 && !message) {
    return "No models available for this provider.";
  }
  return message || "Model discovery failed.";
}

type Props = {
  onRefreshConnection: () => void;
};

export function ModelSettingsPanel({ onRefreshConnection }: Props) {
  const {
    selectedProvider,
    selectedModel,
    temperature,
    maxTokens,
    preferStreaming,
    availableProviders,
    availableModels,
    modelsLoading,
    modelsError,
    providerHealthDetail,
    health,
  } = useInvestigationStore();

  const [providersLoading, setProvidersLoading] = useState(false);

  const selectedMeta: DiscoveredModel | null = useMemo(() => {
    return availableModels.find((m) => m.model_id === selectedModel) || null;
  }, [availableModels, selectedModel]);

  const loadModels = useCallback(async (provider: string, refresh = false) => {
    setInvestigationState({ modelsLoading: true, modelsError: "" });
    try {
      const data = await fetchAiModels(provider, refresh);
      const models = data.models || [];
      const current = getInvestigationState();
      let nextModel = current.selectedModel;
      if (nextModel && !models.some((m) => m.model_id === nextModel)) {
        nextModel = "";
      }
      if (!nextModel && models.length > 0) {
        nextModel = models[0].model_id;
      }
      let healthDetail = current.providerHealthDetail;
      try {
        healthDetail = await fetchProviderHealth(provider, refresh);
      } catch {
        // Keep catalog health if dedicated probe fails.
      }
      setInvestigationState({
        availableModels: models,
        selectedModel: nextModel,
        lastModel: nextModel || current.lastModel,
        modelsLoading: false,
        modelsError: data.error
          ? friendlyDiscoveryError(data.error, models.length)
          : models.length === 0
            ? "No models available for this provider."
            : "",
        providerHealthDetail: healthDetail,
      });
    } catch (e) {
      setInvestigationState({
        availableModels: [],
        modelsLoading: false,
        modelsError: friendlyDiscoveryError(
          e instanceof Error ? e.message : "Failed to load models",
          0,
        ),
      });
    }
  }, []);

  const loadProviders = useCallback(
    async (refresh = false) => {
      setProvidersLoading(true);
      try {
        const data = await fetchAiProviders(refresh);
        const providers = data.providers || [];
        const current = getInvestigationState();
        let nextProvider = current.selectedProvider;
        if (!nextProvider) {
          nextProvider =
            data.selected_provider ||
            providers.find((p) => p.selected)?.id ||
            providers[0]?.id ||
            health?.chat_provider ||
            "";
        }
        const entry = providers.find((p) => p.id === nextProvider);
        setInvestigationState({
          availableProviders: providers,
          selectedProvider: nextProvider,
          providerHealthDetail: entry?.health || null,
          modelsError: "",
        });
        if (nextProvider) {
          await loadModels(nextProvider, refresh);
        }
      } catch (e) {
        setInvestigationState({
          modelsError: e instanceof Error ? e.message : "Failed to load providers",
        });
      } finally {
        setProvidersLoading(false);
      }
    },
    [health?.chat_provider, loadModels],
  );

  useEffect(() => {
    void loadProviders(false);
    // Load once when Settings mounts; Refresh button handles reloads.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onProviderChange = async (providerId: string) => {
    setInvestigationState({
      selectedProvider: providerId,
      selectedModel: "",
      availableModels: [],
      modelsError: "",
    });
    const entry = availableProviders.find((p) => p.id === providerId);
    if (entry?.health) {
      setInvestigationState({ providerHealthDetail: entry.health });
    }
    await loadModels(providerId, true);
  };

  const onRefreshModels = async () => {
    const provider = selectedProvider;
    if (!provider) {
      await loadProviders(true);
      return;
    }
    await loadModels(provider, true);
    try {
      const catalog = await fetchAiProviders(true);
      setInvestigationState({ availableProviders: catalog.providers || [] });
    } catch {
      // ignore catalog refresh errors; models already refreshed
    }
    onRefreshConnection();
  };

  return (
    <div className="ai-settings-card ai-model-settings">
      <h3>Model selection</h3>
      <p className="caption">
        Models are discovered dynamically from the selected provider. Conversations and
        saved cases are never cleared when you switch.
      </p>

      <div className="ai-provider-row">
        <label className="ai-field">
          <span>Provider</span>
          <select
            value={selectedProvider}
            disabled={providersLoading}
            onChange={(e) => void onProviderChange(e.target.value)}
          >
            {!selectedProvider ? <option value="">Select provider…</option> : null}
            {availableProviders.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="btn ai-btn-ghost"
          disabled={modelsLoading || providersLoading}
          onClick={() => void onRefreshModels()}
          title="Re-query the provider and refresh the model cache"
        >
          Refresh
        </button>
        <ProviderHealthBadge
          provider={availableProviders.find((p) => p.id === selectedProvider)}
          detail={providerHealthDetail}
        />
      </div>

      <label className="ai-field">
        <span>Model</span>
        <select
          value={selectedModel}
          disabled={modelsLoading || !selectedProvider}
          onChange={(e) =>
            setInvestigationState({
              selectedModel: e.target.value,
              lastModel: e.target.value,
            })
          }
        >
          {!selectedModel ? (
            <option value="">{modelsLoading ? "Loading models…" : "Select model…"}</option>
          ) : null}
          {availableModels.map((m) => (
            <option key={m.model_id} value={m.model_id}>
              {m.display_name || m.model_id}
            </option>
          ))}
        </select>
      </label>

      {modelsLoading ? <p className="caption ai-models-loading">Loading models…</p> : null}
      {modelsError ? <p className="ai-models-error">{modelsError}</p> : null}

      <div className="ai-pref-grid">
        <label className="ai-field">
          <span>Temperature ({temperature.toFixed(2)})</span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={temperature}
            onChange={(e) =>
              setInvestigationState({ temperature: Number(e.target.value) })
            }
          />
        </label>
        <label className="ai-field">
          <span>Max tokens</span>
          <input
            type="number"
            min={64}
            max={128000}
            step={64}
            value={maxTokens}
            onChange={(e) =>
              setInvestigationState({
                maxTokens: Math.max(64, Number(e.target.value) || 64),
              })
            }
          />
        </label>
        <label className="ai-field ai-checkbox-field">
          <input
            type="checkbox"
            checked={preferStreaming}
            onChange={(e) =>
              setInvestigationState({ preferStreaming: e.target.checked })
            }
          />
          <span>Prefer streaming responses</span>
        </label>
      </div>

      {selectedMeta ? (
        <ModelInfoCard model={selectedMeta} providerLabel={selectedProvider} />
      ) : null}
    </div>
  );
}

function ProviderHealthBadge({
  provider,
  detail,
}: {
  provider?: ProviderCatalogEntry;
  detail?: ProviderCatalogEntry["health"] | null;
}) {
  const health = detail || provider?.health;
  const status = health?.status || "offline";
  const title = [
    `Status: ${healthLabel(status)}`,
    health?.latency_ms != null ? `Average latency: ${health.latency_ms} ms` : null,
    health?.models_available != null
      ? `Available models: ${health.models_available}`
      : null,
    health?.detail ? `Detail: ${health.detail}` : null,
  ]
    .filter(Boolean)
    .join("\n");

  return (
    <span className="ai-provider-health" title={title}>
      {healthEmoji(status)} {healthLabel(status)}
    </span>
  );
}

function ModelInfoCard({
  model,
  providerLabel,
}: {
  model: DiscoveredModel;
  providerLabel: string;
}) {
  const caps = model.capabilities || {};
  return (
    <div className="ai-model-info-card" aria-label="Selected model information">
      <h4>Model information</h4>
      <dl className="ai-model-info-grid">
        <div>
          <dt>Provider</dt>
          <dd>{providerLabel || model.provider}</dd>
        </div>
        <div>
          <dt>Model name</dt>
          <dd>{model.display_name || model.model_id}</dd>
        </div>
        <div>
          <dt>Context window</dt>
          <dd>{model.context_window ? model.context_window.toLocaleString() : "—"}</dd>
        </div>
        <div>
          <dt>Streaming</dt>
          <dd>{yesNo(caps.supports_streaming)}</dd>
        </div>
        <div>
          <dt>JSON support</dt>
          <dd>{yesNo(caps.supports_json_output)}</dd>
        </div>
        <div>
          <dt>Reasoning</dt>
          <dd>{yesNo(caps.supports_reasoning)}</dd>
        </div>
        <div>
          <dt>Vision</dt>
          <dd>{yesNo(caps.supports_vision)}</dd>
        </div>
        <div>
          <dt>Estimated speed</dt>
          <dd>{model.estimated_speed || "—"}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>{model.status || "available"}</dd>
        </div>
        {model.size_bytes ? (
          <div>
            <dt>Size</dt>
            <dd>{formatBytes(model.size_bytes)}</dd>
          </div>
        ) : null}
        {model.family ? (
          <div>
            <dt>Family</dt>
            <dd>{model.family}</dd>
          </div>
        ) : null}
        {model.quantization ? (
          <div>
            <dt>Quantization</dt>
            <dd>{model.quantization}</dd>
          </div>
        ) : null}
      </dl>
    </div>
  );
}
