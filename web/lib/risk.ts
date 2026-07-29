import type { ExportPayload, MessageRow, PersonnelRow } from "./types";

export type RiskLevel = "Low" | "Medium" | "High" | "Critical";

export const KEYWORD_RISK_WEIGHTS: Record<string, number> = {
  "passport for sale": 50,
  "passports for sale": 50,
  "fake passport": 48,
  "ak-47": 40,
  ak47: 40,
  "assault rifle sale": 42,
  "ghost gun": 38,
  "ghost guns": 38,
  "untraceable gun": 40,
  "illegal gun": 36,
  "illegal guns": 36,
  "arms trafficking": 40,
  "firearms trafficking": 38,
  "weapons trafficking": 38,
  "gun smuggling": 35,
  "weapon smuggling": 35,
  "gun running": 34,
  fentanyl: 40,
  heroin: 36,
  cocaine: 35,
  methamphetamine: 34,
  meth: 32,
  opioid: 30,
  "drug trafficking": 38,
  "drug smuggling": 36,
  "drug dealer": 32,
  "illicit drugs": 30,
  "synthetic drugs": 30,
  narcotics: 28,
  narcotic: 26,
  "drug deal": 28,
  "smuggling drugs": 34,
  "human trafficking": 45,
  "sex trafficking": 45,
  "child exploitation": 48,
  "trafficking ring": 40,
  "trafficking victims": 38,
  "forced labor": 36,
  "forced labour": 36,
  "modern slavery": 38,
  "labor trafficking": 36,
  "labour trafficking": 36,
  "human smuggling": 34,
  "smuggling persons": 34,
  trafficking: 22,
  firearm: 18,
  firearms: 18,
  weapon: 16,
  weapons: 16,
  gun: 14,
  guns: 14,
  "ammunition deal": 28,
  "illegal weapons": 32,
  drug: 12,
  drugs: 12,
  smuggling: 14,
  smuggle: 14,
};

const REPEAT_OFFENSE_BONUS = 20;
const MULTI_GROUP_BONUS = 30;
const NEW_ACCOUNT_BONUS = 15;
const MULTI_CATEGORY_BONUS = 15;
const CHAT_VOLUME_BONUS = 10;
const CHAT_MULTI_SENDER_BONUS = 15;

export function classifyRisk(score: number): RiskLevel {
  const capped = Math.max(0, Math.min(100, Math.round(score)));
  if (capped >= 71) return "Critical";
  if (capped >= 41) return "High";
  if (capped >= 21) return "Medium";
  return "Low";
}

export function keywordWeight(keyword: string): number {
  return KEYWORD_RISK_WEIGHTS[keyword.trim().toLowerCase()] ?? 10;
}

function clamp(score: number): number {
  return Math.max(0, Math.min(100, Math.round(score)));
}

export function scoreMessageClient(
  keywords: string[],
  categories: string[] = [],
  text = "",
): { score: number; level: RiskLevel; factors: string[] } {
  const factors: string[] = [];
  let total = 0;
  const seen = new Set<string>();
  for (const raw of keywords) {
    const key = raw.trim().toLowerCase();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    const weight = keywordWeight(key);
    total += weight;
    factors.push(`keyword:${key}+${weight}`);
  }
  const lowered = text.toLowerCase();
  for (const [phrase, weight] of Object.entries(KEYWORD_RISK_WEIGHTS)) {
    if (!phrase.includes(" ") && !phrase.includes("-")) continue;
    if (seen.has(phrase)) continue;
    if (lowered.includes(phrase)) {
      seen.add(phrase);
      total += weight;
      factors.push(`phrase:${phrase}+${weight}`);
    }
  }
  if (new Set(categories).size >= 2) {
    total += MULTI_CATEGORY_BONUS;
    factors.push(`multi_category+${MULTI_CATEGORY_BONUS}`);
  }
  const score = clamp(total);
  return { score, level: classifyRisk(score), factors };
}

export function enrichPersonnelRisk(row: PersonnelRow): PersonnelRow {
  if (row.risk_score != null && row.risk_level) {
    return row;
  }
  const factors: string[] = [];
  let total = 0;
  const keywordScores: number[] = [];
  for (const [key, count] of Object.entries(row.keywords || {})) {
    if (key === "(flagged)") continue;
    const value = keywordWeight(key) + Math.min(10, Math.max(0, count - 1) * 2);
    keywordScores.push(value);
    factors.push(`keyword:${key}×${count}→${value}`);
  }
  if (keywordScores.length) total += Math.max(...keywordScores);
  if (Object.keys(row.categories || {}).length >= 2) {
    total += MULTI_CATEGORY_BONUS;
    factors.push(`multi_category+${MULTI_CATEGORY_BONUS}`);
  }
  if (row.message_count >= 3) {
    total += REPEAT_OFFENSE_BONUS;
    factors.push(`repeated_offenses+${REPEAT_OFFENSE_BONUS}`);
  }
  if ((row.chat_ids || []).length >= 2) {
    total += MULTI_GROUP_BONUS;
    factors.push(`multiple_groups+${MULTI_GROUP_BONUS}`);
  }
  if (row.first_seen) {
    const ageMs = Date.now() - new Date(row.first_seen).getTime();
    if (ageMs <= 14 * 24 * 60 * 60 * 1000) {
      total += NEW_ACCOUNT_BONUS;
      factors.push(`new_account+${NEW_ACCOUNT_BONUS}`);
    }
  }
  const score = clamp(total);
  return {
    ...row,
    risk_score: score,
    risk_level: classifyRisk(score),
    risk_factors: factors,
  };
}

export function enrichMessageRisk(
  message: MessageRow,
  keywords: string[],
  categories: string[],
): MessageRow {
  if (message.risk_score != null && message.risk_level) {
    return message;
  }
  const scored = scoreMessageClient(keywords, categories, message.text || "");
  return {
    ...message,
    risk_score: scored.score,
    risk_level: scored.level,
    risk_factors: scored.factors,
  };
}

export function riskSummary(payload: ExportPayload) {
  const levels: Record<RiskLevel, number> = {
    Low: 0,
    Medium: 0,
    High: 0,
    Critical: 0,
  };
  for (const message of payload.messages) {
    const level = (message.risk_level as RiskLevel) || classifyRisk(message.risk_score || 0);
    levels[level] = (levels[level] || 0) + 1;
  }
  const topMessages = payload.messages
    .slice()
    .sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0))
    .slice(0, 10);
  const topChats = payload.chats
    .slice()
    .sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0))
    .slice(0, 10);
  const topPersonnel = (payload.personnel || [])
    .map(enrichPersonnelRisk)
    .sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0))
    .slice(0, 10);
  return { levels, topMessages, topChats, topPersonnel };
}
