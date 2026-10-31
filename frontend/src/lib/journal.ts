export type JournalTone = "error" | "working" | "success";

export type JournalEntry = {
  time: string;
  tone: JournalTone;
  label: string;
  text: string;
};

const HASH = /\b[0-9a-f]{12,64}\b/gi;

function humanize(text: string): string {
  const endpoint = text.match(/\bep=([A-Za-z0-9_.-]+)/);
  if (/^sbJoin:/i.test(text)) {
    return endpoint ? `Connected ${endpoint[1]} to a Docker network` : "Connected a container to a Docker network";
  }
  if (/^stopping\s+/i.test(text)) return `Stopping ${text.replace(/^stopping\s+/i, "")}`;
  if (/^starting\s+/i.test(text)) return `Starting ${text.replace(/^starting\s+/i, "")}`;
  const cleaned = text.replace(HASH, "").replace(/\s{2,}/g, " ").replace(/\s+([,.;])/g, "$1").trim();
  if (!cleaned) return "Service wrote a log line";
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}

function toneOf(raw: string, text: string): JournalTone {
  const level = raw.match(/\blevel=(\w+)/i)?.[1]?.toLowerCase() ?? "";
  const blob = `${level} ${text}`.toLowerCase();
  if (level === "error" || level === "fatal" || level === "crit" || /\b(error|fatal|failed|failure|exception|panic)\b/.test(blob)) {
    return "error";
  }
  if (/\b(started|listening|completed|succeeded|success|ready|activated|healthy)\b/.test(blob) || /api listen/.test(blob)) {
    return "success";
  }
  return "working";
}

export function explainJournal(line: string): JournalEntry {
  const stamp = line.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})/);
  const quoted = line.match(/\bmsg="([^"]*)"/);
  const body = quoted?.[1] ?? line.replace(/^\S+\s+\S+\s+[^:]+:\s*/, "").replace(/^time="[^"]*"\s*/, "");
  const text = humanize(body);
  const tone = toneOf(line, text);
  const label = tone === "error" ? "Error" : tone === "success" ? "Success" : "Working";
  return { time: stamp ? `${stamp[1]} ${stamp[2]}` : "", tone, label, text };
}
