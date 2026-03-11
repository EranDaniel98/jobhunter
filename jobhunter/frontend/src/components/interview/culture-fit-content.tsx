import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function CultureFitContent({ content }: { content: Record<string, unknown> }) {
  const values = (content.values as Array<{ value: string; description: string; how_to_demonstrate: string }>) || [];
  const tips = (content.tips as string[]) || [];
  return (
    <div className="space-y-4">
      {values.length > 0 && (
        <div className="space-y-3">
          <h4 className="font-semibold text-sm">Company Values & How to Align</h4>
          {values.map((v, i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">{v.value}</CardTitle>
                <CardDescription className="text-xs">{v.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm">{v.how_to_demonstrate}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      {tips.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">General Tips</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc pl-4 space-y-1 text-sm">
              {tips.map((tip, i) => (
                <li key={i}>{tip}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
      {values.length === 0 && tips.length === 0 && (
        <p className="text-sm text-muted-foreground">No culture fit content generated yet.</p>
      )}
    </div>
  );
}
