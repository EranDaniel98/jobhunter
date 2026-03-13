"use client";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Loader2 } from "lucide-react";
import type { OutreachMessageResponse } from "@/lib/types";
import { useDeleteMessage } from "@/lib/hooks/use-outreach";
import { toast } from "sonner";

interface VariantPickerProps {
  variants: OutreachMessageResponse[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPicked: () => void;
}

export function VariantPicker({ variants, open, onOpenChange, onPicked }: VariantPickerProps) {
  const deleteMutation = useDeleteMessage();

  function pickVariant(keep: OutreachMessageResponse, discard: OutreachMessageResponse) {
    deleteMutation.mutate(discard.id, {
      onSuccess: () => {
        toast.success(`Kept ${keep.variant || "message"} variant as draft`);
        onPicked();
        onOpenChange(false);
      },
      onError: () => {
        // Even if delete fails, the pick is fine - user has both drafts
        onPicked();
        onOpenChange(false);
      },
    });
  }

  if (variants.length < 2) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Pick a message variant</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 md:grid-cols-2">
          {variants.map((v, i) => {
            const other = variants[1 - i];
            return (
              <div key={v.id} className="flex flex-col gap-3 rounded-lg border p-4">
                <Badge variant="secondary" className="w-fit capitalize">
                  {v.variant || `Variant ${i + 1}`}
                </Badge>
                {v.subject && (
                  <p className="text-sm font-medium">{v.subject}</p>
                )}
                <p className="text-sm text-muted-foreground whitespace-pre-wrap flex-1">
                  {v.body}
                </p>
                <Button
                  size="sm"
                  onClick={() => pickVariant(v, other)}
                  disabled={deleteMutation.isPending}
                >
                  {deleteMutation.isPending && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
                  Use this
                </Button>
              </div>
            );
          })}
        </div>
      </DialogContent>
    </Dialog>
  );
}
