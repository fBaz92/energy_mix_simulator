/**
 * Minimal error boundary that catches runtime errors in the rendered tree
 * and shows a user-friendly fallback instead of a white screen.
 *
 * Wraps each top-level page in App.tsx.
 */
import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info);
  }

  reset = () => this.setState({ error: null });

  render() {
    if (this.state.error) {
      return (
        <div className="p-8 space-y-4 max-w-2xl">
          <div className="flex items-center gap-3 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            <h2 className="text-lg font-semibold">Something went wrong</h2>
          </div>
          <p className="text-sm text-muted-foreground">
            {this.state.error.message}
          </p>
          <Button onClick={this.reset} variant="outline" size="sm">
            Retry
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
