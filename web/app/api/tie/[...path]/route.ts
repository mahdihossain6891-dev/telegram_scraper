import { NextRequest, NextResponse } from "next/server";

/**
 * Proxy Threat Console → Threat Intelligence Engine /api/v1/tie/*.
 * Keeps TIE_URL server-side; browser never talks to TIE Mongo directly.
 */
function tieBase(): string {
  return (
    process.env.TIE_API_URL?.replace(/\/$/, "") ||
    process.env.THREAT_INTELLIGENCE_ENGINE_URL?.replace(/\/$/, "") ||
    "http://127.0.0.1:8000"
  );
}

async function proxy(path: string, request: NextRequest, init?: RequestInit) {
  const base = tieBase();
  const qs = request.nextUrl.searchParams.toString();
  const url = `${base}/api/v1/tie/${path}${qs ? `?${qs}` : ""}`;

  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  const apiKey = process.env.TIE_API_KEY || process.env.THREAT_INTELLIGENCE_API_KEY;
  const bearer = process.env.TIE_BEARER_TOKEN;
  if (apiKey) headers["X-API-Key"] = apiKey;
  if (bearer) headers.Authorization = `Bearer ${bearer}`;

  const role = request.headers.get("x-console-role");
  if (role) headers["X-Console-Role"] = role;

  const response = await fetch(url, {
    ...init,
    headers,
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
    return await proxy(path.join("/"), request);
  } catch {
    return NextResponse.json(
      {
        error: "Threat Intelligence Engine Offline",
        message: "Could not reach TIE. Check TIE_API_URL and that the engine is running.",
      },
      { status: 503 },
    );
  }
}

export async function PUT(request: NextRequest, context: Ctx) {
  try {
    const { path } = await context.params;
    const body = await request.text();
    return await proxy(path.join("/"), request, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body,
    });
  } catch {
    return NextResponse.json(
      {
        error: "Threat Intelligence Engine Offline",
        message: "Could not reach TIE. Check TIE_API_URL and that the engine is running.",
      },
      { status: 503 },
    );
  }
}

export async function POST(request: NextRequest, context: Ctx) {
  try {
    const { path } = await context.params;
    const body = await request.text();
    return await proxy(path.join("/"), request, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });
  } catch {
    return NextResponse.json(
      {
        error: "Threat Intelligence Engine Offline",
        message: "Could not reach TIE. Check TIE_API_URL and that the engine is running.",
      },
      { status: 503 },
    );
  }
}
