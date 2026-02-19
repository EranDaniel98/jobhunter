import type { SkillResponse } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface SkillsGridProps {
  skills: SkillResponse[];
}

const categoryColors: Record<string, string> = {
  explicit: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  transferable: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
  adjacent: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300",
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
      <CardContent className="space-y-6">
        {Object.entries(grouped).map(([category, catSkills]) => (
          <div key={category}>
            <h4 className="mb-3 text-sm font-medium capitalize text-muted-foreground">
              {category} skills
            </h4>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {catSkills.map((skill) => (
                <div
                  key={skill.id}
                  className="rounded-lg border p-3 space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm">{skill.name}</span>
                    <Badge className={categoryColors[category] || "bg-gray-100 text-gray-800"}>
                      {category}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground">
                    {skill.proficiency && <span>{skill.proficiency}</span>}
                    {skill.years_experience !== null && (
                      <span>{skill.years_experience}y exp</span>
                    )}
                  </div>
                  {skill.evidence && (
                    <p className="text-xs text-muted-foreground line-clamp-2">
                      {skill.evidence}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
