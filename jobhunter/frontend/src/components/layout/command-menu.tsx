"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useCompanies } from "@/lib/hooks/use-companies";
import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandSeparator,
} from "@/components/ui/command";
import {
  LayoutDashboard, FileText, Building2, Mail, ClipboardCheck,
  BarChart3, Settings, Upload, Search,
} from "lucide-react";

const pages = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Resume & DNA", href: "/resume", icon: FileText },
  { label: "Companies", href: "/companies", icon: Building2 },
  { label: "Outreach", href: "/outreach", icon: Mail },
  { label: "Approvals", href: "/approvals", icon: ClipboardCheck },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
  { label: "Settings", href: "/settings", icon: Settings },
];

const actions = [
  { label: "Upload Resume", href: "/resume", icon: Upload },
  { label: "Discover Companies", href: "/companies", icon: Search },
];

export function CommandMenu() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const { data: companiesData } = useCompanies();

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  const go = useCallback((href: string) => {
    setOpen(false);
    router.push(href);
  }, [router]);

  const companies = companiesData?.companies || [];

  return (
    <CommandDialog
      open={open}
      onOpenChange={setOpen}
      title="Search"
      description="Search pages, companies, and actions"
    >
      <CommandInput placeholder="Type to search..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup heading="Pages">
          {pages.map((page) => (
            <CommandItem key={page.href} onSelect={() => go(page.href)}>
              <page.icon className="mr-2 h-4 w-4" />
              {page.label}
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Quick Actions">
          {actions.map((action) => (
            <CommandItem key={action.label} onSelect={() => go(action.href)}>
              <action.icon className="mr-2 h-4 w-4" />
              {action.label}
            </CommandItem>
          ))}
        </CommandGroup>
        {companies.length > 0 && (
          <>
            <CommandSeparator />
            <CommandGroup heading="Companies">
              {companies.slice(0, 10).map((c) => (
                <CommandItem key={c.id} onSelect={() => go(`/companies/${c.id}`)}>
                  <Building2 className="mr-2 h-4 w-4" />
                  <span>{c.name}</span>
                  <span className="ml-2 text-xs text-muted-foreground">{c.domain}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        )}
      </CommandList>
    </CommandDialog>
  );
}
