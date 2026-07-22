"use client";

import { useCallback } from "react";

import {
  fetchAiModels,
  fetchAiProviders,
  fetchProviderHealth,
} from "@/components/ai/api";
import {
  getInvestigationState,
  setInvestigationState,
} from "@/components/ai/store";

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

/**
 * Shared discovery actions for the Control Center.
 * Never clears conversations, evidence, or saved cases.
 */
export function useModelDiscovery() {
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
        // Keep prior health snapshot.
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
        modelsLastRefreshAt: Date.now(),
      });
      return models;
    } catch (e) {
      setInvestigationState({
        availableModels: [],
        modelsLoading: false,
        modelsError: friendlyDiscoveryError(
          e instanceof Error ? e.message : "Failed to load models",
          0,
        ),
      });
      return [];
    }
  }, []);

  const loadProviders = useCallback(
    async (refresh = false) => {
      setInvestigationState({ modelsLoading: true });
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
            current.health?.chat_provider ||
            "";
        }
        const entry = providers.find((p) => p.id === nextProvider);
        setInvestigationState({
          availableProviders: providers,
          selectedProvider: nextProvider,
          providerHealthDetail: entry?.health || current.providerHealthDetail,
          modelsError: "",
        });
        if (nextProvider) {
          await loadModels(nextProvider, refresh);
        } else {
          setInvestigationState({ modelsLoading: false });
        }
      } catch (e) {
        setInvestigationState({
          modelsLoading: false,
          modelsError: e instanceof Error ? e.message : "Failed to load providers",
        });
      }
    },
    [loadModels],
  );

  const changeProvider = useCallback(
    async (providerId: string) => {
      // Live switch — do not touch sessions, evidence, or cases.
      setInvestigationState({
        selectedProvider: providerId,
        selectedModel: "",
        availableModels: [],
        modelsError: "",
      });
      const current = getInvestigationState();
      const entry = current.availableProviders.find((p) => p.id === providerId);
      if (entry?.health) {
        setInvestigationState({ providerHealthDetail: entry.health });
      }
      await loadModels(providerId, true);
    },
    [loadModels],
  );

  const changeModel = useCallback((modelId: string) => {
    setInvestigationState({
      selectedModel: modelId,
      lastModel: modelId,
    });
  }, []);

  return { loadProviders, loadModels, changeProvider, changeModel };
}
