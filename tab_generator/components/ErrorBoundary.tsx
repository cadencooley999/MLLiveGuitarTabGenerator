// ErrorBoundary.tsx
import type {ErrorInfo, ReactNode } from "react";
import { Component } from "react";

interface Props { children: ReactNode; }
interface State { hasError: boolean; }

class ErrorBoundary extends Component<Props, State> {
  public state: State = { hasError: false };

  // eslint-disable-next-line
  public static getDerivedStateFromError(_: Error): State {
    return { hasError: true };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return <div className="p-12 rounded-2xl bg-red-100 text-red-900">Something went wrong displaying the tabs.</div>;
    }
    return this.props.children;
  }
}

export default ErrorBoundary;