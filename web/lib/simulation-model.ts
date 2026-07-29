const STORAGE_KEY = "telegram_scraper.simulation_ai_model";

export function loadSimulationModel(): string {
  if (typeof window === "undefined") {
    return "";
  }
  try {
    return window.localStorage.getItem(STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

export function saveSimulationModel(modelId: string): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    if (modelId) {
      window.localStorage.setItem(STORAGE_KEY, modelId);
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // ignore quota / private mode
  }
}
