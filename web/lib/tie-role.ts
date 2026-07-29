/** Roles for Threat Intelligence (TIE ops) page visibility. */
export type TieConsoleRole =
  | "viewer"
  | "analyst"
  | "senior_analyst"
  | "administrator";

const STORAGE_KEY = "tc.tie.role";

export function canViewTieOpsDetail(role: TieConsoleRole): boolean {
  return role === "administrator" || role === "senior_analyst";
}

/** Change TIE AI provider/model — Senior Analyst / Administrator. */
export function canConfigureTieAi(role: TieConsoleRole): boolean {
  return canViewTieOpsDetail(role);
}

export function normalizeTieRole(raw: string | null | undefined): TieConsoleRole {
  const v = (raw || "").trim().toLowerCase().replace(/\s+/g, "_");
  if (v === "administrator" || v === "admin") return "administrator";
  if (v === "senior_analyst" || v === "senior") return "senior_analyst";
  if (v === "analyst") return "analyst";
  if (v === "viewer") return "viewer";
  return "viewer";
}

/**
 * Resolve Console role for TIE page gating.
 * Priority: localStorage → NEXT_PUBLIC_TIE_ROLE → viewer (safe default).
 */
export function getTieConsoleRole(): TieConsoleRole {
  if (typeof window !== "undefined") {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored) return normalizeTieRole(stored);
    } catch {
      /* ignore */
    }
  }
  return normalizeTieRole(
    typeof process !== "undefined"
      ? process.env.NEXT_PUBLIC_TIE_ROLE || "administrator"
      : "administrator",
  );
}

export function setTieConsoleRole(role: TieConsoleRole): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, role);
  } catch {
    /* ignore */
  }
}
