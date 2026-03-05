import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function TechnicalContent({ content }: { content: Record<string, unknown> }) {
  const topics = (content.topics as Array<{ topic: string; questions: Array<{ question: string; answer: string; difficulty?: string }> }>) || [];
  if (topics.length === 0) {
    return <p className="text-sm text-muted-foreground">No technical content generated yet.</p>;
  }
  return (
    <div className="space-y-6">
      {topics.map((topic, i) => (
        <div key={i} className="space-y-3">
          <h4 className="font-semibold text-sm">{topic.topic}</h4>
          {topic.questions.map((q, j) => (
            <Card key={j}>
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <CardTitle className="text-sm">{q.question}</CardTitle>
                  {q.difficulty && (
                    <Badge variant={q.difficulty === "hard" ? "destructive" : q.difficulty === "medium" ? "default" : "secondary"} className="text-xs">
                      {q.difficulty}
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm">{q.answer}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      ))}
    </div>
  );
}
