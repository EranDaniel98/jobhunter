"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from "@/components/ui/tooltip";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { NotificationCenter } from "@/components/layout/notification-center";
import { useApprovalCount } from "@/lib/hooks/use-approvals";
import type { PlanTier } from "@/lib/types";
import { LogOut, Briefcase, Sparkles, Search, ChevronLeft, ChevronRight, Shield } from "lucide-react";
import { navSections, adminNavItem } from "@/lib/nav-config";

interface SidebarProps {
  lastEvent?: { type: string; data: Record<string, unknown> } | null;
  onCollapseChange?: (collapsed: boolean) => void;
}

export function Sidebar({ lastEvent = null, onCollapseChange }: SidebarProps) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { data: approvalCount } = useApprovalCount();

  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem("sidebar_collapsed") === "true";
  });

  function toggleCollapse() {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem("sidebar_collapsed", String(next));
  }

  useEffect(() => {
    onCollapseChange?.(collapsed);
  }, [collapsed, onCollapseChange]);

  const initials = user?.full_name
    ?.split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2) || "?";

  return (
    <TooltipProvider>
    <aside className={cn("hidden lg:flex lg:flex-col lg:fixed lg:inset-y-0 border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-all duration-200", collapsed ? "lg:w-16" : "lg:w-64")} aria-label="Main navigation">
      <div className={cn("flex h-16 items-center gap-2 border-b border-sidebar-border", collapsed ? "justify-center px-2" : "px-6")}>
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-primary/70 shadow-sm shadow-primary/20">
          <Briefcase className="h-4 w-4 text-sidebar-primary-foreground" />
        </div>
        {!collapsed && <span className="text-lg font-semibold"><span className="font-bold">JobHunter</span><span className="text-primary/70 font-light ml-0.5">AI</span></span>}
      </div>

      {!collapsed && (
        <button
          onClick={() => window.dispatchEvent(new Event("open-command-menu"))}
          className="mx-3 mt-3 flex items-center gap-2 rounded-xl border border-sidebar-border bg-sidebar-accent/50 px-3 py-1.5 text-xs text-sidebar-foreground/50 hover:text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
        >
          <Search className="h-3.5 w-3.5" />
          <span className="flex-1 text-left">Search...</span>
          <kbd className="rounded border border-sidebar-border bg-sidebar px-1.5 py-0.5 text-[10px] font-mono">
            {typeof navigator !== "undefined" && /Mac/.test(navigator.userAgent) ? "\u2318" : "Ctrl"}+K
          </kbd>
        </button>
      )}
      {collapsed && (
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              onClick={() => window.dispatchEvent(new Event("open-command-menu"))}
              className="mx-auto mt-3 flex h-10 w-10 items-center justify-center rounded-xl text-sidebar-foreground/50 hover:text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
            >
              <Search className="h-4 w-4" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="right">Search</TooltipContent>
        </Tooltip>
      )}

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {navSections.map((section) => (
          <div key={section.label} className="mb-3">
            {!collapsed && (
              <p className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-wider text-sidebar-foreground/40">
                {section.label}
              </p>
            )}
            <ul className="space-y-0.5">
              {section.items.map((item) => {
                const Icon = item.icon;
                const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
                return (
                  <li key={item.href}>
                    {collapsed ? (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Link href={item.href} className={cn("flex h-10 w-10 items-center justify-center rounded-xl mx-auto relative", isActive ? "bg-primary/15 text-primary" : "text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent")}>
                            <Icon className="h-4 w-4" />
                            {item.badge && approvalCount?.count ? (
                              <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-[9px] font-bold text-primary-foreground">
                                {approvalCount.count > 9 ? "9+" : approvalCount.count}
                              </span>
                            ) : null}
                          </Link>
                        </TooltipTrigger>
                        <TooltipContent side="right">{item.label}</TooltipContent>
                      </Tooltip>
                    ) : (
                      <Link href={item.href}>
                        <Button
                          variant="ghost"
                          className={cn(
                            "w-full justify-start gap-3 rounded-xl text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent transition-all",
                            isActive && "bg-primary/15 text-primary font-semibold border-l-[3px] border-primary pl-2.5"
                          )}
                        >
                          <Icon className={cn("h-4 w-4", isActive && "text-primary")} />
                          {item.label}
                          {item.badge && approvalCount?.count ? (
                            <span className="ml-auto flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground" aria-label={`${approvalCount.count} pending`}>
                              {approvalCount.count > 99 ? "99+" : approvalCount.count}
                            </span>
                          ) : null}
                        </Button>
                      </Link>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
        {user?.is_admin && (
          <div className="mb-3">
            {!collapsed && (
              <p className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-wider text-sidebar-foreground/40">
                Admin
              </p>
            )}
            <ul>
              <li>
                {collapsed ? (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Link href={adminNavItem.href} className={cn("flex h-10 w-10 items-center justify-center rounded-xl mx-auto", (pathname === adminNavItem.href || pathname.startsWith(adminNavItem.href + "/")) ? "bg-primary/15 text-primary" : "text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent")}>
                        <adminNavItem.icon className="h-4 w-4" />
                      </Link>
                    </TooltipTrigger>
                    <TooltipContent side="right">{adminNavItem.label}</TooltipContent>
                  </Tooltip>
                ) : (
                  <Link href={adminNavItem.href}>
                    <Button
                      variant="ghost"
                      className={cn(
                        "w-full justify-start gap-3 rounded-xl text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent transition-all",
                        (pathname === adminNavItem.href || pathname.startsWith(adminNavItem.href + "/")) && "bg-primary/15 text-primary font-semibold border-l-[3px] border-primary pl-2.5"
                      )}
                    >
                      <adminNavItem.icon className={cn("h-4 w-4", (pathname === adminNavItem.href || pathname.startsWith(adminNavItem.href + "/")) && "text-primary")} />
                      {adminNavItem.label}
                    </Button>
                  </Link>
                )}
              </li>
            </ul>
          </div>
        )}
      </nav>

      {user && user.is_admin ? (
        <div className="px-3 pb-2">
          {collapsed ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex h-10 w-10 items-center justify-center rounded-xl mx-auto bg-amber-500/15 text-amber-600">
                  <Shield className="h-3.5 w-3.5" />
                </div>
              </TooltipTrigger>
              <TooltipContent side="right">Admin</TooltipContent>
            </Tooltip>
          ) : (
            <div className="flex items-center gap-2 rounded-xl px-3 py-1.5 text-xs bg-amber-500/15 text-amber-600 font-medium">
              <Shield className="h-3.5 w-3.5" />
              Admin
            </div>
          )}
        </div>
      ) : user && (user.plan_tier as PlanTier) !== "hunter" ? (
        <div className="px-3 pb-2">
          {collapsed ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <Link href="/plans" className="flex h-10 w-10 items-center justify-center rounded-xl mx-auto text-sidebar-foreground/50 hover:text-primary hover:bg-sidebar-accent">
                  <Sparkles className="h-3.5 w-3.5 text-primary" />
                </Link>
              </TooltipTrigger>
              <TooltipContent side="right">Upgrade Plan</TooltipContent>
            </Tooltip>
          ) : (
            <Link href="/plans">
              <Button variant="ghost" size="sm" className="w-full justify-start gap-2 rounded-xl text-xs text-sidebar-foreground/50 hover:text-primary hover:bg-sidebar-accent">
                <Sparkles className="h-3.5 w-3.5 text-primary" />
                {(user.plan_tier as PlanTier) === "free" ? "Free Plan" : "Explorer"} &mdash; Upgrade
              </Button>
            </Link>
          )}
        </div>
      ) : null}

      <div className={cn("border-t border-sidebar-border p-3", collapsed ? "flex flex-col items-center gap-2" : "space-y-2")}>
        {!collapsed && (
          <div className="flex items-center gap-2">
            <NotificationCenter lastEvent={lastEvent} />
            <ThemeToggle />
          </div>
        )}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            {collapsed ? (
              <button className="flex h-10 w-10 items-center justify-center rounded-xl hover:bg-sidebar-accent transition-colors">
                <Avatar className="h-7 w-7">
                  <AvatarFallback className="text-xs bg-primary/15 text-primary font-semibold">{initials}</AvatarFallback>
                </Avatar>
              </button>
            ) : (
              <Button variant="ghost" className="group/avatar w-full justify-start gap-3 rounded-xl text-sidebar-foreground hover:bg-sidebar-accent">
                <Avatar className="h-7 w-7 shrink-0">
                  <AvatarFallback className="text-xs bg-primary/15 text-primary font-semibold ring-2 ring-transparent group-hover/avatar:ring-primary/30 transition-all">{initials}</AvatarFallback>
                </Avatar>
                <span className="text-sm">{user?.full_name}</span>
              </Button>
            )}
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-56">
            <DropdownMenuItem onClick={() => logout()}>
              <LogOut className="mr-2 h-4 w-4" />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <button
        onClick={toggleCollapse}
        className="mx-3 mb-3 flex items-center justify-center rounded-xl p-2 text-sidebar-foreground/50 hover:text-sidebar-foreground hover:bg-sidebar-accent transition-colors"
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
      </button>
    </aside>
    </TooltipProvider>
  );
}
