import { bundle } from '@remotion/bundler';
import { renderMedia, selectComposition } from '@remotion/renderer';
import path from 'path';
import type { RenderRequest } from '../types';

export async function renderOverlay(req: RenderRequest): Promise<string> {
  const { composition, props, width = 1080, height = 1920, fps = 30, durationSeconds } = req;
  const duration = durationSeconds || (composition === 'cta' ? 3 : 2);
  const durationInFrames = duration * fps;

  const serveUrl = await bundle({
    entryPoint: path.resolve(__dirname, '..', 'Root.tsx'),
  });

  const inputProps = props as unknown as Record<string, unknown>;

  const comp = await selectComposition({
    serveUrl,
    id: composition as string,
    inputProps,
  });

  const outputPath = path.join(process.cwd(), 'public', `output-${Date.now()}.webm`);

  await renderMedia({
    serveUrl,
    composition: comp,
    codec: 'vp8',
    outputLocation: outputPath,
    inputProps,
    imageFormat: 'png',
    pixelFormat: 'yuva420p',
  });

  return outputPath;
}
