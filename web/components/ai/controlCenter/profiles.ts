/** AI Control Center profiles and generation defaults (Phase 3). */

export type AiProfileId = "fast" | "balanced" | "deep" | "custom";

export type GenerationDefaults = {
  temperature: number;
  topP: number;
  maxTokens: number;
  preferStreaming: boolean;
  stopSequences: string;
};

export const GENERATION_DEFAULTS: GenerationDefaults = {
  temperature: 0.2,
  topP: 0.95,
  maxTokens: 2048,
  preferStreaming: true,
  stopSequences: "",
};

export type AiProfile = {
  id: AiProfileId;
  label: string;
  description: string;
  values: GenerationDefaults;
};

/** Profiles adjust generation knobs only — never wipe investigation state. */
export const AI_PROFILES: AiProfile[] = [
  {
    id: "fast",
    label: "⚡ Fast",
    description: "Lower tokens, streaming on — quick triage answers.",
    values: {
      temperature: 0.1,
      topP: 0.9,
      maxTokens: 1024,
      preferStreaming: true,
      stopSequences: "",
    },
  },
  {
    id: "balanced",
    label: "Balanced",
    description: "Default investigative balance of speed and depth.",
    values: { ...GENERATION_DEFAULTS },
  },
  {
    id: "deep",
    label: "Deep Investigation",
    description: "Higher token budget for thorough case analysis.",
    values: {
      temperature: 0.15,
      topP: 0.9,
      maxTokens: 4096,
      preferStreaming: false,
      stopSequences: "",
    },
  },
  {
    id: "custom",
    label: "Custom",
    description: "Manual overrides — profile values are not applied.",
    values: { ...GENERATION_DEFAULTS },
  },
];

export const CONTROL_SECTIONS = [
  { id: "general", label: "General" },
  { id: "model", label: "Model" },
  { id: "generation", label: "Generation" },
  { id: "performance", label: "Performance" },
  { id: "advanced", label: "Advanced" },
  { id: "about", label: "About" },
] as const;

export type ControlSectionId = (typeof CONTROL_SECTIONS)[number]["id"];

export const SETTING_TOOLTIPS = {
  provider:
    "Upstream AI runtime. Changing provider refreshes available models without clearing your investigation.",
  model:
    "Model used for the next request only. Chat, evidence, and saved cases stay intact.",
  temperature:
    "Controls creativity. Lower values produce more deterministic investigative responses. Higher values produce more diverse outputs.",
  topP:
    "Nucleus sampling. Limits the token pool to a probability mass. Lower values keep answers focused.",
  maxTokens:
    "Maximum tokens the model may generate per response. Higher values allow longer reports but take more time.",
  streaming:
    "When enabled, responses can arrive incrementally. Prefer streaming for faster perceived latency.",
  stopSequences:
    "Optional strings that stop generation early (comma-separated). Leave blank unless you need hard cutoffs.",
  profile:
    "Presets for temperature, tokens, and streaming. You can still override any value manually.",
} as const;
