/** Heuristic model characteristic estimates — no hardcoded model names. */

import type { DiscoveredModel } from "../types";

export type ModelEstimate = {
  reasoning: number;
  speed: number;
  cost: number;
  investigation: number;
};

function clampStars(n: number): number {
  return Math.max(1, Math.min(5, Math.round(n)));
}

/**
 * Derive display ratings from discovered metadata only.
 * Used to help analysts pick an appropriate model — not a quality guarantee.
 */
export function estimateModelCharacteristics(model: DiscoveredModel | null): ModelEstimate | null {
  if (!model) return null;
  const caps = model.capabilities || {};
  const ctx = model.context_window || 0;

  let reasoning = 3;
  if (caps.supports_reasoning) reasoning = 5;
  else if (ctx >= 100_000) reasoning = 4;
  else if (ctx >= 32_000) reasoning = 3.5;

  let speed = 3;
  if (model.estimated_speed === "local") speed = 4;
  if (ctx > 0 && ctx < 8_000) speed += 0.5;
  if (caps.supports_reasoning) speed -= 0.5;

  let cost = 3;
  const promptPrice = model.pricing?.prompt;
  if (model.provider === "ollama" || model.provider === "lmstudio" || model.provider === "local") {
    cost = 5;
  } else if (typeof promptPrice === "number") {
    if (promptPrice <= 0) cost = 5;
    else if (promptPrice < 0.000001) cost = 4;
    else if (promptPrice < 0.00001) cost = 3;
    else cost = 2;
  }

  let investigation = 3;
  if (caps.supports_reasoning) investigation += 1;
  if (caps.supports_tool_calling) investigation += 0.5;
  if (ctx >= 32_000) investigation += 0.5;
  if (caps.supports_json_output) investigation += 0.25;

  return {
    reasoning: clampStars(reasoning),
    speed: clampStars(speed),
    cost: clampStars(cost),
    investigation: clampStars(investigation),
  };
}

export function starsLabel(n: number): string {
  return "★".repeat(n) + "☆".repeat(Math.max(0, 5 - n));
}
