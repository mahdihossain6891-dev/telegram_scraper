"use client";

import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { DataModeProvider } from "@/components/mode/DataModeProvider";
import { TieEngineProvider } from "@/components/mode/TieEngineProvider";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <DataModeProvider>
        <TieEngineProvider>{children}</TieEngineProvider>
      </DataModeProvider>
    </ThemeProvider>
  );
}
