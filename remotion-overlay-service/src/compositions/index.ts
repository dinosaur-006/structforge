import { CtaSpring } from './CtaSpring';
import { HookBounce } from './HookBounce';
import type { CompositionName } from '../types';

export const compositions: Record<CompositionName, React.FC<any>> = {
  cta: CtaSpring,
  hook: HookBounce,
};

export { CtaSpring, HookBounce };
