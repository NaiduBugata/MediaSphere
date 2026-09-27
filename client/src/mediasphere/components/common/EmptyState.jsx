import { Inbox } from 'lucide-react';

export default function EmptyState({ title, message }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 px-6 text-center">
      <div className="rounded-full bg-msbg p-3 border border-msline">
        <Inbox className="h-7 w-7 text-msmuted" />
      </div>
      <div>
        <h3 className="text-base font-semibold text-app">{title || 'Nothing here'}</h3>
        {message && <p className="mt-1 text-sm text-msmuted max-w-sm">{message}</p>}
      </div>
    </div>
  );
}
