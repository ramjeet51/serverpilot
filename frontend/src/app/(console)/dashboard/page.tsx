"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { useJobEvents } from "@/lib/events";
import type { DashboardSummary, HealthReport } from "@/lib/types";
import { formatWhen } from "@/lib/utils";

export default function DashboardPage() {
  const summary = useQuery({
    queryKey: ["summary"],
    queryFn: () => api<DashboardSummary>("/api/v1/monitoring/summary"),
    refetchInterval: 15_000,
  });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api<HealthReport>("/api/v1/health"),
    refetchInterval: 15_000,
  });
  useJobEvents(true);

  const servers = summary.data?.servers;
  const jobs = summary.data?.jobs;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl sm:text-4xl">Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">Management server health and job activity. Server fleet metrics arrive with the Ubuntu agent.</p>
      </div>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Servers" value={servers?.total ?? "—"} hint={`${servers?.online ?? 0} online · ${servers?.pending ?? 0} pending`} />
        <Stat label="Queued jobs" value={jobs?.queued ?? "—"} hint={`${jobs?.running ?? 0} running`} />
        <Stat label="Succeeded" value={jobs?.succeeded ?? "—"} hint="All time" />
        <Stat label="Failed (24h)" value={jobs?.failed_last_24h ?? "—"} hint={`${jobs?.failed ?? 0} failed overall`} />
      </section>

      <section className="grid gap-4 lg:grid-cols-5">
        <div className="panel p-5 lg:col-span-2">
          <h2 className="font-display text-xl">Platform</h2>
          <ul className="mt-4 space-y-3">
            {health.isLoading && <li className="text-sm text-muted-foreground">Checking components…</li>}
            {health.data && Object.entries(health.data.components).map(([name, component]) => (
              <li key={name} className="flex items-center justify-between gap-3 text-sm">
                <span className="capitalize">{name}</span>
                <span className="flex items-center gap-2">
                  {component.version && <span className="text-muted-foreground">v{component.version}</span>}
                  <Badge value={component.status === "ok" ? "ok" : component.status} />
                </span>
              </li>
            ))}
            {health.isError && <li className="text-sm text-danger">Health check failed. The API may be down.</li>}
          </ul>
        </div>
        <div className="panel overflow-hidden lg:col-span-3">
          <div className="flex items-center justify-between px-5 py-4">
            <h2 className="font-display text-xl">Recent jobs</h2>
            <Link href="/jobs" className="text-sm text-accent">View all</Link>
          </div>
          <JobRows jobs={summary.data?.recent_jobs ?? []} loading={summary.isLoading} />
        </div>
      </section>
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: number | string; hint: string }) {
  return (
    <div className="panel p-4">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-2 font-display text-3xl">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}

export function JobRows({ jobs, loading }: { jobs: DashboardSummary["recent_jobs"]; loading?: boolean }) {
  if (loading) return <p className="px-5 pb-5 text-sm text-muted-foreground">Loading jobs…</p>;
  if (jobs.length === 0) return <p className="px-5 pb-5 text-sm text-muted-foreground">No jobs yet. Run a diagnostics job to verify the worker.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[36rem] text-left text-sm">
        <thead className="text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="px-5 py-2 font-medium">Type</th>
            <th className="px-3 py-2 font-medium">Status</th>
            <th className="px-3 py-2 font-medium">Progress</th>
            <th className="px-5 py-2 font-medium">Queued</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id} className="border-t border-border">
              <td className="px-5 py-3"><Link href={`/jobs/${job.id}`} className="hover:text-accent">{job.job_type}</Link></td>
              <td className="px-3 py-3"><Badge value={job.status} /></td>
              <td className="px-3 py-3">{job.progress}%</td>
              <td className="px-5 py-3 text-muted-foreground">{formatWhen(job.queued_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
