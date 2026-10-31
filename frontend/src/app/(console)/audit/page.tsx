"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { AuditEntry } from "@/lib/types";
import { formatWhen } from "@/lib/utils";

export default function AuditPage() {
  const [outcome, setOutcome] = useState<"" | "success" | "failure">("");
  const query = useQuery({
    queryKey: ["audit", outcome],
    queryFn: () => api<AuditEntry[]>(`/api/v1/audit${outcome ? `?outcome=${outcome}` : ""}`),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl sm:text-4xl">Audit log</h1>
        <p className="mt-1 text-sm text-muted-foreground">Sign-ins, account changes, and job actions are recorded with the client address.</p>
      </div>
      <div className="flex gap-2">
        {(["", "success", "failure"] as const).map((item) => (
          <button key={item || "all"} onClick={() => setOutcome(item)} className={`rounded-full px-3 py-1 text-xs capitalize ${outcome === item ? "bg-accent text-accent-foreground" : "bg-muted text-muted-foreground"}`}>
            {item || "all"}
          </button>
        ))}
      </div>
      <div className="panel overflow-x-auto">
        {query.isLoading && <p className="p-5 text-sm text-muted-foreground">Loading audit events…</p>}
        {query.isError && <p className="p-5 text-sm text-danger">You need the audit:read permission to view this log.</p>}
        <table className="w-full min-w-[40rem] text-left text-sm">
          <tbody>
            {(query.data ?? []).map((entry) => (
              <tr key={entry.id} className="border-t border-border">
                <td className="px-5 py-3 text-muted-foreground">{formatWhen(entry.created_at)}</td>
                <td className="px-3 py-3">{entry.action}</td>
                <td className="px-3 py-3">{entry.actor_label ?? "—"}</td>
                <td className="px-3 py-3"><Badge value={entry.outcome} /></td>
                <td className="px-5 py-3 text-muted-foreground">{entry.ip_address ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {query.data?.length === 0 && <p className="p-5 text-sm text-muted-foreground">No matching events.</p>}
      </div>
    </div>
  );
}
