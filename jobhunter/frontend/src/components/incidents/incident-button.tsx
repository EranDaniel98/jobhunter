"use client";

import { useState } from "react";
import { MessageSquarePlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { IncidentForm } from "./incident-form";

interface IncidentButtonProps {
  consoleErrors: React.RefObject<string[]>;
}

export function IncidentButton({ consoleErrors }: IncidentButtonProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button
        variant="default"
        size="icon"
        className="fixed bottom-6 right-6 z-40 h-12 w-12 rounded-full shadow-lg"
        onClick={() => setOpen(true)}
        aria-label="Report an incident"
      >
        <MessageSquarePlus className="h-5 w-5" />
      </Button>
      <IncidentForm open={open} onOpenChange={setOpen} consoleErrors={consoleErrors} />
    </>
  );
}
