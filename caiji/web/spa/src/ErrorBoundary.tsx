import React from 'react'

type ErrorBoundaryState = {
  error: Error | null
  componentStack: string
}

export class ErrorBoundary extends React.Component<React.PropsWithChildren, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null, componentStack: '' }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error, componentStack: '' }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    this.setState({ componentStack: errorInfo.componentStack || '' })
    console.error('React Error Boundary caught:', error, errorInfo)
  }

  render() {
    if (this.state.error) {
      return (
        <main className="flex min-h-screen items-center justify-center bg-slate-950 px-6 text-slate-50">
          <section className="max-w-2xl rounded-2xl border border-white/10 bg-white/10 p-6 shadow-xl">
            <p className="text-sm font-medium text-rose-200">Preview failed to render</p>
            <h1 className="mt-2 text-2xl font-semibold">Something went wrong.</h1>
            <p className="mt-3 text-sm text-slate-300">
              The app caught a runtime error instead of rendering a blank screen.
            </p>
            <pre className="mt-4 max-h-40 overflow-auto rounded-lg bg-slate-950/70 p-3 text-xs text-slate-200">
              {this.state.error.message}
            </pre>
            {this.state.componentStack && (
              <details className="mt-4">
                <summary className="text-xs text-slate-400 cursor-pointer hover:text-slate-300">Component stack</summary>
                <pre className="mt-2 max-h-60 overflow-auto rounded-lg bg-slate-950/70 p-3 text-xs text-slate-200">
                  {this.state.componentStack}
                </pre>
              </details>
            )}
            <button
              onClick={() => window.location.reload()}
              className="mt-6 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-500"
            >
              Reload page
            </button>
          </section>
        </main>
      )
    }
    return this.props.children
  }
}
