import { useEffect, useState } from 'react';
import { CalendarDays, Download, Eye, MapPin } from 'lucide-react';
import { formatFileSize, listVisits, visitFileUrl } from '../../services/visitsApi';
import { formatDate } from '../../utils/format';
import VisitKindBadge from './VisitKindBadge';

const INITIAL_COUNT = 6;

function VisitCard({ visit }) {
  const { file } = visit;
  return (
    <article className="flex h-full flex-col rounded-xl border border-msline bg-surface p-4 shadow-soft">
      <div className="flex items-start justify-between gap-2">
        {file ? <VisitKindBadge kind={file.kind} /> : <span />}
        {file?.size ? <span className="text-xs text-msmuted">{formatFileSize(file.size)}</span> : null}
      </div>
      <h3 className="mt-3 text-base font-semibold leading-snug text-app">{visit.title}</h3>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-msmuted">
        {visit.visitDate || visit.createdAt ? (
          <span className="inline-flex items-center gap-1">
            <CalendarDays className="h-3.5 w-3.5" aria-hidden />
            {formatDate(visit.visitDate || visit.createdAt)}
          </span>
        ) : null}
        {visit.place ? (
          <span className="inline-flex items-center gap-1">
            <MapPin className="h-3.5 w-3.5" aria-hidden />
            {visit.place}
          </span>
        ) : null}
      </div>
      {visit.detail ? <p className="mt-2 text-sm text-msmuted line-clamp-3">{visit.detail}</p> : null}
      {file ? (
        <div className="mt-auto flex flex-wrap gap-2 pt-4">
          {file.kind === 'pdf' ? (
            <a
              href={visitFileUrl(file.id)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-hover"
            >
              <Eye className="h-4 w-4" aria-hidden /> View
            </a>
          ) : null}
          <a
            href={visitFileUrl(file.id, true)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-msline px-3 py-1.5 text-sm font-medium text-app hover:border-primary hover:text-primary"
          >
            <Download className="h-4 w-4" aria-hidden /> Download
          </a>
        </div>
      ) : null}
    </article>
  );
}

export default function VisitsSection() {
  const [visits, setVisits] = useState([]);
  const [state, setState] = useState('loading');
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listVisits()
      .then((rows) => {
        if (cancelled) return;
        setVisits(rows);
        setState('ready');
      })
      .catch(() => {
        if (!cancelled) setState('error');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const shown = showAll ? visits : visits.slice(0, INITIAL_COUNT);

  return (
    <section id="visits" className="space-y-3 pt-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="section-title">Visits</h2>
        {visits.length > INITIAL_COUNT ? (
          <button
            type="button"
            onClick={() => setShowAll((value) => !value)}
            className="text-sm font-medium text-primary hover:underline"
          >
            {showAll ? 'Show less' : `View all ${visits.length}`}
          </button>
        ) : null}
      </div>
      {state === 'loading' ? (
        <p className="text-sm text-msmuted">Loading visits…</p>
      ) : state === 'error' ? (
        <p className="text-sm text-msmuted">Visits could not be loaded right now.</p>
      ) : visits.length === 0 ? (
        <p className="rounded-xl border border-dashed border-msline bg-surface px-4 py-6 text-center text-sm text-msmuted">
          No visits have been published yet.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {shown.map((visit) => (
            <VisitCard key={visit.id} visit={visit} />
          ))}
        </div>
      )}
    </section>
  );
}
