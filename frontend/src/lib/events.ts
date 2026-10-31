"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { getAccessToken } from "@/lib/api";
import { env } from "@/lib/env";

export function useJobEvents(enabled: boolean) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!enabled) return;
    const token = getAccessToken();
    if (!token) return;
    const socket = new WebSocket(`${env.wsUrl}/api/v1/ws/events`);
    socket.onopen = () => socket.send(JSON.stringify({ type: "auth", token }));
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as { type: string };
        if (message.type === "job.updated" || message.type === "job.log") {
          void queryClient.invalidateQueries({ queryKey: ["jobs"] });
          void queryClient.invalidateQueries({ queryKey: ["summary"] });
        }
      } catch {
        /* ignore malformed frames */
      }
    };
    return () => socket.close();
  }, [enabled, queryClient]);
}
