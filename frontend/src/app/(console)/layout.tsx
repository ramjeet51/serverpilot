"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Shell } from "@/components/shell";
import { useAuth } from "@/lib/auth";

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) {
    return <p className="p-8 text-sm text-muted-foreground">Checking session…</p>;
  }
  return <Shell>{children}</Shell>;
}
