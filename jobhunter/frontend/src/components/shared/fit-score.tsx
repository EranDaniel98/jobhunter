import { cn, fitScoreBarColor } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";

interface FitScoreProps {
  score: number | null;
  showLabel?: boolean;
  className?: string;
}

export function FitScore({ score, showLabel = true, className }: FitScoreProps) {
  if (score === null) {
    return <span className="text-sm text-muted-foreground">N/A</span>;
  }

  const normalized = score > 1 ? score / 100 : score;
  const percentage = Math.round(normalized * 100);

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <Progress
        value={percentage}
        className={cn("h-2 w-20", fitScoreBarColor(normalized))}
      />
      {showLabel && (
        <span className="text-sm font-medium">{percentage}%</span>
      )}
    </div>
  );
}
