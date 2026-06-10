import { useNavigate } from 'react-router-dom';
import { cn } from '../../shared/cn';

interface Step {
  key: string;
  label: string;
  path: string;
}

const steps: Step[] = [
  { key: 'analyze', label: '分析样例', path: '/analyze' },
  { key: 'migrate', label: '编辑结构', path: '/migrate' },
  { key: 'result', label: '生成结果', path: '/result' },
];

interface WorkflowStepsProps {
  current: 'analyze' | 'migrate' | 'result';
  projectId?: string;
}

export function WorkflowSteps({ current, projectId }: WorkflowStepsProps) {
  const navigate = useNavigate();
  const currentIndex = steps.findIndex((s) => s.key === current);

  return (
    <nav className="flex items-center gap-2 text-sm" aria-label="工作流程">
      {steps.map((step, i) => {
        const isCurrent = i === currentIndex;
        const isDone = i < currentIndex;
        const href = projectId ? `${step.path}/${projectId}` : step.path;

        return (
          <span key={step.key} className="flex items-center gap-2">
            {i > 0 ? (
              <span className={cn('h-px w-6', isDone ? 'bg-primary' : 'bg-border')} />
            ) : null}
            <a
              href={href}
              onClick={(e) => {
                e.preventDefault();
                navigate(href);
              }}
              className={cn(
                'flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium transition-colors',
                isCurrent && 'bg-primary/10 text-primary',
                isDone && 'text-primary hover:underline',
                !isCurrent && !isDone && 'text-text-secondary',
              )}
            >
              <span
                className={cn(
                  'flex h-5 w-5 items-center justify-center rounded-full text-xs font-bold',
                  isCurrent && 'bg-primary text-white',
                  isDone && 'bg-primary text-white',
                  !isCurrent && !isDone && 'bg-border text-text-secondary',
                )}
              >
                {isDone ? '✓' : i + 1}
              </span>
              {step.label}
            </a>
          </span>
        );
      })}
    </nav>
  );
}
