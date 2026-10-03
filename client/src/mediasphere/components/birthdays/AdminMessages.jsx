import { useCallback, useEffect, useMemo, useState } from 'react';
import { FileText, MessageSquareText, Send, UserPlus } from 'lucide-react';
import {
  addBirthday,
  fillTemplate,
  freeTextUntil,
  listBirthdays,
  listMessageTemplates,
  listSentMessages,
  sendMessages,
} from '../../services/birthdaysApi';
import { apiErrorMessage } from '../../services/visitsApi';
import { formatDateTime } from '../../utils/format';

const STATE_META = {
  accepted: { label: 'Accepted', className: 'bg-slate-100 text-slate-700' },
  sent: { label: 'Sent', className: 'bg-sky-100 text-sky-800' },
  delivered: { label: 'Delivered', className: 'bg-emerald-100 text-emerald-800' },
  read: { label: 'Read', className: 'bg-emerald-200 text-emerald-900' },
  failed: { label: 'Failed', className: 'bg-red-100 text-red-800' },
};
const PENDING_REFRESH_MS = 15000;

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
      className={`flex flex-1 items-start gap-3 rounded-xl border p-3 text-left transition-colors ${
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

/** Saves a person to the contact list (birthday optional) so they can be chosen and tracked. */
function AddPerson({ onAdded, handleError }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: '', phone: '', birthday: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline">
        <UserPlus className="h-4 w-4" aria-hidden /> Add a person (name and WhatsApp number)
      </button>
    );
  }

  const setField = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));
  const save = async () => {
    setError('');
    if (!form.name.trim() || !form.phone.trim()) {
      setError('Enter the name and the WhatsApp number.');
      return;
    }
    setSaving(true);
    try {
      const contact = await addBirthday({
        name: form.name.trim(),
        phone: form.phone.trim(),
        ...(form.birthday.trim() ? { birthday: form.birthday.trim() } : {}),
      });
      onAdded(contact);
      setForm({ name: '', phone: '', birthday: '' });
      setOpen(false);
    } catch (err) {
      const text = handleError(err, 'Could not add the person');
      if (text) setError(text);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-2 rounded-lg border border-msline p-3">
      <div className="grid gap-2 sm:grid-cols-3">
        <input className="input-field w-full" placeholder="Name *" value={form.name} onChange={setField('name')} maxLength={80} />
        <input
          className="input-field w-full"
          placeholder="WhatsApp number *"
          inputMode="tel"
          value={form.phone}
          onChange={setField('phone')}
          maxLength={20}
        />
        <input
          className="input-field w-full"
          placeholder="Birthday DD-MM (optional)"
          value={form.birthday}
          onChange={setField('birthday')}
          maxLength={10}
        />
      </div>
      <p className="text-xs text-msmuted">A 10-digit mobile gets +91. With a birthday, the person also gets the 7:00 AM wish.</p>
      {error ? <p className="text-sm text-red-500">{error}</p> : null}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={save}
          disabled={saving}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-hover disabled:opacity-60"
        >
          {saving ? 'Adding…' : 'Add and select'}
        </button>
        <button type="button" onClick={() => setOpen(false)} className="rounded-lg border border-msline px-4 py-2 text-sm font-medium">
          Cancel
        </button>
      </div>
    </div>
  );
}

function templateKey(template) {
  return `${template.name}|${template.language}`;
}

/** Once the new sign-off is approved, the previous birthday templates stay hidden. */
const REPLACED_TEMPLATES = {
  bday_wishes_en: 'bday_wishes_en_mee',
  bday_wishes: 'bday_wishes_mee',
};

function birthdayTemplates(list) {
  const names = new Set(list.map((template) => template.name));
  return list.filter((template) => {
    const newer = REPLACED_TEMPLATES[template.name];
    return !newer || !names.has(newer);
  });
}

export default function AdminMessages({ onUnauthorized }) {
  const [contacts, setContacts] = useState([]);
  const [selected, setSelected] = useState(() => new Set());
  const [mode, setMode] = useState('template');
  const [text, setText] = useState('');
  const [templates, setTemplates] = useState([]);
  const [templateError, setTemplateError] = useState('');
  const [chosenKey, setChosenKey] = useState('');
  const [values, setValues] = useState({});
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState({ kind: '', text: '' });
  const [results, setResults] = useState([]);
  const [history, setHistory] = useState([]);
  const [loadError, setLoadError] = useState('');

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

  const loadHistory = useCallback(async () => {
    try {
      setHistory(await listSentMessages());
    } catch (err) {
      const text = handleError(err, 'Could not load sent messages');
      if (text) setLoadError(text);
    }
  }, [handleError]);

  useEffect(() => {
    (async () => {
      try {
        const data = await listBirthdays();
        setContacts([...data.contacts].sort((a, b) => a.name.localeCompare(b.name)));
      } catch (err) {
        const text = handleError(err, 'Could not load contacts');
        if (text) setLoadError(text);
      }
      try {
        const list = birthdayTemplates(await listMessageTemplates());
        setTemplates(list);
        const preferred = list.find((t) => t.name === 'bday_wishes_en_mee') || list.find((t) => t.name === 'bday_wishes_mee') || list[0];
        if (preferred) setChosenKey(templateKey(preferred));
      } catch (err) {
        const text = handleError(err, 'Could not load templates');
        if (text) setTemplateError(text);
      }
    })();
    loadHistory();
  }, [handleError, loadHistory]);

  const pending = history.some(
    (row) => ['accepted', 'sent'].includes(row.state) && Date.now() - Date.parse(row.at) < 60 * 60 * 1000,
  );
  useEffect(() => {
    if (!pending) return undefined;
    const id = setInterval(loadHistory, PENDING_REFRESH_MS);
    return () => clearInterval(id);
  }, [pending, loadHistory]);

  const template = templates.find((t) => templateKey(t) === chosenKey) || null;
  const chosen = contacts.filter((contact) => selected.has(contact.id));
  const closedWindow = chosen.filter((contact) => !freeTextUntil(contact.lastInboundAt));
  const firstName = chosen[0]?.name || contacts[0]?.name || 'Name';

  const preview = useMemo(() => {
    if (mode === 'text') return text.replace(/\{name\}/gi, firstName);
    if (!template) return '';
    const filled = { ...values };
    if (template.params.includes('name') && !filled.name) filled.name = firstName;
    return fillTemplate(template.body, filled) + (template.footer ? `\n\n${template.footer}` : '');
  }, [mode, text, template, values, firstName]);

  const toggle = (id) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const allSelected = contacts.length > 0 && selected.size === contacts.length;

  const submit = async (event) => {
    event.preventDefault();
    setMessage({ kind: '', text: '' });
    setResults([]);
    if (!chosen.length) {
      setMessage({ kind: 'error', text: 'Choose at least one person.' });
      return;
    }
    const count = chosen.length === 1 ? chosen[0].name : `${chosen.length} people`;
    if (!window.confirm(`Send this WhatsApp message to ${count}?`)) return;
    setSending(true);
    try {
      const payload =
        mode === 'text'
          ? { contactIds: chosen.map((c) => c.id), kind: 'text', text }
          : { contactIds: chosen.map((c) => c.id), kind: 'template', template: template?.name, language: template?.language, params: values };
      const sent = await sendMessages(payload);
      setResults(sent);
      const ok = sent.filter((row) => row.status === 'accepted').length;
      setMessage({
        kind: ok === sent.length ? 'success' : 'error',
        text: `WhatsApp accepted ${ok} of ${sent.length}. Delivery shows below as receipts arrive.`,
      });
      if (mode === 'text') setText('');
      await loadHistory();
    } catch (err) {
      const text = handleError(err, 'Send failed');
      if (text) setMessage({ kind: 'error', text });
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="space-y-5">
      {loadError ? <p className="text-sm text-red-500">{loadError}</p> : null}
      <form onSubmit={submit} className="grid gap-5 lg:grid-cols-5">
        <section className="lg:col-span-2 rounded-2xl border border-msline bg-surface p-5 shadow-soft space-y-3">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-bold uppercase tracking-wide text-msmuted">
              1. Choose people{selected.size ? ` (${selected.size})` : ''}
            </h2>
            {contacts.length ? (
              <button
                type="button"
                onClick={() => setSelected(allSelected ? new Set() : new Set(contacts.map((c) => c.id)))}
                className="text-sm font-medium text-primary hover:underline"
              >
                {allSelected ? 'Clear' : 'Select all'}
              </button>
            ) : null}
          </div>
          {contacts.length === 0 ? (
            <p className="text-sm text-msmuted">No contacts yet. Add a person below.</p>
          ) : (
            <ul className="max-h-[420px] divide-y divide-msline/60 overflow-y-auto rounded-lg border border-msline">
              {contacts.map((contact) => {
                const until = freeTextUntil(contact.lastInboundAt);
                return (
                  <li key={contact.id}>
                    <label className="flex cursor-pointer items-start gap-3 px-3 py-2.5 hover:bg-msbg/60">
                      <input
                        type="checkbox"
                        className="mt-1"
                        checked={selected.has(contact.id)}
                        onChange={() => toggle(contact.id)}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-medium text-app">{contact.name}</span>
                        <span className="block text-xs text-msmuted">
                          +{contact.phone}
                          {contact.place ? ` · ${contact.place}` : ''}
                        </span>
                      </span>
                      <span
                        className={`shrink-0 rounded-md px-1.5 py-0.5 text-[11px] font-semibold ${
                          until ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'
                        }`}
                        title={until ? `Typed text allowed until ${formatDateTime(until.toISOString())}` : 'Has not messaged in the last 24 hours'}
                      >
                        {until ? 'Text OK' : 'Template only'}
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
          <AddPerson
            onAdded={(contact) => {
              setContacts((current) => [...current, contact].sort((a, b) => a.name.localeCompare(b.name)));
              setSelected((current) => new Set(current).add(contact.id));
            }}
            handleError={handleError}
          />
          <p className="text-xs text-msmuted">
            WhatsApp delivers typed text only to people who messaged the business number in the last 24 hours ("Text OK").
            Everyone else needs an approved template. Replies are ignored unless allowed in the Birthdays tab.
          </p>
        </section>

        <section className="lg:col-span-3 rounded-2xl border border-msline bg-surface p-5 shadow-soft space-y-4">
          <h2 className="text-sm font-bold uppercase tracking-wide text-msmuted">2. Message</h2>
          <div className="flex flex-col gap-3 sm:flex-row">
            <ModeButton
              active={mode === 'template'}
              onClick={() => setMode('template')}
              icon={FileText}
              title="Approved template"
              hint="Reaches anyone. Wording is fixed by Meta."
            />
            <ModeButton
              active={mode === 'text'}
              onClick={() => setMode('text')}
              icon={MessageSquareText}
              title="Type a message"
              hint="Only for people marked Text OK."
            />
          </div>

          {mode === 'text' ? (
            <div className="space-y-2">
              <label className="block text-sm">
                <span className="text-msmuted">Message *</span>
                <textarea
                  className="input-field mt-1 w-full min-h-[140px]"
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  maxLength={4000}
                  placeholder="Dear {name}, ..."
                />
              </label>
              <p className="text-xs text-msmuted">
                <code>{'{name}'}</code> becomes each person&apos;s name. {text.length}/4000
              </p>
              {closedWindow.length ? (
                <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                  {closedWindow.length === chosen.length && chosen.length === 1
                    ? `${closedWindow[0].name} has not`
                    : `${closedWindow.length} of the ${chosen.length} chosen people have not`}{' '}
                  messaged in the last 24 hours. WhatsApp will not deliver typed text to them; use an approved template.
                </p>
              ) : null}
            </div>
          ) : templateError ? (
            <p className="text-sm text-red-500">{templateError}</p>
          ) : (
            <div className="space-y-3">
              <label className="block text-sm">
                <span className="text-msmuted">Template *</span>
                <select
                  className="input-field mt-1 w-full"
                  value={chosenKey}
                  onChange={(event) => {
                    setChosenKey(event.target.value);
                    setValues({});
                  }}
                >
                  {templates.map((t) => (
                    <option key={templateKey(t)} value={templateKey(t)}>
                      {t.name} · {t.language}
                      {t.category ? ` · ${t.category.toLowerCase()}` : ''}
                    </option>
                  ))}
                </select>
              </label>
              {template?.params.length ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  {template.params.map((key) => (
                    <label key={key} className="block text-sm">
                      <span className="text-msmuted">
                        {`{{${key}}}`}
                        {key === 'name' ? '' : ' *'}
                      </span>
                      <input
                        className="input-field mt-1 w-full"
                        value={values[key] || ''}
                        onChange={(event) => setValues((current) => ({ ...current, [key]: event.target.value }))}
                        maxLength={1024}
                        placeholder={key === 'name' ? "Leave empty for each person's name" : ''}
                      />
                    </label>
                  ))}
                </div>
              ) : null}
            </div>
          )}

          {preview ? (
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-msmuted">Preview for {firstName}</p>
              <div className="mt-1 whitespace-pre-line rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-slate-800">
                {preview}
              </div>
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={sending || !chosen.length || (mode === 'text' ? !text.trim() : !template)}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-white hover:bg-primary-hover disabled:opacity-60"
            >
              <Send className="h-4 w-4" aria-hidden />
              {sending ? 'Sending…' : `Send on WhatsApp${chosen.length ? ` (${chosen.length})` : ''}`}
            </button>
            <Message message={message} />
          </div>
          {results.some((row) => row.status === 'failed') ? (
            <ul className="list-disc space-y-0.5 pl-5 text-sm text-red-500">
              {results
                .filter((row) => row.status === 'failed')
                .map((row) => (
                  <li key={row.contactId}>
                    {row.name}: {row.error}
                  </li>
                ))}
            </ul>
          ) : null}
        </section>
      </form>

      <section className="rounded-2xl border border-msline bg-surface p-5 shadow-soft">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-sm font-bold uppercase tracking-wide text-msmuted">Sent messages</h2>
          <button type="button" onClick={loadHistory} className="rounded-md border border-msline bg-surface px-3 py-1.5 text-sm font-medium">
            Refresh
          </button>
        </div>
        {history.length === 0 ? (
          <p className="text-sm text-msmuted">Nothing sent from here yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-msline text-left text-xs uppercase text-msmuted">
                  <th className="py-2 pr-3">Sent</th>
                  <th className="py-2 pr-3">To</th>
                  <th className="py-2 pr-3">Message</th>
                  <th className="py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {history.map((row) => {
                  const meta = STATE_META[row.state] || STATE_META.accepted;
                  return (
                    <tr key={row.id} className="border-b border-msline/60 align-top">
                      <td className="whitespace-nowrap py-2.5 pr-3 text-msmuted">{formatDateTime(row.at)}</td>
                      <td className="whitespace-nowrap py-2.5 pr-3">
                        <span className="font-medium text-app">{row.name}</span>
                        <span className="block text-xs text-msmuted">+{row.phone}</span>
                      </td>
                      <td className="max-w-[420px] py-2.5 pr-3">
                        {row.template ? <span className="block text-xs text-msmuted">Template {row.template}</span> : null}
                        <span className="line-clamp-2 whitespace-pre-line" title={row.body}>
                          {row.body}
                        </span>
                      </td>
                      <td className="py-2.5">
                        <span className={`inline-flex rounded-md px-2 py-0.5 text-xs font-semibold uppercase ${meta.className}`}>
                          {meta.label}
                        </span>
                        {row.error ? <span className="mt-1 block max-w-[260px] text-xs text-red-500">{row.error}</span> : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
