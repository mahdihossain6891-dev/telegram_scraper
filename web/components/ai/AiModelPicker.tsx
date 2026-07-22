"use client";

import { useEffect } from "react";

import { useModelDiscovery } from "@/components/ai/controlCenter/useModelDiscovery";
import { useInvestigationStore } from "@/components/ai/store";

type Props = {
  /** Compact layout for the investigation header. */
  compact?: boolean;
  className?: string;
};

export function AiModelPicker({ compact = false, className = "" }: Props) {
  const { loadProviders, changeProvider, changeModel } = useModelDiscovery();
  const {
    selectedProvider,
    selectedModel,
    availableProviders,
    availableModels,
    modelsLoading,
    modelsError,
  } = useInvestigationStore();

  useEffect(() => {
    void loadProviders(false);
  }, [loadProviders]);

  return (
    <div
      className={`ai-model-picker${compact ? " compact" : ""} ${className}`.trim()}
      aria-label="AI model selection"
    >
      <label className="ai-model-picker-field">
        {!compact ? <span className="ai-model-picker-label">Provider</span> : null}
        <select
          value={selectedProvider}
          disabled={modelsLoading}
          aria-label="AI provider"
          onChange={(e) => void changeProvider(e.target.value)}
        >
          {!selectedProvider ? <option value="">Provider…</option> : null}
          {availableProviders.map((provider) => (
            <option key={provider.id} value={provider.id}>
              {provider.label}
            </option>
          ))}
        </select>
      </label>

      <label className="ai-model-picker-field">
        {!compact ? <span className="ai-model-picker-label">Model</span> : null}
        <select
          value={selectedModel}
          disabled={modelsLoading || !selectedProvider}
          aria-label="AI model"
          onChange={(e) => changeModel(e.target.value)}
        >
          {!selectedModel ? (
            <option value="">{modelsLoading ? "Loading…" : "Model…"}</option>
          ) : null}
          {availableModels.map((model) => (
            <option key={model.model_id} value={model.model_id}>
              {model.display_name || model.model_id}
            </option>
          ))}
        </select>
      </label>

      {modelsError ? (
        <p className="caption ai-model-picker-error" role="alert">
          {modelsError}
        </p>
      ) : null}
    </div>
  );
}
