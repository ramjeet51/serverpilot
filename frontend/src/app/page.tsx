"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/lib/auth";

export default function HomePage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!loading) router.replace(user ? "/dashboard" : "/login");
  }, [loading, user, router]);
  return <p className="p-8 text-sm text-muted-foreground">Opening {user ? "dashboard" : "sign in"}…</p>;
}
