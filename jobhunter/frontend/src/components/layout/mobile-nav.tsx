"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ThemeToggle } from "@/components/layout/theme-toggle";

import { useApprovalCount } from "@/lib/hooks/use-approvals";
import type { PlanTier } from "@/lib/types";
import { LogOut, Briefcase, Sparkles } from "lucide-react";
import { navSections, adminNavItem } from "@/lib/nav-config";

interface MobileNavProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  lastEvent?: { type: string; data: Record<string, unknown> } | null;
}

export function MobileNav({ open, onOpenChange }: MobileNavProps) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { data: approvalCount } = useApprovalCount();

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="left" className="w-64 p-0 bg-sidebar text-sidebar-foreground border-sidebar-border">
        <SheetHeader className="flex h-16 items-center gap-2 border-b border-sidebar-border px-6">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-primary/70 shadow-sm shadow-primary/20">
              <Briefcase className="h-4 w-4 text-sidebar-primary-foreground" />
            </div>
            <SheetTitle className="text-lg font-semibold text-sidebar-foreground"><span className="font-bold">JobHunter</span><span className="text-primary/70 font-light ml-0.5">AI</span></SheetTitle>
          </div>
        </SheetHeader>

        <nav className="flex-1 overflow-y-auto px-3 py-4">
          {navSections.map((section) => (
            <div key={section.label} className="mb-3">
              <p className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-wider text-sidebar-foreground/40">
                {section.label}
              </p>
              <ul className="space-y-0.5">
                {section.items.map((item) => {
                  const Icon = item.icon;
                  const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
                  return (
                    <li key={item.href}>
                      <Link href={item.href} onClick={() => onOpenChange(false)}>
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
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
          {user?.is_admin && (
            <div className="mb-3">
              <p className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-wider text-sidebar-foreground/40">
                Admin
              </p>
              <ul>
                <li>
                  <Link href={adminNavItem.href} onClick={() => onOpenChange(false)}>
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
                </li>
              </ul>
            </div>
          )}
        </nav>

        {user && (user.plan_tier as PlanTier) !== "hunter" && (
          <div className="px-3 pb-2">
            <Link href="/plans" onClick={() => onOpenChange(false)}>
              <Button variant="ghost" size="sm" className="w-full justify-start gap-2 rounded-xl text-xs text-sidebar-foreground/50 hover:text-primary hover:bg-sidebar-accent">
                <Sparkles className="h-3.5 w-3.5 text-primary" />
                {(user.plan_tier as PlanTier) === "free" ? "Free Plan" : "Explorer"} &mdash; Upgrade
              </Button>
            </Link>
          </div>
        )}

        <div className="border-t border-sidebar-border p-3 space-y-1">
          <div className="flex items-center gap-2 px-1 pb-1">
            <ThemeToggle />
            <span className="flex-1 truncate text-sm text-sidebar-foreground">{user?.full_name}</span>
          </div>
          <Button variant="ghost" className="w-full justify-start gap-3 rounded-xl text-sidebar-foreground hover:bg-sidebar-accent" onClick={() => logout()}>
            <LogOut className="h-4 w-4" />
            Log out
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
