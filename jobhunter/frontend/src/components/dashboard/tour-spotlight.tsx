"use client";

import { useEffect, useState } from "react";

interface SpotlightRect {
  top: number;
  left: number;
  width: number;
  height: number;
}

interface TourSpotlightProps {
  selector: string;
  padding?: number;
}

export function TourSpotlight({ selector, padding = 8 }: TourSpotlightProps) {
  const [rect, setRect] = useState<SpotlightRect | null>(null);

  useEffect(() => {
    const el = document.querySelector(`[data-tour="${selector}"]`);
    if (!el) return;

    const update = () => {
      const r = el.getBoundingClientRect();
      setRect({
        top: r.top - padding,
        left: r.left - padding,
        width: r.width + padding * 2,
        height: r.height + padding * 2,
      });
    };

    update();
    // Scroll element into view
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    // Recalculate after scroll settles
    const timer = setTimeout(update, 400);

    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("resize", update);
      clearTimeout(timer);
    };
  }, [selector, padding]);

  if (!rect) return null;

  return (
    <>
      {/* Dimmed backdrop with cutout */}
      <div
        className="fixed inset-0 z-[60] transition-all duration-300"
        style={{
          background: `radial-gradient(
            ellipse at ${rect.left + rect.width / 2}px ${rect.top + rect.height / 2}px,
            transparent ${Math.max(rect.width, rect.height) * 0.6}px,
            rgba(0, 0, 0, 0.6) ${Math.max(rect.width, rect.height) * 0.8}px
          )`,
        }}
      />
      {/* Highlight border around target */}
      <div
        className="fixed z-[61] rounded-lg border-2 border-primary shadow-[0_0_0_4px_rgba(var(--primary),0.15)] pointer-events-none transition-all duration-300"
        style={{
          top: rect.top,
          left: rect.left,
          width: rect.width,
          height: rect.height,
        }}
      />
    </>
  );
}
