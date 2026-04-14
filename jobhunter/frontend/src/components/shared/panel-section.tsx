"use client";

import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export interface PanelSectionProps {
  title: string;
  icon?: LucideIcon;
  children: React.ReactNode;
  className?: string;
}

export function PanelSection({ title, icon: Icon, children, className }: PanelSectionProps) {
  return (
    <section
      role="region"
      aria-label={title}
      className={cn("pt-5 first:pt-0 first:border-t-0 border-t", className)}
    >
      <div className="flex items-center gap-2 mb-3">
        {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
        <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {title}
        </h3>
      </div>
      {children}
    </section>
  );
}
