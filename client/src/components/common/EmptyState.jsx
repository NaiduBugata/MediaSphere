import { Inbox } from 'lucide-react';

export default function EmptyState({ title, message }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 px-6 text-center">
      <div className="rounded-full bg-app p-3 border border-app">
        <Inbox className="h-7 w-7 text-muted" />
      </div>
      <div>
        <h3 className="text-base font-semibold text-app">{title || 'Nothing here'}</h3>
        {message && <p className="mt-1 text-sm text-muted max-w-sm">{message}</p>}
      </div>
    </div>
  );
}
