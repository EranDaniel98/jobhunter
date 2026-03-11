import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t px-4 py-3 flex items-center justify-between text-xs text-muted-foreground">
      <span>JobHunter AI v{process.env.NEXT_PUBLIC_APP_VERSION || "0.2.0"}</span>
      <div className="flex items-center gap-4">
        <Link href="/settings" className="hover:text-foreground transition-colors">Settings</Link>
        <button
          onClick={() => window.dispatchEvent(new Event("open-command-menu"))}
          className="hover:text-foreground transition-colors flex items-center gap-1"
        >
          <kbd className="font-mono">{typeof navigator !== "undefined" && /Mac/.test(navigator.userAgent) ? "\u2318" : "Ctrl"}+K</kbd>
          <span>Search</span>
        </button>
      </div>
    </footer>
  );
}
