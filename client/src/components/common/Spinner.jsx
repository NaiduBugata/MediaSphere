import { Loader2 } from 'lucide-react';

export default function Spinner({ label = 'Loading...' }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-10" role="status">
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
      <p className="text-sm text-muted">{label}</p>
    </div>
  );
}
