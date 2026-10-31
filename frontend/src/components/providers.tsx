"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { Toaster } from "sonner";

import { AuthProvider } from "@/lib/auth";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient({
    defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 10_000 } },
  }));
  return (
    <QueryClientProvider client={client}>
      <AuthProvider>
        {children}
        <Toaster theme="dark" position="top-right" />
      </AuthProvider>
    </QueryClientProvider>
  );
}
