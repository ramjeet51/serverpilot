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
import type { Job } from "@/lib/types";

type ServerCard = { id: string; name: string; status: string };
type Software = {
  id: string; category: string; name: string; description: string; packages: string[];
  requires: { id: string; name: string }[]; service: string | null;
  protected_remove: boolean; installed: boolean; version: string | null; candidate_version: string | null; status: string;
};
type ArchivePackage = { name: string; description: string; installed: boolean; version: string | null };

const CATEGORIES = ["All", "Web", "Runtimes", "Containers", "Databases", "Observability", "Automation", "Tools"];

export default function SoftwarePage() {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const [serverId, setServerId] = useState("");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");
  const [archive, setArchive] = useState<ArchivePackage[] | null>(null);
  const [archiveName, setArchiveName] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [pending, setPending] = useState<{ item: Software; action: "install" | "remove" | "update"; version: string } | null>(null);

  const servers = useQuery({ queryKey: ["servers"], queryFn: () => api<ServerCard[]>("/api/v1/servers") });
  const selected = serverId || servers.data?.[0]?.id || "";
  const software = useQuery({
    queryKey: ["software", selected],
    queryFn: () => api<Software[]>(`/api/v1/software?server_id=${selected}`),
    enabled: Boolean(selected),
  });
  const versionQuery = useQuery({
    queryKey: ["software-versions", selected, pending?.item.id],
    queryFn: () => api<{ versions: string[] }>("/api/v1/software/versions", {
      method: "POST", body: JSON.stringify({ server_id: selected, software_id: pending?.item.id }),
    }),
    enabled: Boolean(selected && pending?.action === "install"),
  });

  const inspect = useMutation({
    mutationFn: () => api("/api/v1/software/inspect", { method: "POST", body: JSON.stringify({ server_id: selected }) }),
    onSuccess: () => {
      toast.success("Package inspection finished");
      void queryClient.invalidateQueries({ queryKey: ["software", selected] });
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Inspection failed"),
  });
  const operate = useMutation({
    mutationFn: (body: { software_id: string; action: string; version?: string | null }) => api<Job>("/api/v1/software/operations", {
      method: "POST",
      body: JSON.stringify({ server_id: selected, confirm: true, version: body.version || null, ...body }),
    }),
    onSuccess: (job) => {
      setJobId(job.id);
      setPending(null);
      toast.success("Operation queued");
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Operation failed"),
  });

  const findArchive = useMutation({
    mutationFn: () => api<{ packages: ArchivePackage[] }>("/api/v1/software/library", {
      method: "POST", body: JSON.stringify({ server_id: selected, query: search.trim() }),
    }),
    onSuccess: (result) => setArchive(result.packages),
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Archive search failed"),
  });
  const installArchive = useMutation({
    mutationFn: (name: string) => api<Job>("/api/v1/software/archive", {
      method: "POST", body: JSON.stringify({ server_id: selected, package: name, confirm: true }),
    }),
    onSuccess: (job) => {
      setJobId(job.id);
      setArchiveName(null);
      toast.success("Install queued");
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Install failed"),
  });

  const needle = search.trim().toLowerCase();
  const rows = (software.data ?? []).filter((item) => {
    const matchesCategory = category === "All" || item.category === category;
    const matchesSearch = !needle || `${item.name} ${item.description} ${item.id}`.toLowerCase().includes(needle);
    return matchesCategory && matchesSearch;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-display text-3xl sm:text-4xl">Software library</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Install from this library, or search the Ubuntu archive on the selected server. Each install is one named package, not a shell command.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select className="h-10 rounded-lg border border-border bg-background/60 px-3 text-sm" value={selected} onChange={(event) => setServerId(event.target.value)}>
            {(servers.data ?? []).map((server) => <option key={server.id} value={server.id}>{server.name}</option>)}
          </select>
          <Button variant="outline" disabled={!selected || inspect.isPending} onClick={() => inspect.mutate()}>
            {inspect.isPending ? "Checking…" : "Check installed"}
          </Button>
        </div>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search the library or the Ubuntu archive" />
        <Button variant="outline" disabled={!selected || search.trim().length < 2 || findArchive.isPending} onClick={() => findArchive.mutate()}>
          {findArchive.isPending ? "Searching…" : "Search archive"}
        </Button>
      </div>
      <div className="flex flex-wrap gap-2">
        {CATEGORIES.map((item) => (
          <Button key={item} size="sm" variant={category === item ? "default" : "outline"} onClick={() => setCategory(item)}>{item}</Button>
        ))}
      </div>
      {jobId && <JobProgress jobId={jobId} />}
      {archive && (
        <section className="space-y-3">
          <h2 className="font-display text-2xl">Ubuntu archive</h2>
          <div className="grid gap-3 lg:grid-cols-2">
            {archive.map((item) => (
              <article key={item.name} className="panel flex flex-col gap-2 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm">{item.name}</p>
                  <p className="text-xs text-muted-foreground">{item.description}</p>
                </div>
                {item.installed ? <Badge value="installed" /> : can("software:write") && (
                  <Button size="sm" onClick={() => setArchiveName(item.name)}>Install</Button>
                )}
              </article>
            ))}
            {archive.length === 0 && <p className="text-sm text-muted-foreground">No archive packages matched that search.</p>}
          </div>
        </section>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        {rows.map((item) => (
          <article key={item.id} className="panel space-y-3 p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">{item.category}</p>
                <h2 className="font-display text-2xl">{item.name}</h2>
                <p className="text-sm text-muted-foreground">{item.description}</p>
              </div>
              <Badge value={item.installed ? "installed" : item.status === "unknown" ? "unknown" : "absent"} label={item.installed ? "installed" : item.status === "unknown" ? "not checked" : "not installed"} />
            </div>
            <p className="text-sm">Installed {item.version ?? "—"}{item.candidate_version ? ` · candidate ${item.candidate_version}` : ""}</p>
            <p className="text-xs text-muted-foreground">Packages: {item.packages.join(", ")}{item.service ? ` · service ${item.service}` : ""}</p>
            {item.requires.length > 0 && (
              <p className="text-xs text-muted-foreground">Also installs {item.requires.map((req) => req.name).join(", ")} when it is missing.</p>
            )}
            {can("software:write") && (
              <div className="flex flex-wrap gap-2">
                <Button size="sm" disabled={item.installed} onClick={() => setPending({ item, action: "install", version: "" })}>Install</Button>
                <Button size="sm" variant="outline" disabled={!item.installed} onClick={() => setPending({ item, action: "update", version: "" })}>Update</Button>
                <Button size="sm" variant="danger" disabled={!item.installed || item.protected_remove} onClick={() => setPending({ item, action: "remove", version: "" })}>Remove</Button>
              </div>
            )}
          </article>
        ))}
      </div>
      <Dialog open={pending !== null} onOpenChange={(open) => { if (!open) setPending(null); }}>
        <DialogContent title={pending ? `${pending.action} ${pending.item.name}` : "Confirm"}>
          {pending && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                This runs only the allowlisted APT action for {pending.item.packages.join(", ")} on the selected server.
                {pending.action !== "remove" && pending.item.requires.length > 0
                  ? ` It also installs ${pending.item.requires.map((req) => req.name).join(", ")} when that software is missing.`
                  : ""}
              </p>
              {pending.action === "install" && (
                <select className="h-10 w-full rounded-lg border border-border bg-background/60 px-3 text-sm" value={pending.version} onChange={(event) => setPending({ ...pending, version: event.target.value })}>
                  <option value="">Latest candidate</option>
                  {(versionQuery.data?.versions ?? []).map((version) => <option key={version} value={version}>{version}</option>)}
                </select>
              )}
              <Button disabled={operate.isPending} variant={pending.action === "remove" ? "danger" : "default"} onClick={() => operate.mutate({
                software_id: pending.item.id, action: pending.action, version: pending.version || null,
              })}>
                Confirm {pending.action}
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
      <Dialog open={archiveName !== null} onOpenChange={(open) => { if (!open) setArchiveName(null); }}>
        <DialogContent title={archiveName ? `Install ${archiveName}` : "Install"}>
          {archiveName && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">This installs the Ubuntu package {archiveName} and the packages it requires on the selected server. System packages such as the kernel, sudo, and ssh are refused.</p>
              <Button disabled={installArchive.isPending} onClick={() => installArchive.mutate(archiveName)}>Confirm install</Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
