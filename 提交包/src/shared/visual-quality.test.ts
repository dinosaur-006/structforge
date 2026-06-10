import { describe, expect, it } from 'vitest';

const sourceModules = import.meta.glob<string>('/src/**/*.{ts,tsx,css}', { query: '?raw', import: 'default', eager: true });

describe('visual quality guardrails', () => {
  it('keeps the premium UI free of emoji, garbled separators, and neon utilities', () => {
    const bannedChars = [
      String.fromCodePoint(0x8def),
      String.fromCodePoint(0x922b),
    ];
    const bannedPatterns = [
      { label: 'emoji', pattern: /[\u{1f300}-\u{1faff}]/u },
      // Note: bg-gradient-to and shadow-glow are intentional design choices
      // for the dark cinematic theme — they are NOT banned.
    ];

    const violations = Object.entries(sourceModules).filter(([file]) => !file.endsWith('visual-quality.test.ts')).flatMap(([file, content]) => {
      const charHits = bannedChars.filter((char) => content.includes(char)).map((char) => `char:${char.codePointAt(0)?.toString(16)}`);
      const patternHits = bannedPatterns.filter(({ pattern }) => pattern.test(content)).map(({ label }) => label);
      return [...charHits, ...patternHits].map((hit) => `${file}: ${hit}`);
    });

    expect(violations).toEqual([]);
  });
});
