"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronUp } from "lucide-react";

type Story = { situation: string; task: string; action: string; result: string; question?: string };

function StoryCard({ story, index }: { story: Story; index: number }) {
  const [showAnswer, setShowAnswer] = useState(false);
  return (
    <Card>
      <CardHeader className="pb-2">
        {story.question && (
          <CardDescription className="text-sm font-medium text-foreground">{story.question}</CardDescription>
        )}
        <CardTitle className="text-xs text-muted-foreground">STAR Story #{index + 1}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <Button variant="ghost" size="sm" className="h-7 text-xs text-muted-foreground" onClick={() => setShowAnswer(!showAnswer)}>
          {showAnswer ? <><ChevronUp className="mr-1 h-3.5 w-3.5" />Hide Answer</> : <><ChevronDown className="mr-1 h-3.5 w-3.5" />Show STAR Answer</>}
        </Button>
        {showAnswer && (
          <div className="space-y-2 text-sm animate-in fade-in duration-200">
            <div><span className="font-semibold text-chart-1">Situation: </span>{story.situation}</div>
            <div><span className="font-semibold text-chart-2">Task: </span>{story.task}</div>
            <div><span className="font-semibold text-chart-3">Action: </span>{story.action}</div>
            <div><span className="font-semibold text-chart-4">Result: </span>{story.result}</div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function BehavioralContent({ content }: { content: Record<string, unknown> }) {
  const stories = (content.stories as Story[]) || [];
  if (stories.length === 0) return <p className="text-sm text-muted-foreground">No behavioral stories generated yet.</p>;
  return (
    <div className="space-y-4">
      {stories.map((story, i) => <StoryCard key={i} story={story} index={i} />)}
    </div>
  );
}
