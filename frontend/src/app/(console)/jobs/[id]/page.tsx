"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useJobEvents } from "@/lib/events";
import type { Job, JobLog } from "@/lib/types";
import { formatDuration, formatWhen } from "@/lib/utils";

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const { can } = useAuth();
  const queryClient = useQueryClient();
  useJobEvents(true);

  const job = useQuery({
    queryKey: ["jobs", params.id],
    queryFn: () => api<Job>(`/api/v1/jobs/${params.id}`),
    refetchInterval: (query) => (query.state.data && ["queued", "running"].includes(query.state.data.status) ? 2000 : false),
  });
  const logs = useQuery({
    queryKey: ["jobs", params.id, "logs"],
    queryFn: () => api<JobLog[]>(`/api/v1/jobs/${params.id}/logs`),
    refetchInterval: job.data && ["queued", "running"].includes(job.data.status) ? 2000 : false,
  });

  const action = useMutation({
    mutationFn: (kind: "retry" | "cancel") => api<Job>(`/api/v1/jobs/${params.id}/${kind}`, { method: "POST" }),
    onSuccess: (updated) => {
      toast.success(updated.cancel_requested && updated.status === "running" ? "Cancellation requested" : `Job ${updated.status}`);
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Action failed"),
  });

  const current = job.data;
  return (
    <div className="space-y-6">
      <Link href="/jobs" className="text-sm text-muted-foreground hover:text-foreground">← Jobs</Link>
      {job.isLoading && <p className="text-sm text-muted-foreground">Loading job…</p>}
      {job.isError && <p className="text-sm text-danger">Job not found or you cannot view it.</p>}
      {current && (
        <>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h1 className="font-display text-3xl">{current.job_type}</h1>
              <p className="mt-1 break-all text-xs text-muted-foreground">{current.id}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge value={current.status} />
              {can("jobs:write") && ["failed", "cancelled"].includes(current.status) && (
                <Button size="sm" onClick={() => action.mutate("retry")} disabled={action.isPending}>Retry</Button>
              )}
              {can("jobs:cancel") && !["succeeded", "failed", "cancelled"].includes(current.status) && (
                <Button size="sm" variant="danger" onClick={() => action.mutate("cancel")} disabled={action.isPending || current.cancel_requested}>
                  {current.cancel_requested ? "Cancelling…" : "Cancel"}
                </Button>
              )}
            </div>
          </div>
          <section className="grid gap-3 sm:grid-cols-3">
            <Info label="Progress" value={`${current.progress}%`} />
            <Info label="Attempts" value={`${current.attempts} / ${current.max_retries + 1}`} />
            <Info label="Duration" value={formatDuration(current.started_at, current.finished_at)} />
          </section>
          {current.error_message && <p className="panel p-4 text-sm text-danger">{current.error_message}</p>}
          {current.result && (
            <pre className="panel overflow-x-auto p-4 text-xs">{JSON.stringify(current.result, null, 2)}</pre>
          )}
          <section className="panel p-4">
            <h2 className="font-display text-xl">Logs</h2>
            <ol className="mt-3 space-y-2">
              {(logs.data ?? []).map((entry) => (
                <li key={entry.id} className="grid gap-1 text-sm sm:grid-cols-[9rem_1fr]">
                  <span className="text-xs text-muted-foreground">{formatWhen(entry.created_at)}</span>
                  <span><Badge value={entry.level} /> <span className="ml-2">{entry.message}</span></span>
                </li>
              ))}
              {logs.data?.length === 0 && <li className="text-sm text-muted-foreground">No log lines yet.</li>}
            </ol>
          </section>
        </>
      )}
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="panel p-4">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg">{value}</p>
    </div>
  );
}
