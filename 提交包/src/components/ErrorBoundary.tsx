import type { ErrorInfo, ReactNode } from 'react';
import { Component } from 'react';
import { Button } from './ui/Button';
import { ErrorAlert } from './ui/ErrorAlert';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(error, info);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <main className="flex min-h-dvh items-center justify-center bg-surface p-6 text-text-primary">
        <div className="w-full max-w-xl">
          <ErrorAlert
            title={'\u9875\u9762\u51fa\u9519\u4e86'}
            description={this.state.error.message}
            action={<Button onClick={() => this.setState({ error: null })}>{'\u91cd\u8bd5'}</Button>}
          />
        </div>
      </main>
    );
  }
}
