"use client";

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
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { NotificationCenter } from "@/components/layout/notification-center";
import { useApprovalCount } from "@/lib/hooks/use-approvals";
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

interface SidebarProps {
  lastEvent?: { type: string; data: Record<string, unknown> } | null;
}

export function Sidebar({ lastEvent = null }: SidebarProps) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { data: approvalCount } = useApprovalCount();

  const initials = user?.full_name
    ?.split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2) || "?";

  return (
    <aside className="hidden lg:flex lg:w-64 lg:flex-col lg:fixed lg:inset-y-0 border-r bg-card" role="navigation" aria-label="Main navigation">
      <div className="flex h-16 items-center gap-2 border-b px-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
          <Briefcase className="h-4 w-4 text-primary-foreground" />
        </div>
        <span className="text-lg font-semibold">JobHunter AI</span>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4">
        {[...navItems, ...(user?.is_admin ? [adminNavItem] : [])].map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link key={item.href} href={item.href}>
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

      <div className="border-t p-3 flex items-center gap-2">
        <NotificationCenter lastEvent={lastEvent} />
        <ThemeToggle />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="w-full justify-start gap-3">
              <Avatar className="h-7 w-7">
                <AvatarFallback className="text-xs">{initials}</AvatarFallback>
              </Avatar>
              <span className="truncate text-sm">{user?.full_name}</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-56">
            <DropdownMenuItem onClick={() => logout()}>
              <LogOut className="mr-2 h-4 w-4" />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </aside>
  );
}
