import { cn } from "@/lib/utils";

const tones: Record<string, string> = {
  ok: "bg-signal/15 text-signal",
  queued: "bg-muted text-muted-foreground",
  running: "bg-accent/15 text-accent",
  succeeded: "bg-signal/15 text-signal",
  online: "bg-signal/15 text-signal",
  failed: "bg-danger/15 text-danger",
  cancelled: "bg-muted text-muted-foreground",
  offline: "bg-danger/15 text-danger",
  pending: "bg-accent/15 text-accent",
  degraded: "bg-accent/15 text-accent",
  down: "bg-danger/15 text-danger",
  success: "bg-signal/15 text-signal",
  failure: "bg-danger/15 text-danger",
  warning: "bg-accent/15 text-accent",
  error: "bg-danger/15 text-danger",
  info: "bg-muted text-foreground",
  active: "bg-signal/15 text-signal",
  inactive: "bg-muted text-muted-foreground",
  enabled: "bg-signal/15 text-signal",
  disabled: "bg-muted text-muted-foreground",
  installed: "bg-signal/15 text-signal",
  absent: "bg-muted text-muted-foreground",
  unknown: "bg-muted text-muted-foreground",
  connected: "bg-signal/15 text-signal",
};

export function Badge({ value, label, className }: { value: string; label?: string; className?: string }) {
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize", tones[value] ?? tones.queued, className)}>
      {label ?? value}
    </span>
  );
}
