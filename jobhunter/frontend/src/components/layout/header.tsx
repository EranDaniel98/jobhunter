"use client";

import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/layout/theme-toggle";

interface HeaderProps {
  onMenuClick: () => void;
}

export function Header({ onMenuClick }: HeaderProps) {
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-4 border-b bg-card px-4 lg:hidden">
      <Button variant="ghost" size="icon" onClick={onMenuClick} aria-label="Open navigation menu">
        <Menu className="h-5 w-5" />
      </Button>
      <span className="flex-1 text-lg font-semibold">JobHunter AI</span>
      <ThemeToggle />
    </header>
  );
}
