"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

interface WsEvent {
  type: string;
  data: Record<string, unknown>;
}

const WS_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1")
  .replace(/^http/, "ws");

export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<WsEvent | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelay = useRef(1000);
  const connectRef = useRef<(() => void) | undefined>(undefined);
  const qc = useQueryClient();

  const connect = useCallback(() => {
    const token = localStorage.getItem("access_token");
    if (!token) return;

    try {
      const ws = new WebSocket(`${WS_BASE}/ws?token=${token}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        reconnectDelay.current = 1000; // Reset backoff
      };

      ws.onmessage = (event) => {
        try {
          const parsed: WsEvent = JSON.parse(event.data);
          setLastEvent(parsed);

          // Invalidate React Query caches based on event type
          switch (parsed.type) {
            case "followup_drafted":
              qc.invalidateQueries({ queryKey: ["approvals"] });
              qc.invalidateQueries({ queryKey: ["messages"] });
              toast.info("New follow-up drafted and ready for approval");
              break;
            case "email_sent":
              qc.invalidateQueries({ queryKey: ["messages"] });
              qc.invalidateQueries({ queryKey: ["approvals"] });
              break;
            case "email_delivered":
            case "email_opened":
            case "email_clicked":
              qc.invalidateQueries({ queryKey: ["messages"] });
              break;
            case "resume_parsed":
              qc.invalidateQueries({ queryKey: ["candidates"] });
              qc.invalidateQueries({ queryKey: ["dna"] });
              toast.success("Resume parsed successfully");
              break;
            case "research_completed":
              qc.invalidateQueries({ queryKey: ["companies"] });
              toast.success(
                `Research completed for ${(parsed.data as { company_name?: string }).company_name || "company"}`
              );
              break;
          }
        } catch {
          // Ignore malformed messages
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        wsRef.current = null;
        // Reconnect with exponential backoff (max 30s)
        reconnectTimer.current = setTimeout(() => {
          reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30_000);
          connectRef.current?.();
        }, reconnectDelay.current);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      // Connection failed, will retry via onclose
    }
  }, [qc]);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // Prevent reconnect on unmount
        wsRef.current.close();
      }
    };
  }, [connect]);

  return { isConnected, lastEvent };
}
