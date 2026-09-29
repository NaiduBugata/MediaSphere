import { useCallback, useEffect, useRef, useState } from 'react';
import { Download, Eye, Trash2, Upload } from 'lucide-react';
import {
  VISIT_ACCEPT,
  VISIT_MAX_MB,
  apiErrorMessage,
  deleteVisit,
  formatFileSize,
  listVisits,
  uploadVisit,
  visitFileUrl,
} from '../../services/visitsApi';
import { formatDate, formatDateTime } from '../../utils/format';
import VisitKindBadge from './VisitKindBadge';

const EMPTY_FORM = { title: '', place: '', visitDate: '', detail: '' };
const ALLOWED_EXTENSIONS = VISIT_ACCEPT.split(',');

function extensionOf(name) {
  const dot = name.lastIndexOf('.');
  return dot >= 0 ? name.slice(dot).toLowerCase() : '';
}

export default function AdminVisits({ onUnauthorized }) {
  const [visits, setVisits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [form, setForm] = useState(EMPTY_FORM);
  const [file, setFile] = useState(null);
  const [progress, setProgress] = useState(null);
  const [message, setMessage] = useState({ kind: '', text: '' });
  const [deletingId, setDeletingId] = useState('');
  const fileInputRef = useRef(null);

  const handleError = useCallback(
    (err, fallback) => {
      if (err?.response?.status === 401) {
        onUnauthorized?.();
        return '';
      }
      return apiErrorMessage(err, fallback);
    },
    [onUnauthorized],
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setLoadError('');
      setVisits(await listVisits());
    } catch (err) {
      setLoadError(apiErrorMessage(err, 'Could not load visits'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const pickFile = (event) => {
    const picked = event.target.files?.[0] || null;
    setMessage({ kind: '', text: '' });
    if (!picked) {
      setFile(null);
      return;
    }
    if (!ALLOWED_EXTENSIONS.includes(extensionOf(picked.name))) {
      setFile(null);
      event.target.value = '';
      setMessage({ kind: 'error', text: 'Only PDF, Word (.doc, .docx) or Excel (.xls, .xlsx) files are allowed.' });
      return;
    }
    if (picked.size > VISIT_MAX_MB * 1024 * 1024) {
      setFile(null);
      event.target.value = '';
      setMessage({ kind: 'error', text: `File is too large (max ${VISIT_MAX_MB} MB).` });
      return;
    }
    setFile(picked);
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!file) {
      setMessage({ kind: 'error', text: 'Choose a PDF, Word or Excel file.' });
      return;
    }
    setProgress(0);
    setMessage({ kind: '', text: '' });
    try {
      const visit = await uploadVisit(
        {
          title: form.title.trim(),
          place: form.place.trim(),
          visitDate: form.visitDate,
          detail: form.detail.trim(),
          file,
        },
        setProgress,
      );
      setForm(EMPTY_FORM);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      setMessage({ kind: 'success', text: `Uploaded "${visit?.title || form.title}". It is now visible on the site.` });
      await load();
    } catch (err) {
      const text = handleError(err, 'Upload failed');
      if (text) setMessage({ kind: 'error', text });
    } finally {
      setProgress(null);
    }
  };

  const remove = async (visit) => {
    if (!window.confirm(`Delete "${visit.title}"? The file will be removed from the site.`)) return;
    setDeletingId(visit.id);
    setMessage({ kind: '', text: '' });
    try {
      await deleteVisit(visit.id);
      setVisits((rows) => rows.filter((row) => row.id !== visit.id));
      setMessage({ kind: 'success', text: `Deleted "${visit.title}".` });
    } catch (err) {
      const text = handleError(err, 'Delete failed');
      if (text) setMessage({ kind: 'error', text });
    } finally {
      setDeletingId('');
    }
  };

  const uploading = progress !== null;
  const setField = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-msline bg-surface p-5 shadow-soft">
        <h2 className="text-sm font-bold uppercase tracking-wide text-msmuted">Upload a visit</h2>
        <p className="mt-1 text-sm text-msmuted">
          PDF, Word or Excel, up to {VISIT_MAX_MB} MB. Uploaded visits appear on the site below the news and in the
          WhatsApp assistant&apos;s Visits button.
        </p>
        <form onSubmit={submit} className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="block text-sm md:col-span-2">
            <span className="text-msmuted">Title *</span>
            <input
              className="input-field mt-1 w-full"
              value={form.title}
              onChange={setField('title')}
              maxLength={200}
              required
              placeholder="e.g. Visit to Vinukonda Government Hospital"
            />
          </label>
          <label className="block text-sm">
            <span className="text-msmuted">Visit date</span>
            <input type="date" className="input-field mt-1 w-full" value={form.visitDate} onChange={setField('visitDate')} />
          </label>
          <label className="block text-sm">
            <span className="text-msmuted">Place</span>
            <input
              className="input-field mt-1 w-full"
              value={form.place}
              onChange={setField('place')}
              maxLength={120}
              placeholder="e.g. Vinukonda"
            />
          </label>
          <label className="block text-sm md:col-span-2">
            <span className="text-msmuted">Description</span>
            <textarea
              className="input-field mt-1 w-full min-h-[84px]"
              value={form.detail}
              onChange={setField('detail')}
              maxLength={2000}
              placeholder="Short summary shown on the site"
            />
          </label>
          <label className="block text-sm md:col-span-2">
            <span className="text-msmuted">File (PDF, Word or Excel) *</span>
            <input
              ref={fileInputRef}
              type="file"
              accept={VISIT_ACCEPT}
              onChange={pickFile}
              className="mt-1 block w-full text-sm text-app file:mr-3 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-primary-hover"
            />
            {file ? (
              <span className="mt-1 block text-xs text-msmuted">
                {file.name} · {formatFileSize(file.size)}
              </span>
            ) : null}
          </label>
          <div className="md:col-span-2 flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={uploading}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-white hover:bg-primary-hover disabled:opacity-60"
            >
              <Upload className="h-4 w-4" aria-hidden />
              {uploading ? `Uploading… ${progress}%` : 'Upload visit'}
            </button>
            {message.text ? (
              <p className={`text-sm ${message.kind === 'error' ? 'text-red-500' : 'text-emerald-500'}`}>{message.text}</p>
            ) : null}
          </div>
        </form>
      </section>

      <section className="rounded-2xl border border-msline bg-surface p-5 shadow-soft">
        <div className="flex items-center justify-between gap-3 mb-4">
          <h2 className="text-sm font-bold uppercase tracking-wide text-msmuted">Uploaded visits</h2>
          <button
            type="button"
            onClick={load}
            className="rounded-md border border-msline bg-surface px-3 py-1.5 text-sm font-medium"
          >
            Refresh
          </button>
        </div>
        {loadError ? <p className="text-sm text-red-600">{loadError}</p> : null}
        {loading && visits.length === 0 ? (
          <p className="text-sm text-msmuted">Loading visits…</p>
        ) : visits.length === 0 ? (
          <p className="text-sm text-msmuted">No visits uploaded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-msmuted border-b border-msline">
                  <th className="py-2 pr-3">Type</th>
                  <th className="py-2 pr-3">Title</th>
                  <th className="py-2 pr-3">Visit date</th>
                  <th className="py-2 pr-3">Place</th>
                  <th className="py-2 pr-3">File</th>
                  <th className="py-2 pr-3">Uploaded</th>
                  <th className="py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {visits.map((visit) => (
                  <tr key={visit.id} className="border-b border-msline/60 align-top">
                    <td className="py-2.5 pr-3">
                      {visit.file ? <VisitKindBadge kind={visit.file.kind} /> : <span className="text-msmuted">—</span>}
                    </td>
                    <td className="py-2.5 pr-3 font-medium text-app max-w-[260px]">{visit.title}</td>
                    <td className="py-2.5 pr-3 whitespace-nowrap">{visit.visitDate ? formatDate(visit.visitDate) : '—'}</td>
                    <td className="py-2.5 pr-3">{visit.place || '—'}</td>
                    <td className="py-2.5 pr-3 text-msmuted max-w-[200px] truncate" title={visit.file?.name}>
                      {visit.file ? `${visit.file.name} · ${formatFileSize(visit.file.size)}` : 'No file'}
                    </td>
                    <td className="py-2.5 pr-3 whitespace-nowrap text-msmuted">{formatDateTime(visit.createdAt)}</td>
                    <td className="py-2.5 whitespace-nowrap">
                      <div className="flex items-center gap-3">
                        {visit.file?.kind === 'pdf' ? (
                          <a
                            href={visitFileUrl(visit.file.id)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-primary font-medium hover:underline"
                          >
                            <Eye className="h-4 w-4" aria-hidden /> View
                          </a>
                        ) : null}
                        {visit.file ? (
                          <a
                            href={visitFileUrl(visit.file.id, true)}
                            className="inline-flex items-center gap-1 text-primary font-medium hover:underline"
                          >
                            <Download className="h-4 w-4" aria-hidden /> Download
                          </a>
                        ) : null}
                        <button
                          type="button"
                          onClick={() => remove(visit)}
                          disabled={deletingId === visit.id}
                          className="inline-flex items-center gap-1 text-red-600 font-medium hover:underline disabled:opacity-60"
                        >
                          <Trash2 className="h-4 w-4" aria-hidden />
                          {deletingId === visit.id ? 'Deleting…' : 'Delete'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
