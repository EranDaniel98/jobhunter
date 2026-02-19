"use client";

import { useCallback, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import * as candidatesApi from "@/lib/api/candidates";
import { Card, CardContent } from "@/components/ui/card";
import { toast } from "sonner";
import { Upload, Loader2, CheckCircle2 } from "lucide-react";

interface UploadZoneProps {
  onUploadSuccess?: () => void;
}

export function UploadZone({ onUploadSuccess }: UploadZoneProps) {
  const [dragOver, setDragOver] = useState(false);

  const uploadMutation = useMutation({
    mutationFn: candidatesApi.uploadResume,
    onSuccess: () => {
      toast.success("Resume uploaded! Processing your DNA profile...");
      onUploadSuccess?.();
    },
    onError: (err: unknown) => {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Upload failed";
      toast.error(message);
    },
  });

  const handleFile = useCallback(
    (file: File) => {
      const ext = file.name.split(".").pop()?.toLowerCase();
      if (!ext || !["pdf", "docx"].includes(ext)) {
        toast.error("Only PDF and DOCX files are supported");
        return;
      }
      if (file.size > 10 * 1024 * 1024) {
        toast.error("File too large (max 10MB)");
        return;
      }
      uploadMutation.mutate(file);
    },
    [uploadMutation]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const handleInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  return (
    <Card>
      <CardContent className="p-0">
        <label
          className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors ${
            dragOver
              ? "border-primary bg-primary/5"
              : "border-muted-foreground/25 hover:border-primary/50"
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
        >
          {uploadMutation.isPending ? (
            <>
              <Loader2 className="mb-2 h-10 w-10 animate-spin text-primary" />
              <p className="text-sm font-medium">Uploading & processing...</p>
            </>
          ) : uploadMutation.isSuccess ? (
            <>
              <CheckCircle2 className="mb-2 h-10 w-10 text-green-500" />
              <p className="text-sm font-medium">Resume uploaded successfully</p>
              <p className="text-xs text-muted-foreground">Drop another file to replace</p>
            </>
          ) : (
            <>
              <Upload className="mb-2 h-10 w-10 text-muted-foreground" />
              <p className="text-sm font-medium">Drop your resume here or click to browse</p>
              <p className="text-xs text-muted-foreground">PDF or DOCX, max 10MB</p>
            </>
          )}
          <input
            type="file"
            accept=".pdf,.docx"
            className="hidden"
            onChange={handleInput}
          />
        </label>
      </CardContent>
    </Card>
  );
}
