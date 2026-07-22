import { NextResponse } from "next/server";

const API_BASE = process.env.DASHBOARD_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8510";

export async function POST() {
  try {
    const res = await fetch(`${API_BASE}/api/mode/end`, { method: "POST", cache: "no-store" });
    const body = await res.json();
    return NextResponse.json(body, { status: res.status });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to end simulation" },
      { status: 502 },
    );
  }
}
