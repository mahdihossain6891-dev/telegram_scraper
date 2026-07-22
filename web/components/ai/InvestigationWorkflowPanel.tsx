"use client";

import { useMemo, useState } from "react";

export type WorkflowToolRun = {
  tool?: string;
  name?: string;
  ok?: boolean;
  latency_ms?: number;
  summary?: string;
  error?: string | null;
  cached?: boolean;
  confidence?: number | null;
  freshness?: number | null;
  completeness?: number | null;
  impact?: string;
  data_preview?: Record<string, unknown>;
};

export type InvestigationWorkflow = {
  user_query?: string;
  detected_intent?: string;
  intent_label?: string;
  plan?: {
    required_tools?: string[];
    optional_tools?: string[];
    estimated_ms?: number;
    estimated_evidence_count?: number;
    steps?: Array<{ tool: string; priority?: string; reason?: string }>;
  };
  tools_executed?: WorkflowToolRun[];
  evidence_count?: number;
  context_chars?: number;
  prompt_chars?: number;
  model_used?: string;
  response_generated?: boolean;
  planning_ms?: number;
  total_tool_ms?: number;
  explain_ms?: number;
  total_ms?: number;
  validation?: { ok?: boolean; warnings?: string[]; issues?: string[] };
  stages?: string[];
};

type Props = {
  workflow?: InvestigationWorkflow | null;
  observability?: Record<string, unknown> | null;
};

function Stage({ label, done }: { label: string; done: boolean }) {
  return (
    <li className={`ai-wf-stage${done ? " done" : ""}`}>
      <span aria-hidden="true">{done ? "✓" : "○"}</span>
      <span>{label}</span>
    </li>
  );
}

export function InvestigationWorkflowPanel({ workflow, observability }: Props) {
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const tools = workflow?.tools_executed || [];
  const stages = useMemo(() => {
    const s = new Set(workflow?.stages || []);
    return [
      { id: "user_query", label: "User Query", done: s.has("user_query") || Boolean(workflow?.user_query) },
      {
        id: "detected_intent",
        label: `Detected Intent${workflow?.intent_label ? `: ${workflow.intent_label}` : ""}`,
        done: s.has("detected_intent") || Boolean(workflow?.detected_intent),
      },
      { id: "execution_plan", label: "Execution Plan", done: s.has("execution_plan") || Boolean(workflow?.plan) },
      { id: "tools_executed", label: "Tools Executed", done: s.has("tools_executed") || tools.length > 0 },
      {
        id: "evidence_retrieved",
        label: `Evidence Retrieved (${workflow?.evidence_count ?? "—"})`,
        done: s.has("evidence_retrieved") || (workflow?.evidence_count ?? 0) > 0,
      },
      { id: "context_built", label: "Context Built", done: s.has("context_built") },
      {
        id: "model_used",
        label: `Model Used${workflow?.model_used ? `: ${workflow.model_used}` : ""}`,
        done: s.has("model_used") || Boolean(workflow?.model_used),
      },
      {
        id: "response_generated",
        label: "Response Generated",
        done: s.has("response_generated") || Boolean(workflow?.response_generated),
      },
    ];
  }, [workflow, tools.length]);

  if (!workflow && !observability) return null;

  return (
    <section className="ai-wf-panel" aria-label="Investigation Workflow">
      <button
        type="button"
        className="ai-wf-toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span>Investigation Workflow</span>
        <span className="caption">{open ? "Hide" : "Show"}</span>
      </button>

      {open ? (
        <div className="ai-wf-body">
          <div className="ai-wf-query">
            <span className="caption">User query</span>
            <p>{workflow?.user_query || "—"}</p>
          </div>

          <ol className="ai-wf-stages">
            {stages.map((st) => (
              <Stage key={st.id} label={st.label} done={st.done} />
            ))}
          </ol>

          {workflow?.plan ? (
            <div className="ai-wf-plan">
              <h4>Execution plan</h4>
              <p className="caption">
                Est. {workflow.plan.estimated_ms ?? "—"} ms · ~
                {workflow.plan.estimated_evidence_count ?? "—"} evidence items
              </p>
              <ul>
                {(workflow.plan.steps || []).map((step) => (
                  <li key={`${step.tool}-${step.priority}`}>
                    <strong>{step.tool}</strong>
                    {step.priority === "optional" ? " (optional)" : ""}
                    {step.reason ? <span className="caption"> — {step.reason}</span> : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="ai-wf-tools">
            <h4>Tool execution</h4>
            {tools.length === 0 ? (
              <p className="caption">No tools executed for this turn.</p>
            ) : (
              <ul className="ai-wf-tool-list">
                {tools.map((t) => {
                  const name = t.tool || t.name || "tool";
                  const key = `${name}-${t.latency_ms}`;
                  const isOpen = Boolean(expanded[key]);
                  return (
                    <li key={key} className={t.ok ? "ok" : "fail"}>
                      <button
                        type="button"
                        className="ai-wf-tool-row"
                        onClick={() =>
                          setExpanded((prev) => ({ ...prev, [key]: !prev[key] }))
                        }
                      >
                        <span>
                          {t.ok ? "✓" : "✕"} {name}
                          {t.cached ? " (cached)" : ""}
                        </span>
                        <span className="caption">
                          {typeof t.latency_ms === "number" ? `${t.latency_ms} ms` : "—"}
                        </span>
                      </button>
                      {isOpen ? (
                        <div className="ai-wf-tool-detail">
                          <p>{t.summary || "No summary"}</p>
                          {t.error ? <p className="ai-cc-error">{t.error}</p> : null}
                          {t.impact ? <p className="caption">{t.impact}</p> : null}
                          {t.confidence != null ? (
                            <p className="caption">
                              Confidence {t.confidence}
                              {t.freshness != null ? ` · Freshness ${t.freshness}` : ""}
                              {t.completeness != null
                                ? ` · Completeness ${t.completeness}`
                                : ""}
                            </p>
                          ) : null}
                        </div>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {observability ? (
            <div className="ai-wf-obs caption">
              Planning {String(observability.planning_ms ?? "—")} ms · Tools{" "}
              {String(observability.tool_latency_ms ?? "—")} ms · Total{" "}
              {String(observability.response_time_ms ?? workflow?.total_ms ?? "—")} ms ·
              Context {String(observability.context_size ?? workflow?.context_chars ?? "—")}{" "}
              chars
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
