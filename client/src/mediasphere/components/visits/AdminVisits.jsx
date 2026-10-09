import { useCallback, useEffect, useRef, useState } from 'react';
import { Download, Eye, FileSpreadsheet, FileType, ListPlus, PencilLine, Trash2, Upload } from 'lucide-react';
import {
  IMPORT_ACCEPT,
  VISIT_ACCEPT,
  VISIT_MAX_MB,
  apiErrorMessage,
  deleteVisit,
  formatFileSize,
  formatVisitTime,
  importVisits,
  listAdminVisits,
  templateUrl,
  uploadVisit,
  visitFileUrl,
} from '../../services/visitsApi';
import { formatDate, formatDateTime } from '../../utils/format';
import VisitKindBadge from './VisitKindBadge';

const EMPTY_FORM = { title: '', place: '', visitDate: '', visitTime: '', anytime: false, detail: '', leadPhone: '' };
const REJECTED_SHOWN = 15;

function extensionOf(name) {
  const dot = name.lastIndexOf('.');
  return dot >= 0 ? name.slice(dot).toLowerCase() : '';
}

/** Returns an error message, or '' when the file can be sent. */
function checkFile(file, accept, kinds) {
  if (!accept.split(',').includes(extensionOf(file.name))) return `Only ${kinds} files are allowed.`;
  if (file.size > VISIT_MAX_MB * 1024 * 1024) return `File is too large (max ${VISIT_MAX_MB} MB).`;
  return '';
}

function Message({ message }) {
  if (!message.text) return null;
  return <p className={`text-sm ${message.kind === 'error' ? 'text-red-500' : 'text-emerald-500'}`}>{message.text}</p>;
}

function ModeButton({ active, onClick, icon: Icon, title, hint }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`flex flex-1 items-start gap-3 rounded-xl border p-4 text-left transition-colors ${
        active ? 'border-primary bg-primary/10' : 'border-msline bg-surface hover:border-primary/60'
      }`}
    >
      <Icon className={`mt-0.5 h-5 w-5 shrink-0 ${active ? 'text-primary' : 'text-msmuted'}`} aria-hidden />
      <span>
        <span className="block text-sm font-semibold text-app">{title}</span>
        <span className="mt-0.5 block text-xs text-msmuted">{hint}</span>
      </span>
    </button>
  );
}

function ImportPanel({ onImported, handleError }) {
  const [file, setFile] = useState(null);
  const [progress, setProgress] = useState(null);
  const [message, setMessage] = useState({ kind: '', text: '' });
  const [result, setResult] = useState(null);
  const inputRef = useRef(null);

  const pick = (event) => {
    const picked = event.target.files?.[0] || null;
    setMessage({ kind: '', text: '' });
    setResult(null);
    const error = picked ? checkFile(picked, IMPORT_ACCEPT, 'Excel (.xlsx), Word (.docx) or PDF') : '';
    if (error) {
      event.target.value = '';
      setFile(null);
      setMessage({ kind: 'error', text: error });
      return;
    }
    setFile(picked);
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!file) {
      setMessage({ kind: 'error', text: 'Choose the Excel, Word or PDF file that lists the visits.' });
      return;
    }
    setProgress(0);
    setMessage({ kind: '', text: '' });
    setResult(null);
    try {
      const data = await importVisits(file, setProgress);
      setResult(data);
      setFile(null);
      if (inputRef.current) inputRef.current.value = '';
      await onImported();
    } catch (err) {
      const text = handleError(err, 'Import failed');
      if (text) setMessage({ kind: 'error', text });
    } finally {
      setProgress(null);
    }
  };

  const uploading = progress !== null;
  return (
    <div className="space-y-4">
      <div className="space-y-2 text-sm text-msmuted">
        <p>
          One Excel, Word or PDF file with a table of all visits. Every row becomes a visit on the site. Rows that are
          already on the site are skipped, so you can add new rows to the same file and upload it again.
        </p>
        <p>
          Columns:{' '}
          <span className="font-medium text-app">S.No · Date (DD-MM-YYYY) · Time (10:30 AM) · Place · Purpose / Title · Details</span>
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <a
          href={templateUrl('xlsx')}
          className="inline-flex items-center gap-2 rounded-lg border border-msline px-3 py-2 text-sm font-medium text-app hover:border-emerald-500 hover:text-emerald-500"
        >
          <FileSpreadsheet className="h-4 w-4" aria-hidden /> Download Excel template
        </a>
        <a
          href={templateUrl('docx')}
          className="inline-flex items-center gap-2 rounded-lg border border-msline px-3 py-2 text-sm font-medium text-app hover:border-blue-500 hover:text-blue-500"
        >
          <FileType className="h-4 w-4" aria-hidden /> Download Word template
        </a>
      </div>
      <form onSubmit={submit} className="space-y-3">
        <label className="block text-sm">
          <span className="text-msmuted">Visits file (Excel .xlsx, Word .docx or PDF) *</span>
          <input
            ref={inputRef}
            type="file"
            accept={IMPORT_ACCEPT}
            onChange={pick}
            className="mt-1 block w-full text-sm text-app file:mr-3 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-primary-hover"
          />
          {file ? (
            <span className="mt-1 block text-xs text-msmuted">
              {file.name} · {formatFileSize(file.size)}
            </span>
          ) : null}
        </label>
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={uploading}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-white hover:bg-primary-hover disabled:opacity-60"
          >
            <Upload className="h-4 w-4" aria-hidden />
            {uploading ? (progress < 100 ? `Uploading… ${progress}%` : 'Reading the file…') : 'Upload all visits'}
          </button>
          <Message message={message} />
        </div>
      </form>
      {result ? (
        <div className="rounded-xl border border-msline bg-msbg/40 p-4 text-sm">
          <p className="font-semibold text-app">
            {result.imported === 1 ? '1 new visit added' : `${result.imported} new visits added`} from {result.fileName}.
          </p>
          <p className="mt-1 text-msmuted">
            {result.found} {result.found === 1 ? 'row' : 'rows'} read
            {result.duplicates ? `, ${result.duplicates} already on the site (skipped)` : ''}
            {result.rejected.length ? `, ${result.rejected.length} could not be read` : ''}.
          </p>
          {result.rejected.length ? (
            <ul className="mt-2 list-disc space-y-0.5 pl-5 text-red-500">
              {result.rejected.slice(0, REJECTED_SHOWN).map((row) => (
                <li key={`${row.where}-${row.reason}`}>
                  {row.where}: {row.reason}
                </li>
              ))}
              {result.rejected.length > REJECTED_SHOWN ? (
                <li>and {result.rejected.length - REJECTED_SHOWN} more. Fix these rows and upload the file again.</li>
              ) : null}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function SingleVisitPanel({ onSaved, handleError }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [file, setFile] = useState(null);
  const [progress, setProgress] = useState(null);
  const [message, setMessage] = useState({ kind: '', text: '' });
  const inputRef = useRef(null);

  const pick = (event) => {
    const picked = event.target.files?.[0] || null;
    setMessage({ kind: '', text: '' });
    const error = picked ? checkFile(picked, VISIT_ACCEPT, 'PDF, Word (.doc, .docx) or Excel (.xls, .xlsx)') : '';
    if (error) {
      event.target.value = '';
      setFile(null);
      setMessage({ kind: 'error', text: error });
      return;
    }
    setFile(picked);
  };

  const submit = async (event) => {
    event.preventDefault();
    setProgress(0);
    setMessage({ kind: '', text: '' });
    try {
      const visit = await uploadVisit(
        {
          title: form.title.trim(),
          place: form.place.trim(),
          visitDate: form.visitDate,
          visitTime: form.visitTime,
          detail: form.detail.trim(),
          leadPhone: form.leadPhone.trim(),
          file,
        },
        setProgress,
      );
      setForm(EMPTY_FORM);
      setFile(null);
      if (inputRef.current) inputRef.current.value = '';
      setMessage({ kind: 'success', text: `Saved "${visit?.title || form.title}". It is now visible on the site.` });
      await onSaved();
    } catch (err) {
      const text = handleError(err, 'Save failed');
      if (text) setMessage({ kind: 'error', text });
    } finally {
      setProgress(null);
    }
  };

  const saving = progress !== null;
  const setField = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));
  return (
    <form onSubmit={submit} className="grid gap-4 md:grid-cols-2">
      <label className="block text-sm md:col-span-2">
        <span className="text-msmuted">Purpose / Title *</span>
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
        <span className="text-msmuted">Visit time</span>
        <input
          type="time"
          className="input-field mt-1 w-full"
          value={form.visitTime}
          onChange={setField('visitTime')}
          disabled={form.anytime}
        />
        <label className="mt-2 flex items-center gap-2 text-xs text-msmuted">
          <input
            type="checkbox"
            checked={Boolean(form.anytime)}
            onChange={(event) => setForm((current) => ({ ...current, anytime: event.target.checked, visitTime: event.target.checked ? '' : current.visitTime }))}
          />
          Anytime
        </label>
      </label>
      <label className="block text-sm md:col-span-2">
        <span className="text-msmuted">Place</span>
        <input className="input-field mt-1 w-full" value={form.place} onChange={setField('place')} maxLength={120} placeholder="e.g. Vinukonda" />
      </label>
      <label className="block text-sm md:col-span-2">
        <span className="text-msmuted">Lead WhatsApp number (optional, not shown on the site or in the visits chat)</span>
        <input
          className="input-field mt-1 w-full"
          value={form.leadPhone}
          onChange={setField('leadPhone')}
          maxLength={20}
          inputMode="tel"
          placeholder="e.g. 9876543210"
        />
      </label>
      <label className="block text-sm md:col-span-2">
        <span className="text-msmuted">Details</span>
        <textarea
          className="input-field mt-1 w-full min-h-[84px]"
          value={form.detail}
          onChange={setField('detail')}
          maxLength={2000}
          placeholder="Short summary shown on the site"
        />
      </label>
      <label className="block text-sm md:col-span-2">
        <span className="text-msmuted">Attachment (optional): PDF, Word or Excel, up to {VISIT_MAX_MB} MB</span>
        <input
          ref={inputRef}
          type="file"
          accept={VISIT_ACCEPT}
          onChange={pick}
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
          disabled={saving}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-white hover:bg-primary-hover disabled:opacity-60"
        >
          <ListPlus className="h-4 w-4" aria-hidden />
          {saving ? (file ? `Uploading… ${progress}%` : 'Saving…') : 'Save visit'}
        </button>
        <Message message={message} />
      </div>
    </form>
  );
}

function SourceCell({ visit }) {
  if (visit.file) return <VisitKindBadge kind={visit.file.kind} />;
  return (
    <span className="inline-flex whitespace-nowrap rounded-md border border-msline px-2 py-0.5 text-xs font-semibold text-msmuted">
      {visit.source === 'import' ? 'From file' : 'Typed'}
    </span>
  );
}

export default function AdminVisits({ onUnauthorized }) {
  const [mode, setMode] = useState('bulk');
  const [visits, setVisits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [listMessage, setListMessage] = useState({ kind: '', text: '' });
  const [deletingId, setDeletingId] = useState('');

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
      setVisits(await listAdminVisits());
    } catch (err) {
      setLoadError(apiErrorMessage(err, 'Could not load visits'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const remove = async (visit) => {
    if (!window.confirm(`Delete "${visit.title}"? It will be removed from the site.`)) return;
    setDeletingId(visit.id);
    setListMessage({ kind: '', text: '' });
    try {
      await deleteVisit(visit.id);
      setVisits((rows) => rows.filter((row) => row.id !== visit.id));
      setListMessage({ kind: 'success', text: `Deleted "${visit.title}".` });
    } catch (err) {
      const text = handleError(err, 'Delete failed');
      if (text) setListMessage({ kind: 'error', text });
    } finally {
      setDeletingId('');
    }
  };

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-msline bg-surface p-5 shadow-soft space-y-4">
        <h2 className="text-sm font-bold uppercase tracking-wide text-msmuted">Add visits</h2>
        <div className="flex flex-col gap-3 sm:flex-row">
          <ModeButton
            active={mode === 'bulk'}
            onClick={() => setMode('bulk')}
            icon={Upload}
            title="Upload all visits (one file)"
            hint="Excel, Word or PDF table. Each row becomes a visit."
          />
          <ModeButton
            active={mode === 'single'}
            onClick={() => setMode('single')}
            icon={PencilLine}
            title="Add a single visit"
            hint="Type the details. Attaching a file is optional."
          />
        </div>
        {mode === 'bulk' ? (
          <ImportPanel onImported={load} handleError={handleError} />
        ) : (
          <SingleVisitPanel onSaved={load} handleError={handleError} />
        )}
      </section>

      <section className="rounded-2xl border border-msline bg-surface p-5 shadow-soft">
        <div className="flex items-center justify-between gap-3 mb-4">
          <h2 className="text-sm font-bold uppercase tracking-wide text-msmuted">
            Visits on the site{visits.length ? ` (${visits.length})` : ''}
          </h2>
          <button
            type="button"
            onClick={load}
            className="rounded-md border border-msline bg-surface px-3 py-1.5 text-sm font-medium"
          >
            Refresh
          </button>
        </div>
        <Message message={listMessage} />
        {loadError ? <p className="text-sm text-red-500">{loadError}</p> : null}
        {loading && visits.length === 0 ? (
          <p className="text-sm text-msmuted">Loading visits…</p>
        ) : visits.length === 0 ? (
          <p className="text-sm text-msmuted">No visits yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-msmuted border-b border-msline">
                  <th className="py-2 pr-3">Source</th>
                  <th className="py-2 pr-3">Purpose / Title</th>
                  <th className="py-2 pr-3">Date &amp; time</th>
                  <th className="py-2 pr-3">Place</th>
                  <th className="py-2 pr-3">Lead</th>
                  <th className="py-2 pr-3">Details</th>
                  <th className="py-2 pr-3">Added</th>
                  <th className="py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {visits.map((visit) => (
                  <tr key={visit.id} className="border-b border-msline/60 align-top">
                    <td className="py-2.5 pr-3">
                      <SourceCell visit={visit} />
                    </td>
                    <td className="py-2.5 pr-3 font-medium text-app max-w-[240px]">{visit.title}</td>
                    <td className="py-2.5 pr-3 whitespace-nowrap">
                      {visit.visitDate ? formatDate(visit.visitDate) : '—'}
                      {visit.visitDate ? (
                        <span className="block text-xs text-msmuted">{visit.visitTime ? formatVisitTime(visit.visitTime) : 'Anytime'}</span>
                      ) : null}
                    </td>
                    <td className="py-2.5 pr-3">{visit.place || '—'}</td>
                    <td className="py-2.5 pr-3">
                      {(visit.leadPhones?.length ? visit.leadPhones : visit.leadPhone ? [visit.leadPhone] : []).map((phone) => (
                        <span key={phone} className="block whitespace-nowrap">+{phone}</span>
                      ))}
                      {!(visit.leadPhones?.length || visit.leadPhone) ? '—' : null}
                    </td>
                    <td className="py-2.5 pr-3 text-msmuted max-w-[260px] truncate" title={visit.detail}>
                      {visit.detail || (visit.file ? `${visit.file.name} · ${formatFileSize(visit.file.size)}` : '—')}
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
                          className="inline-flex items-center gap-1 text-red-500 font-medium hover:underline disabled:opacity-60"
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
