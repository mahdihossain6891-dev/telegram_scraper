"use client";

import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { DataModeProvider } from "@/components/mode/DataModeProvider";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <DataModeProvider>{children}</DataModeProvider>
    </ThemeProvider>
  );
}
