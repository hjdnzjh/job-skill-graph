import React from 'react'

type ErrorBoundaryState = {
  error: Error | null
}

export class ErrorBoundary extends React.Component<React.PropsWithChildren, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <main className="flex min-h-screen items-center justify-center bg-slate-950 px-6 text-slate-50">
          <section className="max-w-md rounded-2xl border border-white/10 bg-white/10 p-6 shadow-xl">
            <p className="text-sm font-medium text-rose-200">Preview failed to render</p>
            <h1 className="mt-2 text-2xl font-semibold">Something went wrong.</h1>
            <p className="mt-3 text-sm text-slate-300">
              The app caught a runtime error instead of rendering a blank screen.
            </p>
            <pre className="mt-4 max-h-40 overflow-auto rounded-lg bg-slate-950/70 p-3 text-xs text-slate-200">
              {this.state.error.message}
            </pre>
          </section>
        </main>
      )
    }
    return this.props.children
  }
}
