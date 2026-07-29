import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.DASHBOARD_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8510";

export async function GET() {
  try {
    const res = await fetch(`${API_BASE}/api/tie-engine`, { cache: "no-store" });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
    });
  } catch {
    return NextResponse.json(
      {
        enabled: false,
        analyser: "console_builtin",
        description: "Threat Console built-in scrape analyser",
        error: "Dashboard API unavailable",
      },
      { status: 200 },
    );
  }
}

export async function PUT(request: NextRequest) {
  try {
    const body = await request.text();
    const res = await fetch(`${API_BASE}/api/tie-engine`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body,
      cache: "no-store",
    });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("Content-Type") || "application/json" },
    });
  } catch {
    return NextResponse.json(
      { error: "Dashboard API unavailable. Start dashboard.bat." },
      { status: 503 },
    );
  }
}
