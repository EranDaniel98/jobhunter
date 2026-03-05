import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function CompanyQAContent({ content }: { content: Record<string, unknown> }) {
  const questions = (content.questions as Array<{ question: string; answer: string; tips?: string }>) || [];
  if (questions.length === 0) {
    return <p className="text-sm text-muted-foreground">No Q&A content generated yet.</p>;
  }
  return (
    <div className="space-y-4">
      {questions.map((qa, i) => (
        <Card key={i}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Q: {qa.question}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-sm">{qa.answer}</p>
            {qa.tips && (
              <p className="text-xs text-muted-foreground italic">Tip: {qa.tips}</p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
