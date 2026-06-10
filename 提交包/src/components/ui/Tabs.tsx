import { cn } from '../../shared/cn';

export interface TabItem<T extends string> {
  id: T;
  label: string;
}

export interface TabsProps<T extends string> {
  items: TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
}

export function Tabs<T extends string>({ items, value, onChange }: TabsProps<T>) {
  return (
    <div className="flex flex-wrap gap-1 rounded-xl border border-border bg-sidebar p-1">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          className={cn(
            'min-h-10 rounded-md border px-4 text-sm font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-primary/30',
            value === item.id ? 'border-border bg-card text-text-primary shadow-sm' : 'border-transparent text-text-secondary hover:bg-card/60 hover:text-text-primary',
          )}
          onClick={() => onChange(item.id)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
