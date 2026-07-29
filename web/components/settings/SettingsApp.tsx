"use client";

import Link from "next/link";

import { ConsoleJumpNav } from "@/components/layout/ConsoleJumpNav";
import { EnvSettingsPanel } from "@/components/settings/EnvSettingsPanel";

export function SettingsApp() {
  return (
    <div className="settings-shell">
      <ConsoleJumpNav active="settings" className="settings-sidebar" />

      <main className="settings-main">
        <header className="settings-header page-header">
          <div>
            <p className="eyebrow">Configuration</p>
            <h1>Settings</h1>
            <p>
              Dark mode, Telegram API credentials, and your OpenRouter key for AI support. Each
              operator uses their own keys on this machine.
            </p>
          </div>
          <Link href="/" className="btn ghost">
            ← Threat Console
          </Link>
        </header>

        <section className="panel card settings-panel-wide" aria-label="Settings">
          <EnvSettingsPanel layout="page" />
        </section>
      </main>
    </div>
  );
}
