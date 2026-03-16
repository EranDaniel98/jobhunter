"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { MobileNav } from "@/components/layout/mobile-nav";
import { Footer } from "@/components/layout/footer";
import { CommandMenu } from "@/components/layout/command-menu";
import { TourOverlay } from "@/components/dashboard/tour-overlay";

import { useWebSocket } from "@/lib/hooks/use-websocket";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, isOnboarded } = useAuth();
  const router = useRouter();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { lastEvent } = useWebSocket();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
    if (!isLoading && isAuthenticated && !isOnboarded) {
      router.replace("/onboarding");
    }
  }, [isAuthenticated, isLoading, isOnboarded, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!isAuthenticated || !isOnboarded) return null;

  return (
    <div className="min-h-screen bg-background">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground focus:shadow-lg"
      >
        Skip to main content
      </a>
      <Sidebar lastEvent={lastEvent} onCollapseChange={setSidebarCollapsed} />
      <MobileNav open={mobileNavOpen} onOpenChange={setMobileNavOpen} lastEvent={lastEvent} />
      <CommandMenu />
      <div className={sidebarCollapsed ? "lg:pl-16" : "lg:pl-64"}>
        <Header onMenuClick={() => setMobileNavOpen(true)} lastEvent={lastEvent} />
        <main id="main-content" className="p-4 md:p-6 lg:p-8">{children}</main>
        <Footer />
      </div>
      <TourOverlay />
    </div>
  );
}
