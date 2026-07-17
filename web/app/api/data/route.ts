import { readFile } from "fs/promises";
import path from "path";
import { NextResponse } from "next/server";

import type { ExportPayload } from "@/lib/types";

async function readExport(relativePath: string): Promise<ExportPayload | null> {
  try {
    const filePath = path.join(process.cwd(), relativePath);
    const raw = await readFile(filePath, "utf-8");
    return JSON.parse(raw) as ExportPayload;
  } catch {
    return null;
  }
}

export async function GET() {
  const exportUrl = process.env.EXPORT_JSON_URL;
  if (exportUrl) {
    try {
      const response = await fetch(exportUrl, { cache: "no-store" });
      if (response.ok) {
        const payload = (await response.json()) as ExportPayload;
        return NextResponse.json({ source: "remote", payload });
      }
    } catch {
      // Fall through to local files.
    }
  }

  const live = await readExport("public/data/export.json");
  if (live) {
    return NextResponse.json({ source: "local", payload: live });
  }

  const sample = await readExport("public/data/export.sample.json");
  if (sample) {
    return NextResponse.json({ source: "sample", payload: sample });
  }

  return NextResponse.json(
    { error: "No export data found. Run export.bat and copy export.json to web/public/data/." },
    { status: 404 },
  );
}
