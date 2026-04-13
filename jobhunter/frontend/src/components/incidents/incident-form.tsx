"use client";

import { useRef, useState } from "react";
import { Bug, HelpCircle, ImagePlus, Lightbulb, Loader2, MoreHorizontal, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { useSubmitIncident } from "@/lib/hooks/use-incidents";
import { useAuth } from "@/providers/auth-provider";

type Category = "bug" | "feature_request" | "question" | "other";

const CATEGORIES: { value: Category; label: string; icon: React.ReactNode; placeholder: string }[] = [
  { value: "bug", label: "Bug", icon: <Bug className="h-4 w-4" />, placeholder: "Steps to reproduce..." },
  { value: "feature_request", label: "Feature Request", icon: <Lightbulb className="h-4 w-4" />, placeholder: "What would you like to see?" },
  { value: "question", label: "Question", icon: <HelpCircle className="h-4 w-4" />, placeholder: "What do you need help with?" },
  { value: "other", label: "Other", icon: <MoreHorizontal className="h-4 w-4" />, placeholder: "Tell us more..." },
];

const MAX_FILES = 3;
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB

export interface IncidentFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  consoleErrors: React.RefObject<string[]>;
}

export function IncidentForm({ open, onOpenChange, consoleErrors }: IncidentFormProps) {
  const { user } = useAuth();
  const { mutate: submitIncident, isPending } = useSubmitIncident();

  const [category, setCategory] = useState<Category>("bug");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const currentCategory = CATEGORIES.find((c) => c.value === category)!;

  function resetForm() {
    setCategory("bug");
    setTitle("");
    setDescription("");
    setFiles([]);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(e.target.files ?? []);
    const valid = selected.filter((f) => f.size <= MAX_FILE_SIZE);
    const merged = [...files, ...valid].slice(0, MAX_FILES);
    setFiles(merged);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  function removeFile(index: number) {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const context = {
      email: user?.email ?? null,
      plan_tier: user?.plan_tier ?? null,
      page_url: window.location.href,
      browser: navigator.userAgent,
      os: navigator.platform,
      console_errors: consoleErrors.current ?? [],
    };

    const formData = new FormData();
    formData.append("category", category);
    formData.append("title", title);
    formData.append("description", description);
    formData.append("context", JSON.stringify(context));
    files.forEach((f) => formData.append("files", f));

    submitIncident(formData, {
      onSuccess: () => {
        resetForm();
        onOpenChange(false);
      },
    });
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-2xl overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Report an Incident</SheetTitle>
          <SheetDescription>Help us improve by sharing what happened.</SheetDescription>
        </SheetHeader>

        <form onSubmit={handleSubmit} className="mt-6 space-y-5">
          {/* Category */}
          <div className="space-y-2">
            <Label>Category</Label>
            <RadioGroup value={category} onValueChange={(v) => setCategory(v as Category)} className="grid grid-cols-2 gap-2">
              {CATEGORIES.map(({ value, label, icon }) => (
                <Label
                  key={value}
                  htmlFor={`cat-${value}`}
                  className="flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm font-normal transition-colors has-[input:checked]:border-primary has-[input:checked]:bg-primary/5"
                >
                  <RadioGroupItem id={`cat-${value}`} value={value} className="sr-only" />
                  {icon}
                  {label}
                </Label>
              ))}
            </RadioGroup>
          </div>

          {/* Title */}
          <div className="space-y-2">
            <Label htmlFor="incident-title">Title <span className="text-destructive">*</span></Label>
            <Input
              id="incident-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={200}
              placeholder="Brief summary"
              required
            />
          </div>

          {/* Description */}
          <div className="space-y-2">
            <Label htmlFor="incident-description">Description <span className="text-destructive">*</span></Label>
            <Textarea
              id="incident-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={5000}
              placeholder={currentCategory.placeholder}
              required
              rows={5}
            />
          </div>

          {/* Attachments */}
          <div className="space-y-2">
            <Label>Attachments <span className="text-muted-foreground text-xs">(max {MAX_FILES}, 5 MB each)</span></Label>
            {files.length > 0 && (
              <ul className="space-y-1">
                {files.map((f, i) => (
                  <li key={i} className="flex items-center justify-between rounded-md border px-3 py-1.5 text-sm">
                    <span className="truncate max-w-[calc(100%-2rem)]">{f.name}</span>
                    <button type="button" onClick={() => removeFile(i)} className="ml-2 text-muted-foreground hover:text-destructive">
                      <X className="h-4 w-4" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {files.length < MAX_FILES && (
              <>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  multiple
                  className="hidden"
                  onChange={handleFileChange}
                />
                <Button type="button" variant="outline" size="sm" className="gap-2" onClick={() => fileInputRef.current?.click()}>
                  <ImagePlus className="h-4 w-4" />
                  Add image
                </Button>
              </>
            )}
          </div>

          {/* Submit */}
          <Button type="submit" className="w-full" disabled={isPending}>
            {isPending ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Submitting…</> : "Submit"}
          </Button>
        </form>
      </SheetContent>
    </Sheet>
  );
}
