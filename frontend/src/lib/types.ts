export type User = {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  mfa_enabled: boolean;
  roles: string[];
  permissions: string[];
  last_login_at: string | null;
  created_at: string;
};

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export type Job = {
  id: string;
  job_type: string;
  status: JobStatus;
  server_id: string | null;
  params: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error_message: string | null;
  progress: number;
  attempts: number;
  max_retries: number;
  timeout_seconds: number;
  cancellable: boolean;
  cancel_requested: boolean;
  created_by_id: string | null;
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type JobLog = {
  id: number;
  job_id: string;
  level: string;
  message: string;
  data: Record<string, unknown> | null;
  created_at: string;
};

export type JobStats = {
  queued: number;
  running: number;
  succeeded: number;
  failed: number;
  cancelled: number;
  failed_last_24h: number;
};

export type PageMeta = { page: number; page_size: number; total: number; pages: number };

export type AuditEntry = {
  id: number;
  actor_user_id: string | null;
  actor_type: string;
  actor_label: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  outcome: string;
  ip_address: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
};

export type HealthReport = {
  status: "ok" | "degraded" | "down";
  app: string;
  environment: string;
  components: Record<string, { status: string; latency_ms?: number; version?: string; error?: string; workers?: string[] }>;
};

export type DashboardSummary = {
  servers: { total: number; online: number; offline: number; pending: number };
  jobs: JobStats;
  recent_jobs: Job[];
};

export type Role = { name: string; description: string; permissions: string[] };
