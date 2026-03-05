import { cn } from "@/lib/utils"

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("rounded-md bg-gradient-to-r from-primary/[0.06] via-primary/[0.12] to-primary/[0.06] bg-[length:200%_100%] animate-[shimmer_1.5s_ease-in-out_infinite]", className)}
      {...props}
    />
  )
}

export { Skeleton }
