"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatBytes, formatWhen } from "@/lib/utils";

type ManagedServer = {
  id: string;
  name: string;
  hostname: string;
  ip_address: string | null;
  status: string;
  os_name: string | null;
  os_version: string | null;
  kernel_version: string | null;
  cpu_cores: number | null;
  memory_total_bytes: number | null;
  disk_total_bytes: number | null;
  last_seen_at: string | null;
  agent_status: string | null;
  cpu_percent: number | null;
  memory_percent: number | null;
  disk_percent: number | null;
  description: string;
};

type Registration = {
  server: ManagedServer;
  registration_token: string;
  gateway_url: string;
  expires_at: string | null;
};

export default function ServersPage() {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [issued, setIssued] = useState<Registration | null>(null);
  const [form, setForm] = useState({ name: "", hostname: "", ip_address: "", description: "" });

  const servers = useQuery({
    queryKey: ["servers"],
    queryFn: () => api<ManagedServer[]>("/api/v1/servers"),
    refetchInterval: 10_000,
  });

  const create = useMutation({
    mutationFn: () => api<Registration>("/api/v1/servers", {
      method: "POST",
      body: JSON.stringify({ ...form, environment: "production" }),
    }),
    onSuccess: (result) => {
      setIssued(result);
      setForm({ name: "", hostname: "", ip_address: "", description: "" });
      void queryClient.invalidateQueries({ queryKey: ["servers"] });
      void queryClient.invalidateQueries({ queryKey: ["summary"] });
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Could not add the server"),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api(`/api/v1/servers/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast.success("Server removed");
      void queryClient.invalidateQueries({ queryKey: ["servers"] });
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Could not remove the server"),
  });

  const rotate = useMutation({
    mutationFn: (id: string) => api<Registration>(`/api/v1/servers/${id}/registration-token`, { method: "POST" }),
    onSuccess: (result) => setIssued(result),
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Could not issue a token"),
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-display text-3xl sm:text-4xl">Servers</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Each Ubuntu machine runs an agent that connects outbound. The agent reports health. It does not open a shell.
          </p>
        </div>
        {can("servers:write") && (
          <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (!next) setIssued(null); }}>
            <DialogTrigger asChild><Button>Add server</Button></DialogTrigger>
            <DialogContent title={issued ? "Registration token" : "Add server"}>
              {issued ? (
                <IssuedToken issued={issued} />
              ) : (
                <form className="space-y-3" onSubmit={(event) => { event.preventDefault(); create.mutate(); }}>
                  <Field label="Name"><Input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="k8s-worker" /></Field>
                  <Field label="Hostname"><Input required value={form.hostname} onChange={(event) => setForm({ ...form, hostname: event.target.value })} placeholder="k8s-worker" /></Field>
                  <Field label="IP address"><Input required value={form.ip_address} onChange={(event) => setForm({ ...form, ip_address: event.target.value })} placeholder="172.16.17.59" /></Field>
                  <Field label="Notes"><Input value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></Field>
                  <Button type="submit" disabled={create.isPending}>Create registration token</Button>
                </form>
              )}
            </DialogContent>
          </Dialog>
        )}
      </div>

      {issued && !open && <IssuedToken issued={issued} />}

      {servers.isLoading && <p className="text-sm text-muted-foreground">Loading servers…</p>}
      {servers.isError && <p className="text-sm text-danger">Could not load servers.</p>}
      {servers.data?.length === 0 && <p className="panel p-5 text-sm text-muted-foreground">No servers yet. Add one to get a registration token for its agent.</p>}

      <div className="grid gap-4 lg:grid-cols-2">
        {(servers.data ?? []).map((server) => (
          <article key={server.id} className="panel space-y-4 p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="font-display text-2xl">{server.name}</h2>
                <p className="text-sm text-muted-foreground">{server.hostname} · {server.ip_address}</p>
              </div>
              <Badge value={server.status} />
            </div>
            <dl className="grid grid-cols-3 gap-3 text-sm">
              <Metric label="CPU" value={server.cpu_percent == null ? "—" : `${server.cpu_percent}%`} hint={server.cpu_cores ? `${server.cpu_cores} cores` : "waiting"} />
              <Metric label="Memory" value={server.memory_percent == null ? "—" : `${server.memory_percent}%`} hint={formatBytes(server.memory_total_bytes)} />
              <Metric label="Disk" value={server.disk_percent == null ? "—" : `${server.disk_percent}%`} hint={formatBytes(server.disk_total_bytes)} />
            </dl>
            <p className="text-sm text-muted-foreground">
              {server.os_name ? `${server.os_name} ${server.os_version ?? ""}` : "Agent has not reported yet"}
              {server.kernel_version ? ` · ${server.kernel_version}` : ""}
            </p>
            <p className="text-xs text-muted-foreground">Last seen {formatWhen(server.last_seen_at)} · agent {server.agent_status ?? "missing"}</p>
            {server.description && <p className="text-sm">{server.description}</p>}
            {can("servers:write") && (
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline" onClick={() => rotate.mutate(server.id)} disabled={rotate.isPending}>New token</Button>
                <Button size="sm" variant="danger" onClick={() => {
                  if (window.confirm(`Remove ${server.name}? The agent will be rejected.`)) remove.mutate(server.id);
                }}>Remove</Button>
              </div>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}

function IssuedToken({ issued }: { issued: Registration }) {
  const local = issued.gateway_url.includes("127.0.0.1") || issued.gateway_url.includes("localhost");
  return (
    <div className="panel space-y-3 p-5">
      <h2 className="font-display text-xl">Token for {issued.server.name}</h2>
      <p className="text-sm text-muted-foreground">Shown once. Put it in the agent environment, then start the agent. It expires {formatWhen(issued.expires_at)}.</p>
      <code className="block overflow-x-auto rounded-lg bg-background px-3 py-2 text-xs">{issued.registration_token}</code>
      <p className="text-sm">Gateway URL</p>
      <code className="block overflow-x-auto rounded-lg bg-background px-3 py-2 text-xs">{issued.gateway_url}</code>
      {local && (
        <p className="text-sm text-muted-foreground">
          This URL is on the server itself. Use it when the Mac holds an SSH tunnel to that host, because the host cannot route back to the Mac.
        </p>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="space-y-1"><Label>{label}</Label>{children}</div>;
}

function Metric({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-lg">{value}</dd>
      <dd className="text-xs text-muted-foreground">{hint}</dd>
    </div>
  );
}
