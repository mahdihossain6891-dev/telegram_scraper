import type { Metadata } from "next";

import { AiCopilotApp } from "@/components/ai/AiCopilotApp";

export const metadata: Metadata = {
  title: "Sébastien · AI Investigation Copilot",
  description:
    "Sébastien — AI-powered cyber investigation assistant for evidence-grounded analysis",
};

/**
 * Isolated Sébastien investigation workspace.
 * Does not mount DashboardApp or share page state with the Threat Console SPA.
 */
export default function AiCopilotPage() {
  return <AiCopilotApp />;
}
