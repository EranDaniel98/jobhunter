import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function BehavioralContent({ content }: { content: Record<string, unknown> }) {
  const stories = (content.stories as Array<{ situation: string; task: string; action: string; result: string; question?: string }>) || [];
  if (stories.length === 0) {
    return <p className="text-sm text-muted-foreground">No behavioral stories generated yet.</p>;
  }
  return (
    <div className="space-y-4">
      {stories.map((story, i) => (
        <Card key={i}>
          <CardHeader className="pb-2">
            {story.question && (
              <CardDescription className="text-sm font-medium text-foreground">{story.question}</CardDescription>
            )}
            <CardTitle className="text-xs text-muted-foreground">STAR Story #{i + 1}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div>
              <span className="font-semibold text-chart-1">Situation: </span>
              {story.situation}
            </div>
            <div>
              <span className="font-semibold text-chart-2">Task: </span>
              {story.task}
            </div>
            <div>
              <span className="font-semibold text-chart-3">Action: </span>
              {story.action}
            </div>
            <div>
              <span className="font-semibold text-chart-4">Result: </span>
              {story.result}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
