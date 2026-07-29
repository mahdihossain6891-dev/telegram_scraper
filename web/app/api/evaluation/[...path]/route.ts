import { NextRequest, NextResponse } from "next/server";

async function proxy(path: string, init?: RequestInit) {
  const base = process.env.DASHBOARD_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8510";
  let response: Response;
  try {
    response = await fetch(`${base}/api/evaluation/${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {}),
      },
    });
  } catch (cause) {
    const message = cause instanceof Error ? cause.message : "Backend unreachable";
    return NextResponse.json(
      { error: `Evaluation API offline (${base}): ${message}` },
      { status: 503 },
    );
  }
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
    return NextResponse.json({ error: "Evaluation API unavailable." }, { status: 503 });
  }
}

export async function POST(request: NextRequest, context: Ctx) {
  try {
    const { path } = await context.params;
    const suffix = path.join("/");
    const body = await request.text();
    return await proxy(suffix, { method: "POST", body: body || undefined });
  } catch {
    return NextResponse.json({ error: "Evaluation API unavailable." }, { status: 503 });
  }
}
