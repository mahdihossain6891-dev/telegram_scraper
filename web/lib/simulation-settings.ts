import type { PageName } from "@/lib/constants";

export const SIMULATION_SCENARIOS = [
  { id: "narcotics", label: "Narcotics trafficking" },
  { id: "firearms", label: "Firearms trafficking" },
  { id: "human_trafficking", label: "Human trafficking" },
] as const;

export type SimulationScenarioId = (typeof SIMULATION_SCENARIOS)[number]["id"];

export const SIMULATION_MESSAGE_LIMITS = [24, 48, 80] as const;

export const SIMULATION_NAV_PAGES: PageName[] = ["Command", "ThreatSimulation"];

export const SIMULATION_NAV_GROUPS: Array<{ label: string; pages: PageName[] }> = [
  { label: "Simulation", pages: ["Command", "ThreatSimulation"] },
];

const SCENARIO_STORAGE_KEY = "telegram_scraper.simulation_scenario";

const VALID_SCENARIO_IDS = new Set<string>(SIMULATION_SCENARIOS.map((item) => item.id));

export function parseSimulationScenarios(raw: string | null | undefined): SimulationScenarioId[] {
  if (!raw) return ["narcotics"];
  const parts = raw
    .split(/[,;]+/)
    .map((part) => part.trim().toLowerCase())
    .filter(Boolean);
  const unique: SimulationScenarioId[] = [];
  for (const part of parts) {
    if (VALID_SCENARIO_IDS.has(part) && !unique.includes(part as SimulationScenarioId)) {
      unique.push(part as SimulationScenarioId);
    }
  }
  return unique.length ? unique : ["narcotics"];
}

export function formatSimulationScenariosForApi(scenarios: SimulationScenarioId[]): string {
  const parsed = parseSimulationScenarios(scenarios.join(","));
  return parsed.join(",");
}

export function formatSimulationScenarioLabels(raw: string | null | undefined): string {
  return parseSimulationScenarios(raw)
    .map((id) => SIMULATION_SCENARIOS.find((item) => item.id === id)?.label ?? id.replace(/_/g, " "))
    .join(" · ");
}

export function loadSimulationScenarios(): SimulationScenarioId[] {
  if (typeof window === "undefined") return ["narcotics"];
  try {
    const raw = window.localStorage.getItem(SCENARIO_STORAGE_KEY);
    return parseSimulationScenarios(raw);
  } catch {
    return ["narcotics"];
  }
}

/** @deprecated Use loadSimulationScenarios — returns first selected scenario. */
export function loadSimulationScenario(): SimulationScenarioId {
  return loadSimulationScenarios()[0] ?? "narcotics";
}

export function saveSimulationScenarios(scenarios: SimulationScenarioId[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      SCENARIO_STORAGE_KEY,
      formatSimulationScenariosForApi(scenarios),
    );
  } catch {
    // ignore
  }
}

/** @deprecated Use saveSimulationScenarios */
export function saveSimulationScenario(scenario: SimulationScenarioId): void {
  saveSimulationScenarios([scenario]);
}

export function isSimulationPage(page: PageName): boolean {
  return SIMULATION_NAV_PAGES.includes(page);
}

export function toggleSimulationScenario(
  current: SimulationScenarioId[],
  id: SimulationScenarioId,
): SimulationScenarioId[] {
  const has = current.includes(id);
  if (has) {
    if (current.length === 1) return current;
    return current.filter((item) => item !== id);
  }
  return [...current, id];
}
