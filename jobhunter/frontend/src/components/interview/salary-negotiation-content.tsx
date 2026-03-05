import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function SalaryNegotiationContent({ content }: { content: Record<string, unknown> }) {
  const range = content.salary_range as { low: number; mid: number; high: number } | undefined;
  const strategies = (content.strategies as string[]) || [];
  const talking_points = (content.talking_points as string[]) || [];
  return (
    <div className="space-y-4">
      {range && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Estimated Salary Range</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-6 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">Low</p>
                <p className="font-semibold">${range.low?.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Mid</p>
                <p className="font-semibold text-primary">${range.mid?.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">High</p>
                <p className="font-semibold">${range.high?.toLocaleString()}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
      {strategies.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Negotiation Strategies</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc pl-4 space-y-1 text-sm">
              {strategies.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
      {talking_points.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Talking Points</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc pl-4 space-y-1 text-sm">
              {talking_points.map((tp, i) => (
                <li key={i}>{tp}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
      {!range && strategies.length === 0 && talking_points.length === 0 && (
        <p className="text-sm text-muted-foreground">No salary negotiation content generated yet.</p>
      )}
    </div>
  );
}
