"use client";

import Link from "next/link";
import { useTheme } from "next-themes";
import { useState, useEffect } from "react";
import {
  Crosshair,
  Sun,
  Moon,
  Menu,
  X,
} from "lucide-react";

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return <div className="h-9 w-9" />;
  return (
    <button
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
      className="rounded-lg p-2 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
      aria-label="Toggle theme"
    >
      {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
    </button>
  );
}

const NAV_LINKS = [
  { href: "/#features", label: "Features" },
  { href: "/pricing", label: "Pricing" },
  { href: "/about", label: "About" },
];

export function MarketingShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Navbar */}
      <header className="sticky top-0 z-40 w-full border-b border-border/60 bg-background/80 backdrop-blur-lg">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 no-underline" data-slot="logo">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Crosshair className="h-5 w-5" />
            </div>
            <span className="text-lg font-bold text-foreground">
              Job<span className="text-primary">Hunter</span> AI
            </span>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-1">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground transition-colors no-underline"
                data-slot="nav"
              >
                {link.label}
              </Link>
            ))}
          </nav>

          {/* Right side */}
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Link
              href="/login"
              className="hidden sm:inline-flex rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-accent transition-colors no-underline"
              data-slot="nav"
            >
              Log in
            </Link>
            <Link
              href="/#waitlist"
              className="hidden sm:inline-flex rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors no-underline"
              data-slot="nav"
            >
              Get Early Access
            </Link>

            {/* Mobile hamburger */}
            <button
              className="md:hidden rounded-lg p-2 text-muted-foreground hover:bg-accent"
              onClick={() => setMobileOpen(!mobileOpen)}
              aria-label="Toggle menu"
            >
              {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <div className="border-t border-border md:hidden">
            <div className="space-y-1 px-4 py-3">
              {NAV_LINKS.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setMobileOpen(false)}
                  className="block rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground transition-colors no-underline"
                  data-slot="nav"
                >
                  {link.label}
                </Link>
              ))}
              <Link
                href="/login"
                className="block rounded-lg px-3 py-2 text-sm font-medium text-foreground hover:bg-accent transition-colors no-underline"
                data-slot="nav"
              >
                Log in
              </Link>
            </div>
          </div>
        )}
      </header>

      {/* Main content */}
      <main className="flex-1">{children}</main>

      {/* Footer */}
      <footer className="border-t border-border bg-card">
        <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {/* Brand */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                  <Crosshair className="h-4 w-4" />
                </div>
                <span className="font-bold text-foreground">
                  Job<span className="text-primary">Hunter</span> AI
                </span>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                AI-powered job search automation. From resume optimization to
                personalized outreach, we handle the grind so you can focus on
                landing the right role.
              </p>
            </div>

            {/* Product */}
            <div className="space-y-3">
              <h4 className="text-sm font-semibold text-foreground">Product</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><Link href="/#features" className="hover:text-foreground transition-colors no-underline" data-slot="nav">Features</Link></li>
                <li><Link href="/pricing" className="hover:text-foreground transition-colors no-underline" data-slot="nav">Pricing</Link></li>
                <li><Link href="/#waitlist" className="hover:text-foreground transition-colors no-underline" data-slot="nav">Early Access</Link></li>
              </ul>
            </div>

            {/* Company */}
            <div className="space-y-3">
              <h4 className="text-sm font-semibold text-foreground">Company</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><Link href="/about" className="hover:text-foreground transition-colors no-underline" data-slot="nav">About</Link></li>
              </ul>
            </div>

            {/* Contact */}
            <div className="space-y-3">
              <h4 className="text-sm font-semibold text-foreground">Contact</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><a href="mailto:support@hunter-job.com" className="hover:text-foreground transition-colors no-underline">support@hunter-job.com</a></li>
              </ul>
            </div>
          </div>

          <div className="mt-10 border-t border-border pt-6 text-center text-sm text-muted-foreground">
            &copy; {new Date().getFullYear()} JobHunter AI. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  );
}
