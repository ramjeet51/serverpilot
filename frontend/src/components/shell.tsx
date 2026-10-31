"use client";

import { Activity, ClipboardList, Cog, LayoutDashboard, LogOut, Menu, Package, ScrollText, Server, Shield, Users, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { env } from "@/lib/env";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/servers", label: "Servers", icon: Server, permission: "servers:read" },
  { href: "/software", label: "Software", icon: Package, permission: "software:read" },
  { href: "/services", label: "Services", icon: Cog, permission: "services:read" },
  { href: "/jobs", label: "Jobs", icon: ClipboardList, permission: "jobs:read" },
  { href: "/audit", label: "Audit", icon: ScrollText, permission: "audit:read" },
  { href: "/accounts", label: "Accounts", icon: Users, permission: "accounts:read" },
  { href: "/account", label: "Security", icon: Shield },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout, can } = useAuth();
  const [open, setOpen] = useState(false);
  const items = NAV.filter((item) => !item.permission || can(item.permission));

  async function signOut() {
    await logout();
    router.replace("/login");
  }

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 px-4 py-5">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-accent text-sm font-semibold text-accent-foreground">SP</span>
        <div>
          <p className="font-display text-lg leading-none">{env.appName}</p>
          <p className="mt-1 text-xs text-muted-foreground">Control plane</p>
        </div>
      </div>
      <nav className="flex-1 space-y-1 px-3">
        {items.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm",
                active ? "bg-accent/15 text-accent" : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-border p-4">
        <p className="truncate text-sm font-medium">{user?.full_name || user?.email}</p>
        <p className="truncate text-xs text-muted-foreground">{user?.roles.join(", ")}</p>
        <Button variant="ghost" className="mt-3 w-full justify-start px-2" onClick={signOut}>
          <LogOut className="h-4 w-4" /> Sign out
        </Button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen md:grid md:grid-cols-[16rem_1fr]">
      <aside className="hidden border-r border-border bg-card/70 md:block">{sidebar}</aside>
      {open && (
        <div className="fixed inset-0 z-30 md:hidden">
          <button className="absolute inset-0 bg-black/60" aria-label="Close menu" onClick={() => setOpen(false)} />
          <aside className="relative z-10 h-full w-72 bg-card">{sidebar}</aside>
        </div>
      )}
      <div className="min-w-0">
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-border bg-background/80 px-4 py-3 backdrop-blur md:px-8">
          <button className="rounded-lg p-2 hover:bg-muted md:hidden" onClick={() => setOpen((v) => !v)} aria-label="Menu">
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
          <div className="hidden items-center gap-2 text-sm text-muted-foreground md:flex">
            <Activity className="h-4 w-4 text-signal" /> Management server
          </div>
          <p className="truncate text-sm text-muted-foreground md:hidden">{env.appName}</p>
          <span className="text-xs uppercase tracking-wide text-muted-foreground">Phase 1</span>
        </header>
        <main className="px-4 py-6 md:px-8 md:py-8">{children}</main>
      </div>
    </div>
  );
}
