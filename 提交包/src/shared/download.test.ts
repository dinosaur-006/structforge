import { describe, expect, it, vi } from 'vitest';
import type { FinalScript } from './types';
import { downloadJson, finalScriptToSrt } from './download';

const finalScript: FinalScript = {
  version: 'high_click',
  total_duration: 6.25,
  segments: [
    {
      id: 'seg-1',
      type: 'hook',
      start: 0,
      end: 2.5,
      duration: 2.5,
      script: '开头抓住注意力',
      visual: '产品特写',
      asset_id: null,
      subtitle_style: 'clean',
      transition: 'hard_cut',
      locked: false,
      source: 'packaging',
    },
    {
      id: 'seg-2',
      type: 'cta',
      start: 2.5,
      end: 6.25,
      duration: 3.75,
      script: '现在下单',
      visual: '行动卡',
      asset_id: null,
      subtitle_style: 'clean',
      transition: 'hard_cut',
      locked: false,
      source: 'packaging',
    },
  ],
  metadata: {},
};

describe('download exports', () => {
  it('converts a final script to ordered SRT captions', () => {
    expect(finalScriptToSrt(finalScript)).toBe(
      '1\n00:00:00,000 --> 00:00:02,500\n开头抓住注意力\n\n2\n00:00:02,500 --> 00:00:06,250\n现在下单\n',
    );
  });

  it('downloads indented JSON through a browser blob', () => {
    const createObjectURL = vi.fn(() => 'blob:artifact');
    const revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL });
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);

    downloadJson('analysis.json', { status: 'ready' });

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(click).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:artifact');
  });
});
