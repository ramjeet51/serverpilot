import { describe, expect, it } from "vitest";

import { explainJournal } from "@/lib/journal";

describe("service journal", () => {
  it("turns a docker error into a readable error", () => {
    const entry = explainJournal(
      '2026-10-30T23:34:42+05:30 k8s-worker dockerd[1923]: time="2026-10-30T23:34:42.1+05:30" level=error msg="failed to start container"',
    );
    expect(entry.tone).toBe("error");
    expect(entry.label).toBe("Error");
    expect(entry.text).toBe("Failed to start container");
    expect(entry.time).toBe("2026-10-30 23:34:42");
  });

  it("marks startup as success and in-progress lines as working", () => {
    const started = explainJournal("2026-10-30T18:48:46+05:30 k8s-worker systemd[1]: Started docker.service - Docker Application Container Engine.");
    expect(started.tone).toBe("success");
    const stopping = explainJournal(
      '2026-10-30T23:34:42+05:30 k8s-worker dockerd[1923]: time="2026-10-30T23:34:42.1+05:30" level=info msg="stopping restart-manager"',
    );
    expect(stopping.tone).toBe("working");
    expect(stopping.text).toBe("Stopping restart-manager");
  });
});
