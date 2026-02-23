"use client";

import { LocaleProvider } from "@/contexts/LocaleContext";

export function Providers({ children }: { children: React.ReactNode }) {
  return <LocaleProvider>{children}</LocaleProvider>;
}
