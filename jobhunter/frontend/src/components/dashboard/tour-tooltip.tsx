"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";

interface TourTooltipProps {
  selector: string;
  position: "top" | "bottom" | "left" | "right";
  title: string;
  description: string;
  currentStep: number;
  totalSteps: number;
  onNext: () => void;
  onSkip: () => void;
  isLast: boolean;
}

export function TourTooltip({
  selector,
  position,
  title,
  description,
  currentStep,
  totalSteps,
  onNext,
  onSkip,
  isLast,
}: TourTooltipProps) {
  const [style, setStyle] = useState<React.CSSProperties>({});

  useEffect(() => {
    const el = document.querySelector(`[data-tour="${selector}"]`);
    if (!el) return;

    const update = () => {
      const r = el.getBoundingClientRect();
      const gap = 16;
      const tooltipWidth = 340;

      let top = 0;
      let left = 0;

      switch (position) {
        case "bottom":
          top = r.bottom + gap;
          left = r.left + r.width / 2 - tooltipWidth / 2;
          break;
        case "top":
          top = r.top - gap;
          left = r.left + r.width / 2 - tooltipWidth / 2;
          break;
        case "right":
          top = r.top + r.height / 2;
          left = r.right + gap;
          break;
        case "left":
          top = r.top + r.height / 2;
          left = r.left - gap - tooltipWidth;
          break;
      }

      // Clamp to viewport
      left = Math.max(16, Math.min(left, window.innerWidth - tooltipWidth - 16));
      top = Math.max(16, top);

      setStyle({
        position: "fixed",
        top,
        left,
        width: tooltipWidth,
        zIndex: 62,
        transform: position === "top" ? "translateY(-100%)" : position === "right" || position === "left" ? "translateY(-50%)" : undefined,
      });
    };

    // Wait for scroll to settle
    const timer = setTimeout(update, 450);
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("resize", update);
      clearTimeout(timer);
    };
  }, [selector, position]);

  return (
    <div style={style} className="animate-in fade-in slide-in-from-bottom-2 duration-300">
      <Card className="shadow-xl border-primary/20">
        <CardContent className="space-y-3 py-4">
          <div className="flex items-start justify-between">
            <h3 className="font-semibold text-base">{title}</h3>
            <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0" onClick={onSkip}>
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
          <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
          <div className="flex items-center justify-between pt-1">
            <span className="text-xs text-muted-foreground">
              {currentStep + 1} of {totalSteps}
            </span>
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" onClick={onSkip}>
                Skip tour
              </Button>
              <Button size="sm" onClick={onNext}>
                {isLast ? "Finish" : "Next"}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
