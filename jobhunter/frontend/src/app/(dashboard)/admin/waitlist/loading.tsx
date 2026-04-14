import { Skeleton } from "@/components/ui/skeleton";

export default function WaitlistLoading() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading waitlist">
      <Skeleton className="h-9 w-40" />
      <div className="grid gap-4 grid-cols-2 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border p-4 space-y-2">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-8 w-12" />
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-9 w-40" />
      </div>
      <div className="rounded-lg border">
        <div className="border-b p-3 flex gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-4 flex-1" />
          ))}
        </div>
        {Array.from({ length: 10 }).map((_, i) => (
          <div key={i} className="border-b p-3 flex gap-4 items-center">
            <Skeleton className="h-4 w-4" />
            {Array.from({ length: 4 }).map((_, j) => (
              <Skeleton key={j} className="h-5 flex-1" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
