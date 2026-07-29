import { NextResponse } from "next/server";

const API_BASE = process.env.DASHBOARD_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8510";

export async function GET() {
  try {
    const res = await fetch(`${API_BASE}/api/tie-engine/process`, { cache: "no-store" });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
    });
  } catch {
    return NextResponse.json(
      { running: false, healthy: false, error: "Dashboard API unavailable" },
      { status: 503 },
    );
  }
}
