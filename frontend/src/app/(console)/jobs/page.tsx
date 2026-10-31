"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { JobRows } from "@/app/(console)/dashboard/page";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useJobEvents } from "@/lib/events";
import type { Job } from "@/lib/types";
import { cn } from "@/lib/utils";

const FILTERS = ["all", "queued", "running", "succeeded", "failed", "cancelled"] as const;

export default function JobsPage() {
  const { can } = useAuth();
  const [status, setStatus] = useState<(typeof FILTERS)[number]>("all");
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  useJobEvents(true);

  const query = useQuery({
    queryKey: ["jobs", status],
    queryFn: () => {
      const params = new URLSearchParams({ page_size: "20" });
      if (status !== "all") params.set("status", status);
      return api<Job[]>(`/api/v1/jobs?${params}`);
    },
  });

  const create = useMutation({
    mutationFn: (job_type: "platform.diagnostics" | "platform.sleep_test") =>
      api<Job>("/api/v1/jobs", { method: "POST", body: JSON.stringify({ job_type, params: job_type === "platform.sleep_test" ? { duration_seconds: 5 } : {} }) }),
    onSuccess: (job) => {
      toast.success(`Queued ${job.job_type}`);
      setOpen(false);
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (error) => toast.error(error instanceof ApiError ? error.message : "Could not queue the job"),
  });

  const jobs = Array.isArray(query.data) ? query.data : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-display text-3xl sm:text-4xl">Jobs</h1>
          <p className="mt-1 text-sm text-muted-foreground">Queued work runs on the Celery worker and streams status over WebSocket.</p>
        </div>
        {can("jobs:write") && (
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild><Button>New job</Button></DialogTrigger>
            <DialogContent title="Queue a job">
              <div className="space-y-3">
                <Button className="w-full" disabled={create.isPending} onClick={() => create.mutate("platform.diagnostics")}>
                  Platform diagnostics
                </Button>
                <Button variant="secondary" className="w-full" disabled={create.isPending} onClick={() => create.mutate("platform.sleep_test")}>
                  Sleep test (5s, cancellable)
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        )}
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {FILTERS.map((item) => (
          <button
            key={item}
            onClick={() => setStatus(item)}
            className={cn("shrink-0 rounded-full px-3 py-1 text-xs capitalize", status === item ? "bg-accent text-accent-foreground" : "bg-muted text-muted-foreground")}
          >
            {item}
          </button>
        ))}
      </div>
      <div className="panel overflow-hidden">
        {query.isError ? (
          <p className="p-5 text-sm text-danger">Could not load jobs.</p>
        ) : (
          <JobRows jobs={jobs} loading={query.isLoading} />
        )}
        {jobs[0] && <p className="px-5 pb-4 text-xs text-muted-foreground">Open a row for logs, retry, and cancellation. <Link className="text-accent" href={`/jobs/${jobs[0].id}`}>Latest</Link></p>}
      </div>
    </div>
  );
}
