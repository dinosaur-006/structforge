interface SourceLegendProps {
  items: Array<{ color: string; label: string }>;
}

export function SourceLegend({ items }: SourceLegendProps) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-2">
      {items.map((item) => (
        <span key={item.label} className="inline-flex items-center gap-2 text-xs font-medium text-text-secondary">
          <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
          {item.label}
        </span>
      ))}
    </div>
  );
}
