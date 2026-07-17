"use client";

import { useEffect, useMemo, useState } from "react";

import { buildDashboardStats, type DashboardStats } from "@/lib/analytics";
import type { ExportPayload } from "@/lib/types";

type ApiResponse = {
  source: string;
  payload: ExportPayload;
};

export default function HomePage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [source, setSource] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [query, setQuery] = useState<string>("");

  useEffect(() => {
    async function loadData() {
      try {
        const response = await fetch("/api/data");
        const body = await response.json();
        if (!response.ok) {
          setError(body.error || "Failed to load export data.");
          return;
        }
        const parsed = body as ApiResponse;
        setSource(parsed.source);
        setStats(buildDashboardStats(parsed.payload));
      } catch {
        setError("Could not load dashboard data.");
      }
    }

    loadData();
  }, []);

  const filteredMessages = useMemo(() => {
    if (!stats) {
      return [];
    }
    const cleaned = query.trim().toLowerCase();
    if (!cleaned) {
      return stats.messages.slice(0, 100);
    }
    return stats.messages
      .filter((message) => (message.text || "").toLowerCase().includes(cleaned))
      .slice(0, 100);
  }, [query, stats]);

  if (error) {
    return (
      <main>
        <div className="hero">
          <h1>Telegram Intelligence Dashboard</h1>
        </div>
        <div className="error">{error}</div>
      </main>
    );
  }

  if (!stats) {
    return (
      <main>
        <div className="hero">
          <h1>Telegram Intelligence Dashboard</h1>
          <p>Loading export data...</p>
        </div>
      </main>
    );
  }

  return (
    <main>
      <div className="hero">
        <h1>Telegram Intelligence Dashboard</h1>
        <p>
          Vercel read-only view · data source: <strong>{source}</strong> · exported{" "}
          {new Date(stats.exportedAt).toLocaleString()}
        </p>
      </div>

      {source === "sample" ? (
        <div className="notice">
          Showing sample data. Export locally with <code>export.bat</code>, copy to{" "}
          <code>web/public/data/export.json</code>, then redeploy on Vercel.
        </div>
      ) : null}

      <div className="grid">
        <div className="card">
          <div className="metric-label">Flagged messages</div>
          <div className="metric-value">{stats.totalMessages}</div>
        </div>
        <div className="card">
          <div className="metric-label">Flagged chats</div>
          <div className="metric-value">{stats.flaggedChats}</div>
        </div>
        <div className="card">
          <div className="metric-label">Keyword flags</div>
          <div className="metric-value">{stats.keywordFlags}</div>
        </div>
        <div className="card">
          <div className="metric-label">Categories</div>
          <div className="metric-value">{Object.keys(stats.categoryCounts).length}</div>
        </div>
      </div>

      <section className="panel card">
        <h2>Chats</h2>
        <table>
          <thead>
            <tr>
              <th>Chat</th>
              <th>Type</th>
              <th>Messages</th>
              <th>Narcotics</th>
              <th>Trafficking</th>
              <th>Firearms</th>
            </tr>
          </thead>
          <tbody>
            {stats.chatSummaries.map((chat) => (
              <tr key={chat.chatId}>
                <td>{chat.title}</td>
                <td>{chat.chatType}</td>
                <td>{chat.messageCount}</td>
                <td>{chat.narcotics}</td>
                <td>{chat.humanTrafficking}</td>
                <td>{chat.firearms}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel card">
        <h2>Search messages</h2>
        <input
          type="search"
          placeholder="Search flagged message text..."
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <table>
          <thead>
            <tr>
              <th>Chat</th>
              <th>Time</th>
              <th>Keywords</th>
              <th>Text</th>
            </tr>
          </thead>
          <tbody>
            {filteredMessages.map((message) => (
              <tr key={message.id}>
                <td>{message.chatTitle}</td>
                <td>{message.timestamp || ""}</td>
                <td>
                  {message.keywords.map((keyword) => (
                    <span className="badge" key={`${message.id}-${keyword}`}>
                      {keyword}
                    </span>
                  ))}
                </td>
                <td>{message.text || ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
