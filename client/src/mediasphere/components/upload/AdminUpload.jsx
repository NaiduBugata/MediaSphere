import { useEffect, useState } from 'react';
import { downloadUploadTemplate, getUploadKinds, uploadAdminFile } from '../../services/adminApi';

const FALLBACK = [
  { id: 'visits', label: 'Visits' },
  { id: 'schedule', label: 'Schedule' },
  { id: 'campaigns', label: 'Campaigns' },
  { id: 'grievances', label: 'Grievances' },
  { id: 'projects', label: 'Projects' },
  { id: 'constituency', label: 'Constituency details' },
  { id: 'leaders', label: 'Leaders' },
  { id: 'birthdays', label: 'Birthday wishes' },
];

export default function AdminUpload({ onUnauthorized }) {
  const [kinds, setKinds] = useState(FALLBACK);
  const [kind, setKind] = useState('visits');
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    getUploadKinds()
      .then((data) => {
        if (Array.isArray(data?.kinds) && data.kinds.length) {
          setKinds(data.kinds.map((item) => ({ ...item, label: labelFor(item.id) })));
        }
      })
      .catch((err) => {
        if (err?.response?.status === 401) onUnauthorized?.();
      });
  }, [onUnauthorized]);

  const selected = kinds.find((item) => item.id === kind) || kinds[0];

  const download = async () => {
    const blob = await downloadUploadTemplate(kind);
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${kind}-template.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setResult(null);
    try {
      const response = await uploadAdminFile(kind, file);
      if (response.status === 401) {
        onUnauthorized?.();
        return;
      }
      const data = response.data || {};
      if (response.status < 300 && data.status === 'success') {
        setResult({ ok: true, text: `Success. ${data.inserted} saved.` });
        setFile(null);
        event.target.reset?.();
      } else {
        const errors = Array.isArray(data.errors) ? data.errors : [data.message || data.error || 'Upload was not accepted.'];
        setResult({ ok: false, text: errors.join('\n') });
      }
    } catch (err) {
      setResult({ ok: false, text: err?.message || 'Upload was not accepted.' });
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="mx-auto max-w-3xl space-y-4 rounded-2xl border border-msline bg-surface p-5">
      <div>
        <h2 className="text-lg font-bold text-app">Upload in the saved format</h2>
        <p className="mt-1 text-sm text-msmuted">
          Download the template, keep the header row exactly as it is, and replace the sample row. Success is shown only when every row matches that format.
        </p>
      </div>
      <label className="block text-sm">
        <span className="text-msmuted">What is in the file</span>
        <select value={kind} onChange={(event) => { setKind(event.target.value); setResult(null); }} className="input-field mt-1 w-full">
          {kinds.map((item) => (
            <option key={item.id} value={item.id}>{item.label}</option>
          ))}
        </select>
      </label>
      {selected?.headers ? (
        <p className="rounded-lg bg-msbg px-3 py-2 text-sm text-app">
          Header: {selected.headers.join(', ')}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => void download()} className="rounded-lg border border-msline px-3 py-2 text-sm font-medium">
          Download template
        </button>
      </div>
      <label className="block text-sm">
        <span className="text-msmuted">.csv or .xlsx file</span>
        <input
          type="file"
          accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          required
          onChange={(event) => setFile(event.target.files?.[0] || null)}
          className="mt-1 block w-full text-sm"
        />
      </label>
      {result ? (
        <p className={`whitespace-pre-line text-sm ${result.ok ? 'text-emerald-700' : 'text-red-600'}`}>{result.text}</p>
      ) : null}
      <button type="submit" disabled={busy || !file} className="rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60">
        {busy ? 'Uploading....' : 'Upload'}
      </button>
    </form>
  );
}

function labelFor(id) {
  return FALLBACK.find((item) => item.id === id)?.label || id;
}
