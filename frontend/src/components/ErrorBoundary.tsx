import { Component, type ErrorInfo, type ReactNode } from "react"

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex h-screen flex-col items-center justify-center gap-4 bg-background p-8">
          <h1 className="font-mono text-lg font-bold tracking-[0.2em] text-destructive">
            SOMETHING WENT WRONG
          </h1>
          <p className="max-w-md text-center font-mono text-sm text-muted-foreground">
            {this.state.error.message}
          </p>
          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            className="rounded border border-primary/30 bg-primary/10 px-6 py-2 font-mono text-sm font-semibold text-primary transition-colors hover:bg-primary/20"
          >
            Try Again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
