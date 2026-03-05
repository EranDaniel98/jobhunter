export function GenericContent({ data }: { data: Record<string, unknown> }) {
  return (
    <dl className="space-y-3">
      {Object.entries(data).map(([key, value]) => (
        <div key={key}>
          <dt className="text-sm font-medium capitalize">{key.replace(/_/g, " ")}</dt>
          <dd className="text-sm text-muted-foreground mt-0.5">
            {typeof value === "string" ? value : Array.isArray(value) ? value.join(", ") : String(value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}
