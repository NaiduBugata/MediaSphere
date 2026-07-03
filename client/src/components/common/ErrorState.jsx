import { FiAlertCircle, FiRefreshCw } from 'react-icons/fi';

export default function ErrorState({ message = 'Something went wrong', onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-4 rounded-full bg-gray-100 p-4">
        <FiAlertCircle className="h-8 w-8 text-gray-600" />
      </div>
      <h3 className="text-base font-semibold text-gray-800">Unable to load dashboard</h3>
      <p className="mt-1 max-w-md text-sm text-gray-500">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 transition-colors"
        >
          <FiRefreshCw className="h-4 w-4" />
          Retry
        </button>
      )}
    </div>
  );
}
