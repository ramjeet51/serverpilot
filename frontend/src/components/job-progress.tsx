"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { useJobEvents } from "@/lib/events";
import type { Job, JobLog } from "@/lib/types";

export function JobProgress({ jobId }: { jobId: string }) {
  useJobEvents(true);
  const job = useQuery({
    queryKey: ["jobs", jobId],
    queryFn: () => api<Job>(`/api/v1/jobs/${jobId}`),
    refetchInterval: (query) => (query.state.data && ["queued", "running"].includes(query.state.data.status) ? 2000 : false),
  });
  const logs = useQuery({
    queryKey: ["jobs", jobId, "logs"],
    queryFn: () => api<JobLog[]>(`/api/v1/jobs/${jobId}/logs`),
    refetchInterval: job.data && ["queued", "running"].includes(job.data.status) ? 2000 : false,
  });
  const current = job.data;
  return (
    <section className="panel space-y-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-display text-xl">Operation</h2>
        {current && <Badge value={current.status} />}
      </div>
      {current && (
        <p className="text-sm text-muted-foreground">
          {current.job_type} · {current.progress}% · <Link className="underline" href={`/jobs/${current.id}`}>Open in Jobs</Link>
        </p>
      )}
      {current?.error_message && <p className="text-sm text-danger">{current.error_message}</p>}
      <ol className="max-h-64 space-y-1 overflow-auto font-mono text-xs">
        {(logs.data ?? []).map((entry) => (
          <li key={entry.id}>{entry.message}</li>
        ))}
        {logs.data?.length === 0 && <li className="text-muted-foreground">Waiting for log lines…</li>}
      </ol>
    </section>
  );
}
