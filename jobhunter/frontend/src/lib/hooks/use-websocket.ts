"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useQueryClient, type QueryKey } from "@tanstack/react-query";
import { toast } from "sonner";

interface WsEvent {
  type: string;
  data: Record<string, unknown>;
}

const WS_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1")
  .replace(/^http/, "ws");

const INVALIDATION_DEBOUNCE_MS = 500;

export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<WsEvent | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelay = useRef(1000);
  const connectRef = useRef<(() => void) | undefined>(undefined);
  const pendingKeys = useRef<Set<string>>(new Set());
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const qc = useQueryClient();

  const debouncedInvalidate = useCallback((...keys: QueryKey[]) => {
    for (const key of keys) {
      pendingKeys.current.add(JSON.stringify(key));
    }
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => {
      for (const serialized of pendingKeys.current) {
        qc.invalidateQueries({ queryKey: JSON.parse(serialized) });
      }
      pendingKeys.current.clear();
    }, INVALIDATION_DEBOUNCE_MS);
  }, [qc]);

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

          // Invalidate React Query caches based on event type (debounced)
          switch (parsed.type) {
            case "followup_drafted":
              debouncedInvalidate(["approvals"], ["messages"]);
              toast.info("New follow-up drafted and ready for approval");
              break;
            case "email_sent":
              debouncedInvalidate(["messages"], ["approvals"], ["analytics"]);
              break;
            case "email_delivered":
            case "email_opened":
            case "email_clicked":
              debouncedInvalidate(["messages"], ["analytics"]);
              break;
            case "resume_parsed": {
              debouncedInvalidate(["candidates"], ["dna"], ["resumes"]);
              const resumeData = parsed.data as { status?: string };
              if (resumeData.status === "failed") {
                toast.error("Resume processing failed. Our team has been notified — please try again later.");
              } else {
                toast.success("Resume parsed successfully");
              }
              break;
            }
            case "research_completed": {
              debouncedInvalidate(["companies"], ["company"], ["dossier"], ["contacts"]);
              const researchData = parsed.data as { company_name?: string; status?: string; error?: string };
              if (researchData.status === "failed") {
                toast.error(researchData.error || `Research failed for ${researchData.company_name || "company"}`);
              } else {
                toast.success(
                  `Research completed for ${researchData.company_name || "company"}`
                );
              }
              break;
            }
            case "analytics_completed":
            case "analytics_failed":
              debouncedInvalidate(["analytics-dashboard"], ["analytics-insights"], ["analytics"]);
              break;
            case "apply_analysis_completed":
            case "apply_analysis_failed":
              debouncedInvalidate(["job-postings"], ["apply-analysis"]);
              break;
            case "interview_prep_completed":
            case "interview_prep_failed":
              debouncedInvalidate(["interview-sessions"]);
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
  }, [debouncedInvalidate]);

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
