import {
  LayoutDashboard, FileText, Building2, Mail, GraduationCap,
  FileCheck, ClipboardCheck, BarChart3, Settings, Shield,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  badge?: boolean;
}

export interface NavSection {
  label: string;
  items: NavItem[];
}

export const navSections: NavSection[] = [
  {
    label: "Core",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/resume", label: "Resume & DNA", icon: FileText },
      { href: "/companies", label: "Companies", icon: Building2 },
    ],
  },
  {
    label: "Outreach",
    items: [
      { href: "/outreach", label: "Outreach", icon: Mail },
      { href: "/interview-prep", label: "Interview Prep", icon: GraduationCap },
      { href: "/apply", label: "Apply", icon: FileCheck },
      { href: "/approvals", label: "Approvals", icon: ClipboardCheck, badge: true },
    ],
  },
  {
    label: "Insights",
    items: [
      { href: "/analytics", label: "Analytics", icon: BarChart3 },
    ],
  },
  {
    label: "System",
    items: [
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

export const adminNavItem: NavItem = { href: "/admin", label: "Admin", icon: Shield };

export const allNavItems: NavItem[] = navSections.flatMap((s) => s.items);
