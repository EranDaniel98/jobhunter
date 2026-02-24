"use client";

import { useState, useEffect, useCallback } from "react";
import { Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";

interface Notification {
  id: string;
  type: string;
  message: string;
  timestamp: Date;
  read: boolean;
}

function eventToMessage(type: string, data: Record<string, unknown>): string {
  switch (type) {
    case "followup_drafted": return "New follow-up drafted and ready for approval";
    case "email_sent": return "Email sent successfully";
    case "email_delivered": return "Email delivered";
    case "email_opened": return "Your email was opened";
    case "email_clicked": return "Link clicked in your email";
    case "resume_parsed": return "Resume parsed successfully";
    case "research_completed": return `Research completed for ${(data as { company_name?: string }).company_name || "a company"}`;
    default: return type.replace(/_/g, " ");
  }
}

export function NotificationCenter({ lastEvent }: { lastEvent: { type: string; data: Record<string, unknown> } | null }) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!lastEvent) return;
    const notification: Notification = {
      id: `${Date.now()}-${Math.random()}`,
      type: lastEvent.type,
      message: eventToMessage(lastEvent.type, lastEvent.data),
      timestamp: new Date(),
      read: false,
    };
    setNotifications((prev) => [notification, ...prev].slice(0, 50));
  }, [lastEvent]);

  const unreadCount = notifications.filter((n) => !n.read).length;

  const markAllRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  return (
    <Popover open={open} onOpenChange={(o) => { setOpen(o); if (o) markAllRead(); }}>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="relative" aria-label="Notifications">
          <Bell className="h-4 w-4" />
          {unreadCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h4 className="text-sm font-semibold">Notifications</h4>
          {notifications.length > 0 && (
            <Button variant="ghost" size="sm" className="text-xs" onClick={() => setNotifications([])}>
              Clear all
            </Button>
          )}
        </div>
        <ScrollArea className="max-h-80">
          {notifications.length === 0 ? (
            <p className="p-4 text-center text-sm text-muted-foreground">No notifications yet</p>
          ) : (
            <div className="divide-y">
              {notifications.map((n) => (
                <div key={n.id} className="px-4 py-3">
                  <p className="text-sm">{n.message}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {n.timestamp.toLocaleTimeString()}
                  </p>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </PopoverContent>
    </Popover>
  );
}
