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
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    const timer = setTimeout(update, 400);

    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("resize", update);
      clearTimeout(timer);
    };
  }, [selector, padding]);

  if (!rect) return null;

  return (
    <div
      className="fixed z-[60] rounded-2xl pointer-events-none transition-all duration-500 ease-in-out"
      style={{
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height,
        boxShadow: "0 0 0 9999px rgba(0, 0, 0, 0.6), 0 0 20px 4px rgba(0, 0, 0, 0.3)",
      }}
    />
  );
}
