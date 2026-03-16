interface PageHeaderProps {
  title: string;
  description?: string;
  children?: React.ReactNode;
  dataTour?: string;
}

export function PageHeader({ title, description, children, dataTour }: PageHeaderProps) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between" {...(dataTour ? { "data-tour": dataTour } : {})}>
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-primary shrink-0" />
          {title}
        </h1>
        {description && <p className="text-muted-foreground">{description}</p>}
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  );
}
