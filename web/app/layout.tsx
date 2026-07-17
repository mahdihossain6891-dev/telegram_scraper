import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Telegram Intelligence Dashboard",
  description: "Read-only OSINT dashboard deployed on Vercel",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
