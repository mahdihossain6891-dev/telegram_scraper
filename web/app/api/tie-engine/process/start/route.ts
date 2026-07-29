import { NextResponse } from "next/server";

const API_BASE = process.env.DASHBOARD_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8510";

export async function POST() {
  try {
    const res = await fetch(`${API_BASE}/api/tie-engine/process/start`, {
      method: "POST",
      cache: "no-store",
    });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
    });
  } catch {
    return NextResponse.json(
      { ok: false, error: "Dashboard API unavailable. Start dashboard.bat." },
      { status: 503 },
    );
  }
}
