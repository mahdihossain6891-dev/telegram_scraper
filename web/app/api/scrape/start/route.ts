import { NextResponse } from "next/server";

async function proxy(path: string, init?: RequestInit) {
  const base = process.env.DASHBOARD_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8510";
  const response = await fetch(`${base}${path}`, {
    ...init,
    cache: "no-store",
  });
  const text = await response.text();
  return new NextResponse(text, {
    status: response.status,
    headers: { "Content-Type": response.headers.get("Content-Type") || "application/json" },
  });
}

export async function POST(request: Request) {
  try {
    const body = await request.text();
    return await proxy("/api/scrape/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body || "{}",
    });
  } catch {
    return NextResponse.json(
      { error: "FastAPI unavailable. Start dashboard.bat." },
      { status: 503 },
    );
  }
}
