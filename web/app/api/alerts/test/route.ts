import { NextResponse } from "next/server";

export async function POST() {
  const base = process.env.DASHBOARD_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8510";
  try {
    const response = await fetch(`${base}/api/alerts/test`, {
      method: "POST",
      cache: "no-store",
    });
    const text = await response.text();
    return new NextResponse(text, {
      status: response.status,
      headers: { "Content-Type": response.headers.get("Content-Type") || "application/json" },
    });
  } catch {
    return NextResponse.json(
      { error: "FastAPI unavailable. Start dashboard.bat." },
      { status: 503 },
    );
  }
}
