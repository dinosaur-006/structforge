import { useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';
import type { CtaProps } from '../types';

export const CtaSpring: React.FC<CtaProps> = ({ price, originalPrice, slogan, primaryColor }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  const bgOpacity = interpolate(frame, [0, 15], [0, 0.6], { extrapolateRight: 'clamp' });

  const priceSpring = spring({
    frame: Math.max(0, frame - fps * 0.5),
    fps,
    config: { mass: 1, stiffness: 200, damping: 20 },
  });

  const originalSlideX = interpolate(frame, [fps * 1.5, fps * 1.8], [100, 0], { extrapolateRight: 'clamp' });
  const sloganOpacity = interpolate(frame, [fps * 2, fps * 2.5], [0, 1], { extrapolateRight: 'clamp' });
  const glowScale = 1 + 0.03 * Math.sin(frame / 3);

  return (
    <div style={{
      width, height,
      backgroundColor: `rgba(0,0,0,${bgOpacity})`,
      display: 'flex', flexDirection: 'column',
      justifyContent: 'center', alignItems: 'center',
      position: 'relative', overflow: 'hidden',
    }}>
      <div style={{
        position: 'absolute',
        width: 400, height: 400, borderRadius: '50%',
        background: `radial-gradient(circle, ${primaryColor}33, transparent)`,
        transform: `scale(${glowScale})`,
      }} />
      <div style={{
        fontSize: 120, fontWeight: 'bold', color: primaryColor,
        transform: `scale(${priceSpring})`,
        textShadow: '0 0 30px rgba(0,0,0,0.5)',
        fontFamily: 'sans-serif',
      }}>
        ¥{price}
      </div>
      {originalPrice ? (
        <div style={{
          fontSize: 48, color: 'white',
          transform: `translateX(${originalSlideX}px)`,
          textDecoration: 'line-through',
          opacity: frame > fps * 1.5 ? 1 : 0,
        }}>
          ¥{originalPrice}
        </div>
      ) : null}
      <div style={{
        fontSize: 36, color: 'white', marginTop: 20,
        opacity: sloganOpacity, fontFamily: 'sans-serif',
      }}>
        {slogan}
      </div>
    </div>
  );
};
