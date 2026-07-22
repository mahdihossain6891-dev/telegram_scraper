import { NextRequest, NextResponse } from "next/server";

/**
 * Proxy for isolated AI FastAPI routes under /api/ai/*.
 * Does not share handlers with /api/data or behavioral proxies.
 */
async function proxy(path: string, init?: RequestInit) {
  const base = process.env.DASHBOARD_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8510";
  const response = await fetch(`${base}/api/ai/${path}`, {
    ...init,
    cache: "no-store",
  });
  const text = await response.text();
  return new NextResponse(text, {
    status: response.status,
    headers: {
      "Content-Type": response.headers.get("Content-Type") || "application/json",
    },
  });
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, context: Ctx) {
  try {
    const { path } = await context.params;
    const suffix = path.join("/");
    const qs = request.nextUrl.searchParams.toString();
    return await proxy(qs ? `${suffix}?${qs}` : suffix);
  } catch {
    return NextResponse.json(
      { error: "AI API unavailable. Start the FastAPI server (dashboard.bat)." },
      { status: 503 },
    );
  }
}

export async function POST(request: NextRequest, context: Ctx) {
  try {
    const { path } = await context.params;
    const suffix = path.join("/");
    const body = await request.text();
    return await proxy(suffix, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });
  } catch {
    return NextResponse.json(
      { error: "AI API unavailable. Start the FastAPI server (dashboard.bat)." },
      { status: 503 },
    );
  }
}
