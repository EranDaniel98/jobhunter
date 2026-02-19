import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  COMPANY_STATUS_COLORS,
  COMPANY_STATUS_LABELS,
  MESSAGE_STATUS_COLORS,
  MESSAGE_STATUS_LABELS,
  RESEARCH_STATUS_COLORS,
  RESEARCH_STATUS_LABELS,
} from "@/lib/constants";

type BadgeType = "company" | "research" | "message";

interface StatusBadgeProps {
  type: BadgeType;
  status: string;
  className?: string;
}

const colorMaps: Record<BadgeType, Record<string, string>> = {
  company: COMPANY_STATUS_COLORS,
  research: RESEARCH_STATUS_COLORS,
  message: MESSAGE_STATUS_COLORS,
};

const labelMaps: Record<BadgeType, Record<string, string>> = {
  company: COMPANY_STATUS_LABELS,
  research: RESEARCH_STATUS_LABELS,
  message: MESSAGE_STATUS_LABELS,
};

export function StatusBadge({ type, status, className }: StatusBadgeProps) {
  const colors = colorMaps[type]?.[status] || "bg-gray-100 text-gray-800";
  const label = labelMaps[type]?.[status] || status;

  return (
    <Badge variant="secondary" className={cn("font-medium", colors, className)}>
      {label}
    </Badge>
  );
}
