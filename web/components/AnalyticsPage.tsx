"use client";

import { useMemo } from "react";

import { EChart } from "@/components/EChart";
import {
  areaTimelineOption,
  donutSeverityOption,
  heatmapOption,
  horizontalKeywordsOption,
  peakActivityHeatmap,
  stackedCategoryBySourceOption,
} from "@/lib/charts";
import {
  categoryBySourceType,
  multiCategoryMessages,
  timelineFromMessages,
  topKeywordTerms,
} from "@/lib/dashboard-data";
import { riskSummary } from "@/lib/risk";
import type {
  EntityDisplayRow,
  ExportPayload,
  MessageDisplayRow,
} from "@/lib/types";

type AnalyticsPageProps = {
  payload: ExportPayload;
  filteredMessages: MessageDisplayRow[];
  filteredEntities: EntityDisplayRow[];
};

export function AnalyticsPage({
  payload,
  filteredMessages,
  filteredEntities,
}: AnalyticsPageProps) {
  const timeline = useMemo(() => timelineFromMessages(filteredMessages), [filteredMessages]);
  const heatmap = useMemo(() => peakActivityHeatmap(filteredMessages), [filteredMessages]);
  const bySource = useMemo(() => categoryBySourceType(filteredMessages), [filteredMessages]);
  const keywords = useMemo(() => topKeywordTerms(filteredEntities, 12), [filteredEntities]);
  const severity = useMemo(() => riskSummary(payload).levels, [payload]);
  const multi = useMemo(() => multiCategoryMessages(filteredMessages, 20), [filteredMessages]);

  return (
    <>
      <div className="page-header">
        <h1>Analytics</h1>
        <p>
          One chart per question — volume, timing, source mix, keywords, and severity. No duplicate
          dashboard views.
        </p>
      </div>

      <div className="analytics-grid charts">
        <section className="panel card">
          <div className="panel-head">
            <h2>Is activity rising?</h2>
            <span className="caption">Flagged volume over time</span>
          </div>
          {timeline.length ? (
            <EChart option={areaTimelineOption(timeline)} height={280} ariaLabel="Volume over time" />
          ) : (
            <div className="empty-state">No time series in scope.</div>
          )}
        </section>

        <section className="panel card">
          <div className="panel-head">
            <h2>When do they operate?</h2>
            <span className="caption">Day × hour heatmap</span>
          </div>
          <EChart option={heatmapOption(heatmap)} height={280} ariaLabel="Operating hours heatmap" />
        </section>

        <section className="panel card">
          <div className="panel-head">
            <h2>Category by source type</h2>
            <span className="caption">Channel / group / DM mix</span>
          </div>
          {bySource.length ? (
            <EChart
              option={stackedCategoryBySourceOption(bySource)}
              height={280}
              ariaLabel="Category by source type"
            />
          ) : (
            <div className="empty-state">No category×source data.</div>
          )}
        </section>

        <section className="panel card">
          <div className="panel-head">
            <h2>Which terms dominate?</h2>
            <span className="caption">Top keyword Pareto</span>
          </div>
          {keywords.length ? (
            <EChart
              option={horizontalKeywordsOption(keywords)}
              height={280}
              ariaLabel="Top keywords"
            />
          ) : (
            <div className="empty-state">No keyword terms in scope.</div>
          )}
        </section>
      </div>

      <div className="two-col">
        <section className="panel card">
          <div className="panel-head">
            <h2>How hot is the caseload?</h2>
            <span className="caption">Severity bands</span>
          </div>
          <EChart
            option={donutSeverityOption(severity)}
            height={260}
            ariaLabel="Severity donut"
          />
        </section>
        <section className="panel card">
          <div className="panel-head">
            <h2>Highest-confidence hits</h2>
            <span className="caption">Multi-category messages</span>
          </div>
          {!multi.length ? (
            <div className="empty-state">No multi-category messages in scope.</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Source</th>
                    <th>Categories</th>
                    <th>Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {multi.map((row) => (
                    <tr key={`${row.chat_id}-${row.message_id}`}>
                      <td className="mono">{row.timestamp.slice(0, 16).replace("T", " ")}</td>
                      <td>{row.chat}</td>
                      <td>{row.categories}</td>
                      <td>
                        <span
                          className={`risk-badge risk-${String(row.risk_level || "Low").toLowerCase()}`}
                        >
                          {row.risk_level} · {row.risk_score}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
