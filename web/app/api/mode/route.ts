import { NextResponse } from "next/server";

const API_BASE = process.env.DASHBOARD_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8510";

export async function GET() {
  try {
    const res = await fetch(`${API_BASE}/api/mode`, { cache: "no-store" });
    const body = await res.json();
    return NextResponse.json(body, { status: res.status });
  } catch {
    return NextResponse.json(
      {
        mode: "live",
        simulation_active: false,
        scenario: null,
        session_id: null,
        session_name: null,
      },
      { status: 200 },
    );
  }
}

export async function PUT(request: Request) {
  try {
    const payload = await request.json();
    const res = await fetch(`${API_BASE}/api/mode`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
    const body = await res.json();
    return NextResponse.json(body, { status: res.status });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Mode update failed" },
      { status: 502 },
    );
  }
}
