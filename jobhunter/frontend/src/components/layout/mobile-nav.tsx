"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useApprovalCount } from "@/lib/hooks/use-approvals";
import type { PlanTier } from "@/lib/types";
import {
  LayoutDashboard,
  FileText,
  Building2,
  Mail,
  ClipboardCheck,
  BarChart3,
  Settings,
  LogOut,
  Briefcase,
  Shield,
  Sparkles,
} from "lucide-react";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/resume", label: "Resume & DNA", icon: FileText },
  { href: "/companies", label: "Companies", icon: Building2 },
  { href: "/outreach", label: "Outreach", icon: Mail },
  { href: "/approvals", label: "Approvals", icon: ClipboardCheck, badge: true },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];

const adminNavItem = { href: "/admin", label: "Admin", icon: Shield };

interface MobileNavProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MobileNav({ open, onOpenChange }: MobileNavProps) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { data: approvalCount } = useApprovalCount();

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="left" className="w-64 p-0">
        <SheetHeader className="flex h-16 items-center gap-2 border-b px-6">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
              <Briefcase className="h-4 w-4 text-primary-foreground" />
            </div>
            <SheetTitle className="text-lg font-semibold">JobHunter AI</SheetTitle>
          </div>
        </SheetHeader>

        <nav className="flex-1 space-y-1 px-3 py-4">
          {[...navItems, ...(user?.is_admin ? [adminNavItem] : [])].map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link key={item.href} href={item.href} onClick={() => onOpenChange(false)}>
                <Button
                  variant={isActive ? "secondary" : "ghost"}
                  className={cn("w-full justify-start gap-3", isActive && "font-medium")}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                  {"badge" in item && item.badge && approvalCount?.count ? (
                    <span className="ml-auto flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
                      {approvalCount.count > 99 ? "99+" : approvalCount.count}
                    </span>
                  ) : null}
                </Button>
              </Link>
            );
          })}
        </nav>

        {user && (user.plan_tier as PlanTier) !== "hunter" && (
          <div className="px-3 pb-2">
            <Link href="/plans" onClick={() => onOpenChange(false)}>
              <Button variant="ghost" size="sm" className="w-full justify-start gap-2 text-xs text-muted-foreground hover:text-foreground">
                <Sparkles className="h-3.5 w-3.5" />
                {(user.plan_tier as PlanTier) === "free" ? "Free Plan" : "Explorer"} &mdash; Upgrade
              </Button>
            </Link>
          </div>
        )}

        <div className="border-t p-3">
          <Button variant="ghost" className="w-full justify-start gap-3" onClick={() => logout()}>
            <LogOut className="h-4 w-4" />
            Log out
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
