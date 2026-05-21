import { Clapperboard, Sticker, Type } from 'lucide-react';
import type { PackagingStructure as Packaging } from '../../shared/types';

export function PackagingStructure({ data }: { data: Packaging }) {
  const cards = [
    { title: '\u5b57\u5e55\u6837\u5f0f', icon: Type, rows: data.subtitleStyle },
    { title: '\u8f6c\u573a\u7c7b\u578b', icon: Clapperboard, rows: data.transitions },
    { title: '\u53e0\u52a0\u5143\u7d20', icon: Sticker, rows: data.overlays },
  ];
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <div key={card.title} className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <Icon className="h-6 w-6 text-primary" />
            <h3 className="mt-4 font-semibold">{card.title}</h3>
            <ul className="mt-3 space-y-2 text-sm text-text-secondary">
              {card.rows.map((row) => <li key={row}>{row}</li>)}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
