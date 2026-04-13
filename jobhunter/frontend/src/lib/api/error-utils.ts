import { toast } from "sonner";

interface ApiError {
  response?: {
    status?: number;
    data?: { detail?: string | Record<string, unknown> | Array<{ msg: string; loc: string[] }> };
  };
  message?: string;
}

const QUOTA_LABELS: Record<string, string> = {
  discovery: "company discovery",
  research: "company research",
  hunter: "contact lookup",
  email: "email",
  openai: "AI call",
};

function isQuotaDetail(detail: unknown): detail is { quota_type: string; limit: number; message: string } {
  return (
    typeof detail === "object" &&
    detail !== null &&
    "quota_type" in detail &&
    "limit" in detail
  );
}

export function getErrorMessage(err: unknown, fallback = "Something went wrong"): string {
  const apiErr = err as ApiError;

  if (!apiErr?.response) {
    return "Network error - check your connection and try again";
  }

  const status = apiErr.response.status;
  const detail = apiErr.response.data?.detail;

  if (status === 422 && Array.isArray(detail)) {
    return detail.map((d) => d.msg).join(". ");
  }

  // Structured quota exceeded response
  if (status === 429 && isQuotaDetail(detail)) {
    const label = QUOTA_LABELS[detail.quota_type] || detail.quota_type;
    return `Daily ${label} limit (${detail.limit}) reached. Try again tomorrow.`;
  }

  if (typeof detail === "string") return detail;

  if (status === 401) return "Session expired - please log in again";
  if (status === 403) return "You don't have permission to do that";
  if (status === 404) return "Not found - it may have been deleted";
  if (status === 409) return "Conflict - this already exists";
  if (status === 429) return "Too many requests - please slow down";
  if (status && status >= 500) return "Server error - please try again later";

  return fallback;
}

export function toastError(err: unknown, fallback?: string) {
  toast.error(getErrorMessage(err, fallback));
}

