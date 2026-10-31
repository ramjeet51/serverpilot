"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { JobProgress } from "@/components/job-progress";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { explainJournal, type JournalTone } from "@/lib/journal";
import type { Job } from "@/lib/types";

type ServerCard = { id: string; name: string; status: string };
type ServiceRow = { unit: string; description: string; active: string; sub: string; enabled: string; suggested: boolean };
type ServiceDetail = { unit: string; description: string; active: string; sub: string; enabled: string; fragment_path: string; main_pid: string };
type ServiceAction = "restart" | "enable" | "disable";
type LogFilter = "all" | JournalTone;

const ACTIONS: ServiceAction[] = ["restart", "enable", "disable"];

export default function ServicesPage() {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const [serverId, setServerId] = useState("");
  const [search, setSearch] = useState("");
  const [suggestedOnly, setSuggestedOnly] = useState(true);
  const [selectedUnit, setSelectedUnit] = useState<string | null>(null);
  const [follow, setFollow] = useState(true);
  const [logFilter, setLogFilter] = useState<LogFilter>("all");
  const [jobId, setJobId] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<ServiceAction | null>(null);

  const servers = useQuery({ queryKey: ["servers"], queryFn: () => api<ServerCard[]>("/api/v1/servers") });
  const selected = serverId || servers.data?.[0]?.id || "";
  const services = useQuery({
    queryKey: ["services", selected, search],
    queryFn: () => api<ServiceRow[]>(`/api/v1/services?server_id=${selected}&q=${encodeURIComponent(search)}`),
    enabled: Boolean(selected),
  });
  const detail = useQuery({
    queryKey: ["service", selected, selectedUnit],
    queryFn: () => api<ServiceDetail>("/api/v1/services/show", {
      method: "POST", body: JSON.stringify({ server_id: selected, unit: selectedUnit }),
    }),
    enabled: Boolean(selected && selectedUnit),
  });
  const logs = useQuery({
    queryKey: ["service-logs", selected, selectedUnit],
    queryFn: () => api<{ lines: string[] }>("/api/v1/services/logs", {
      method: "POST", body: JSON.stringify({ server_id: selected, unit: selectedUnit }),
    }),
    enabled: Boolean(selected && selectedUnit),
    refetchInterval: follow && selectedUnit ? 3000 : false,
  });

  const refresh = useMutation({
    mutationFn: () => api("/api/v1/services/refresh", { method: "POST", body: JSON.stringify({ server_id: selected }) }),
    onSuccess: () => {
      toast.success("Service list updated");
      void queryClient.invalidateQueries({ queryKey: ["services", selected] });
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Could not list services"),
  });
  const operate = useMutation({
    mutationFn: (action: ServiceAction) => api<Job>("/api/v1/services/operations", {
      method: "POST",
      body: JSON.stringify({ server_id: selected, unit: selectedUnit, action, confirm: true }),
    }),
    onSuccess: (job) => {
      setJobId(job.id);
      setConfirm(null);
      toast.success("Service action queued");
      void queryClient.invalidateQueries({ queryKey: ["service", selected, selectedUnit] });
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Service action failed"),
  });

  const rows = (services.data ?? []).filter((row) => !suggestedOnly || row.suggested || search.trim().length > 0);
  const entries = (logs.data?.lines ?? []).map(explainJournal).reverse();
  const visible = entries.filter((entry) => logFilter === "all" || entry.tone === logFilter);
  const counts = {
    error: entries.filter((entry) => entry.tone === "error").length,
    working: entries.filter((entry) => entry.tone === "working").length,
    success: entries.filter((entry) => entry.tone === "success").length,
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-display text-3xl sm:text-4xl">Services</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            systemd units discovered on the server. You can restart a service, or enable and disable it at boot. Stop and delete are not available.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select className="h-10 rounded-lg border border-border bg-background/60 px-3 text-sm" value={selected} onChange={(event) => { setServerId(event.target.value); setSelectedUnit(null); }}>
            {(servers.data ?? []).map((server) => <option key={server.id} value={server.id}>{server.name}</option>)}
          </select>
          <Button variant="outline" disabled={!selected || refresh.isPending} onClick={() => refresh.mutate()}>
            {refresh.isPending ? "Discovering…" : "Discover services"}
          </Button>
        </div>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search units" />
        <Button variant="outline" onClick={() => setSuggestedOnly((value) => !value)}>{suggestedOnly ? "Showing common" : "Showing all"}</Button>
      </div>
      {jobId && <JobProgress jobId={jobId} />}
      <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="panel overflow-hidden">
          <ul className="divide-y divide-border">
            {rows.map((row) => (
              <li key={row.unit}>
                <button className="flex w-full flex-col gap-1 px-4 py-3 text-left hover:bg-muted/60 sm:flex-row sm:items-center sm:justify-between" onClick={() => setSelectedUnit(row.unit)}>
                  <span>
                    <span className="block text-sm">{row.unit}</span>
                    <span className="block text-xs text-muted-foreground">{row.description || "No description"}</span>
                  </span>
                  <span className="flex gap-2">
                    <Badge value={row.active} />
                    <Badge value={row.enabled === "enabled" ? "enabled" : "disabled"} label={row.enabled} />
                  </span>
                </button>
              </li>
            ))}
            {rows.length === 0 && <li className="p-4 text-sm text-muted-foreground">No services yet. Discover services on the selected server.</li>}
          </ul>
        </div>
        <section className="panel space-y-3 p-4">
          {!selectedUnit && <p className="text-sm text-muted-foreground">Select a service to see its unit file, status and journal.</p>}
          {selectedUnit && detail.data && (
            <>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h2 className="font-display text-2xl">{detail.data.unit}</h2>
                  <p className="text-sm text-muted-foreground">{detail.data.description}</p>
                </div>
                <Badge value={detail.data.active} />
              </div>
              <p className="text-sm">Startup {detail.data.enabled} · pid {detail.data.main_pid || "—"}</p>
              <p className="break-all text-xs text-muted-foreground">{detail.data.fragment_path || "No unit file path reported"}</p>
              {can("services:write") && (
                <div className="flex flex-wrap gap-2">
                  {ACTIONS.map((action) => (
                    <Button key={action} size="sm" variant={action === "disable" ? "danger" : "outline"} disabled={operate.isPending} onClick={() => setConfirm(action)}>
                      {action}
                    </Button>
                  ))}
                </div>
              )}
              <div className="flex items-center justify-between gap-2">
                <h3 className="font-display text-lg">Journal</h3>
                <Button size="sm" variant="outline" onClick={() => setFollow((value) => !value)}>{follow ? "Following" : "Follow"}</Button>
              </div>
              <div className="flex flex-wrap gap-2">
                <FilterChip active={logFilter === "all"} onClick={() => setLogFilter("all")} label={`All ${entries.length}`} />
                <FilterChip active={logFilter === "error"} onClick={() => setLogFilter("error")} label={`Errors ${counts.error}`} />
                <FilterChip active={logFilter === "working"} onClick={() => setLogFilter("working")} label={`Working ${counts.working}`} />
                <FilterChip active={logFilter === "success"} onClick={() => setLogFilter("success")} label={`Success ${counts.success}`} />
              </div>
              <ol className="max-h-80 space-y-2 overflow-auto">
                {visible.map((entry, index) => (
                  <li key={`${entry.time}-${index}`} className="rounded-lg bg-background px-3 py-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge value={entry.tone === "working" ? "running" : entry.tone === "success" ? "succeeded" : "failed"} label={entry.label} />
                      {entry.time && <span className="text-xs text-muted-foreground">{entry.time}</span>}
                    </div>
                    <p className="mt-1 text-sm">{entry.text}</p>
                  </li>
                ))}
                {visible.length === 0 && <li className="text-sm text-muted-foreground">No log lines in this view.</li>}
              </ol>
            </>
          )}
        </section>
      </div>
      <Dialog open={confirm !== null} onOpenChange={(open) => { if (!open) setConfirm(null); }}>
        <DialogContent title={confirm ? `${confirm} ${selectedUnit}` : "Confirm"}>
          {confirm && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                {confirm === "restart" && "The service stops and starts again. Open connections drop until it is back."}
                {confirm === "enable" && "The service will start automatically when the server boots."}
                {confirm === "disable" && "The service will not start on boot. ssh and the core systemd units cannot be disabled."}
              </p>
              <Button variant={confirm === "disable" ? "danger" : "default"} disabled={operate.isPending} onClick={() => operate.mutate(confirm)}>Confirm {confirm}</Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function FilterChip({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return <Button size="sm" variant={active ? "default" : "outline"} onClick={onClick}>{label}</Button>;
}
