import { FiInbox } from 'react-icons/fi';

export default function EmptyState({ title = 'No data available', message = 'There are no articles to display at this time.' }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-4 rounded-full bg-secondary-100 p-4">
        <FiInbox className="h-8 w-8 text-gray-400" />
      </div>
      <h3 className="text-base font-semibold text-gray-800">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-gray-500">{message}</p>
    </div>
  );
}
