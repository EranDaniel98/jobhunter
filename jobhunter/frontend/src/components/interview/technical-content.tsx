"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronUp } from "lucide-react";

type TechQuestion = { question: string; answer: string; difficulty?: string };

function TechQCard({ q }: { q: TechQuestion }) {
  const [showAnswer, setShowAnswer] = useState(false);
  return (
    <Card>
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
      <CardContent className="space-y-2">
        <Button variant="ghost" size="sm" className="h-7 text-xs text-muted-foreground" onClick={() => setShowAnswer(!showAnswer)}>
          {showAnswer ? <><ChevronUp className="mr-1 h-3.5 w-3.5" />Hide Answer</> : <><ChevronDown className="mr-1 h-3.5 w-3.5" />Show Answer</>}
        </Button>
        {showAnswer && <p className="text-sm animate-in fade-in duration-200">{q.answer}</p>}
      </CardContent>
    </Card>
  );
}

export function TechnicalContent({ content }: { content: Record<string, unknown> }) {
  const topics = (content.topics as Array<{ topic: string; questions: TechQuestion[] }>) || [];
  if (topics.length === 0) return <p className="text-sm text-muted-foreground">No technical content generated yet.</p>;
  return (
    <div className="space-y-6">
      {topics.map((topic, i) => (
        <div key={i} className="space-y-3">
          <h4 className="font-semibold text-sm">{topic.topic}</h4>
          {topic.questions.map((q, j) => <TechQCard key={j} q={q} />)}
        </div>
      ))}
    </div>
  );
}
