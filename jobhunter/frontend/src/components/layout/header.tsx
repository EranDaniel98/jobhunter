"use client";

import { usePathname } from "next/navigation";
import { Menu, Briefcase, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { NotificationCenter } from "@/components/layout/notification-center";
import { allNavItems } from "@/lib/nav-config";

interface HeaderProps {
  onMenuClick: () => void;
  lastEvent?: { type: string; data: Record<string, unknown> } | null;
}

export function Header({ onMenuClick, lastEvent = null }: HeaderProps) {
  const pathname = usePathname();
  const currentPage = allNavItems.find(
    (item) => pathname === item.href || pathname.startsWith(item.href + "/")
  );

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-4 border-b border-sidebar-border bg-sidebar px-4 lg:hidden">
      <Button variant="ghost" size="icon" onClick={onMenuClick} aria-label="Open navigation menu">
        <Menu className="h-5 w-5" />
      </Button>
      <div className="flex flex-1 items-center gap-2 min-w-0">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-primary/70 shadow-sm shadow-primary/20">
          <Briefcase className="h-3.5 w-3.5 text-sidebar-primary-foreground" />
        </div>
        <span className="text-sm font-semibold truncate">
          {currentPage?.label || "JobHunter AI"}
        </span>
      </div>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => window.dispatchEvent(new Event("open-command-menu"))}
        aria-label="Search"
      >
        <Search className="h-4 w-4" />
      </Button>
      <NotificationCenter lastEvent={lastEvent} />
      <ThemeToggle />
    </header>
  );
}
