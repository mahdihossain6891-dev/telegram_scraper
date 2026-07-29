import { NextRequest, NextResponse } from "next/server";

/**
 * Proxy for isolated Behavioral Analytics FastAPI routes.
 * Does not share handlers with the main /api/data export pipeline.
 */
async function proxy(path: string, init?: RequestInit) {
  const base = process.env.DASHBOARD_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8510";
  const response = await fetch(`${base}/api/behavioral/${path}`, {
    ...init,
    cache: "no-store",
  });
  const text = await response.text();
  return new NextResponse(text, {
    status: response.status,
    headers: { "Content-Type": response.headers.get("Content-Type") || "application/json" },
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
      { error: "Behavioral Analytics API unavailable. Start dashboard.bat." },
      { status: 503 },
    );
  }
}

export async function POST(_request: NextRequest, context: Ctx) {
  try {
    const { path } = await context.params;
    const suffix = path.join("/");
    return await proxy(suffix, { method: "POST" });
  } catch {
    return NextResponse.json(
      { error: "Behavioral Analytics API unavailable. Start dashboard.bat." },
      { status: 503 },
    );
  }
}
