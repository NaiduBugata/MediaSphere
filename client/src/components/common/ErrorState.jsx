import { AlertCircle, RefreshCw } from 'lucide-react';

export default function ErrorState({ message, onRetry }) {
  return (
    <div className="card flex flex-col items-center justify-center gap-4 py-16 px-6 text-center">
      <div className="rounded-full bg-danger/10 p-3">
        <AlertCircle className="h-8 w-8 text-danger" />
      </div>
      <div>
        <h3 className="text-lg font-semibold text-app">Something went wrong</h3>
        <p className="mt-1 text-sm text-muted max-w-md">{message || 'Unable to load data.'}</p>
      </div>
      {onRetry && (
        <button type="button" onClick={onRetry} className="btn-primary">
          <RefreshCw className="h-4 w-4" />
          Try again
        </button>
      )}
    </div>
  );
}
