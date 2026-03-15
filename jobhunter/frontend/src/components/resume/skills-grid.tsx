import type { SkillResponse } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BadgeCheck, CircleDashed } from "lucide-react";

interface SkillsGridProps {
  skills: SkillResponse[];
}

const categoryColors: Record<string, string> = {
  explicit: "bg-secondary text-secondary-foreground",
  transferable: "bg-chart-4/15 text-chart-4",
  adjacent: "bg-chart-5/15 text-chart-5",
};

export function SkillsGrid({ skills }: SkillsGridProps) {
  if (!skills.length) return null;

  const grouped = skills.reduce<Record<string, SkillResponse[]>>((acc, skill) => {
    const cat = skill.category || "other";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(skill);
    return acc;
  }, {});

  return (
    <Card>
      <CardHeader>
        <CardTitle>Skills</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {Object.entries(grouped).map(([category, catSkills]) => (
          <div key={category}>
            <h4 className="mb-2 text-sm font-medium capitalize text-muted-foreground">
              {category} skills
            </h4>
            <div className="divide-y rounded-md border">
              {catSkills.map((skill) => (
                <div
                  key={skill.id}
                  className="flex items-center justify-between px-3 py-2.5 sm:px-4"
                >
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <span className="font-medium text-sm">{skill.name}</span>
                    {skill.evidence ? (
                      <span title="Evidence-backed"><BadgeCheck className="h-3.5 w-3.5 text-primary shrink-0" /></span>
                    ) : (
                      <span title="Inferred"><CircleDashed className="h-3.5 w-3.5 text-muted-foreground/50 shrink-0" /></span>
                    )}
                    {skill.proficiency && (
                      <span className="text-xs text-muted-foreground hidden sm:inline">{skill.proficiency}</span>
                    )}
                    {skill.years_experience !== null && (
                      <span className="text-xs text-muted-foreground hidden sm:inline">{skill.years_experience}y</span>
                    )}
                  </div>
                  <Badge className={`shrink-0 ${categoryColors[category] || "bg-muted text-muted-foreground"}`}>
                    {category}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
