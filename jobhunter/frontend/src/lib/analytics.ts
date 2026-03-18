/**
 * Track a custom event in Plausible Analytics.
 *
 * No-ops gracefully when Plausible is not loaded (local dev, ad-blockers).
 * See: https://plausible.io/docs/custom-event-goals
 */
export function trackEvent(
  name: string,
  props: Record<string, string | number | boolean> = {}
): void {
  if (typeof window !== "undefined" && typeof window.plausible === "function") {
    window.plausible(name, { props });
  }
}

declare global {
  interface Window {
    plausible?: (
      event: string,
      options?: { props?: Record<string, string | number | boolean> }
    ) => void;
  }
}
