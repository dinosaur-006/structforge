import { Composition } from 'remotion';
import { CtaSpring, HookBounce } from './compositions';

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="cta"
        component={CtaSpring}
        durationInFrames={90}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition
        id="hook"
        component={HookBounce}
        durationInFrames={60}
        fps={30}
        width={1080}
        height={1920}
      />
    </>
  );
};
