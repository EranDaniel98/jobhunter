import { Skeleton } from "@/components/ui/skeleton";

export default function InterviewPrepLoading() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading interview prep">
      <Skeleton className="h-9 w-48" />
      <Skeleton className="h-10 w-80" />
      <div className="rounded-lg border p-6">
        <Skeleton className="h-5 w-40 mb-4" />
        <div className="flex gap-3 flex-wrap">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex flex-col items-center gap-2">
              <Skeleton className="h-12 w-12 rounded-full" />
              <Skeleton className="h-3 w-16" />
            </div>
          ))}
        </div>
      </div>
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-4 flex items-center gap-3">
            <Skeleton className="h-10 w-10 rounded" />
            <div className="flex-1 space-y-1.5">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-32" />
            </div>
            <Skeleton className="h-6 w-20" />
          </div>
        ))}
      </div>
    </div>
  );
}
