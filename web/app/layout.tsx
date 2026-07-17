import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Telegram Intelligence Scraper",
  description: "Read-only OSINT dashboard matching the Streamlit export view",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
