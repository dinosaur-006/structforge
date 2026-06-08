import express from 'express';
import cors from 'cors';
import path from 'path';
import * as fs from 'fs';
import { renderOverlay } from './render/render-overlay';
import type { RenderRequest, RenderResponse } from './types';

const app = express();
app.use(cors());
app.use(express.json());
app.use('/output', express.static(path.join(__dirname, '..', 'public')));

const PORT = Number(process.env.PORT) || 3001;
let activeRenders = 0;
const MAX_CONCURRENT = 2;

app.post('/render', async (req, res) => {
  const body = req.body as RenderRequest;
  if (activeRenders >= MAX_CONCURRENT) {
    res.status(202).json({ message: 'Too many renders in progress, retry later', queueLength: activeRenders });
    return;
  }

  const startTime = Date.now();
  activeRenders++;
  let outputPath = '';
  try {
    outputPath = await renderOverlay(body);
    const videoFilename = path.basename(outputPath);
    const videoUrl = `http://localhost:${PORT}/output/${videoFilename}`;
    const renderTimeMs = Date.now() - startTime;
    const durationMs = (body.durationSeconds || (body.composition === 'cta' ? 3 : 2)) * 1000;

    const response: RenderResponse = { videoUrl, durationMs, renderTimeMs };
    res.json(response);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  } finally {
    activeRenders--;
    // Cleanup after 5 minutes
    if (outputPath) {
      setTimeout(() => { try { fs.unlinkSync(outputPath); } catch {} }, 300_000);
    }
  }
});

app.get('/health', (_req, res) => res.json({ status: 'ok', activeRenders }));

app.listen(PORT, () => console.log(`Remotion overlay service on port ${PORT}`));
