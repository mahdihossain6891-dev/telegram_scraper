import type { Metadata } from "next";

import { SettingsApp } from "@/components/settings/SettingsApp";

export const metadata: Metadata = {
  title: "Settings · Threat Console",
  description: "Telegram API and AI provider configuration for Threat Console",
};

export default function SettingsPage() {
  return <SettingsApp />;
}
