import { useCurrentFrame, spring, interpolate, useVideoConfig } from 'remotion';
import type { HookProps } from '../types';

export const HookBounce: React.FC<HookProps> = ({ keyword, emotion }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const chars = [...keyword];
  const charDelay = 3;

  const vignetteOpacity = interpolate(frame, [0, 10], [0, 0.5], { extrapolateRight: 'clamp' });

  return (
    <div style={{
      width, height, backgroundColor: 'black',
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      position: 'relative', overflow: 'hidden',
    }}>
      <div style={{
        position: 'absolute', inset: 0,
        background: `radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,${vignetteOpacity}) 100%)`,
      }} />
      <div style={{ display: 'flex', fontSize: 80, fontWeight: 'bold', color: 'white', gap: 5, flexWrap: 'wrap', justifyContent: 'center' }}>
        {chars.map((char, i) => {
          const charFrame = Math.max(0, frame - i * charDelay);
          const y = charFrame > 0
            ? spring({ frame: charFrame, fps, config: { mass: 1, stiffness: 150, damping: 12 } })
            : 0;
          const offsetY = (1 - y) * 20;
          let shake = 0;
          if (emotion === '恐惧' && charFrame > 0) {
            shake = Math.sin(charFrame * 0.8) * 3 * (1 - y);
          }
          return (
            <span key={i} style={{
              display: 'inline-block',
              transform: `translateY(${offsetY}px) translateX(${shake}px)`,
              opacity: charFrame > 0 ? y : 0,
              textShadow: '0 0 15px rgba(255,255,255,0.8)',
            }}>
              {char}
            </span>
          );
        })}
      </div>
    </div>
  );
};
