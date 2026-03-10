"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronUp } from "lucide-react";

function QACard({ qa, index }: { qa: { question: string; answer: string; tips?: string }; index: number }) {
  const [showAnswer, setShowAnswer] = useState(false);

  return (
    <Card key={index}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Q: {qa.question}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <Button
          variant="ghost"
          size="sm"
          className="h-7 text-xs text-muted-foreground"
          onClick={() => setShowAnswer(!showAnswer)}
        >
          {showAnswer ? (
            <><ChevronUp className="mr-1 h-3.5 w-3.5" />Hide Answer</>
          ) : (
            <><ChevronDown className="mr-1 h-3.5 w-3.5" />Show Answer</>
          )}
        </Button>
        {showAnswer && (
          <div className="space-y-2 animate-in fade-in duration-200">
            <p className="text-sm">{qa.answer}</p>
            {qa.tips && (
              <p className="text-xs text-muted-foreground italic">Tip: {qa.tips}</p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function CompanyQAContent({ content }: { content: Record<string, unknown> }) {
  const questions = (content.questions as Array<{ question: string; answer: string; tips?: string }>) || [];
  if (questions.length === 0) {
    return <p className="text-sm text-muted-foreground">No Q&A content generated yet.</p>;
  }
  return (
    <div className="space-y-4">
      {questions.map((qa, i) => (
        <QACard key={i} qa={qa} index={i} />
      ))}
    </div>
  );
}
