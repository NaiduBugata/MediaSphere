import { useCallback, useEffect, useState } from 'react';
import { Cake, Send, Trash2, UserPlus } from 'lucide-react';
import {
  addBirthday,
  deleteBirthday,
  formatBirthday,
  isBirthdayToday,
  listBirthdays,
  sendBirthdayWish,
  setBirthdayReplies,
} from '../../services/birthdaysApi';
import { apiErrorMessage } from '../../services/visitsApi';
import { formatDateTime } from '../../utils/format';

const EMPTY_FORM = { name: '', phone: '', birthday: '', place: '', designation: '', notes: '', language: 'en' };

function Message({ message }) {
  if (!message.text) return null;
  return <p className={`text-sm ${message.kind === 'error' ? 'text-red-500' : 'text-emerald-500'}`}>{message.text}</p>;
}

function WishCell({ wish, today }) {
  if (!wish) return <span className="text-msmuted">Not wished yet</span>;
  const when = wish.day === today ? 'Today' : wish.day;
  if (wish.status === 'sent') {
    return (
      <span className="text-emerald-600" title={formatDateTime(wish.at)}>
        Sent {when}
        {wish.manual ? ' (manual)' : ''}
      </span>
    );
  }
  return (
    <span className="text-red-500" title={wish.error || ''}>
      Failed {when} ({wish.tries} {wish.tries === 1 ? 'try' : 'tries'})
    </span>
  );
}

export default function AdminBirthdays({ onUnauthorized }) {
  const [info, setInfo] = useState({ contacts: [], today: '', automatic: false, hour: 7, templates: {} });
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [formMessage, setFormMessage] = useState({ kind: '', text: '' });
  const [listMessage, setListMessage] = useState({ kind: '', text: '' });
  const [busyId, setBusyId] = useState('');

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
      setInfo(await listBirthdays());
    } catch (err) {
      const text = handleError(err, 'Could not load birthdays');
      if (text) setListMessage({ kind: 'error', text });
    } finally {
      setLoading(false);
    }
  }, [handleError]);

  useEffect(() => {
    load();
  }, [load]);

  const setField = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setFormMessage({ kind: '', text: '' });
    try {
      const contact = await addBirthday({
        ...form,
        name: form.name.trim(),
        phone: form.phone.trim(),
        place: form.place.trim(),
        designation: form.designation.trim(),
        notes: form.notes.trim(),
      });
      setForm(EMPTY_FORM);
      setFormMessage({ kind: 'success', text: `Added ${contact?.name || form.name}.` });
      await load();
    } catch (err) {
      const text = handleError(err, 'Save failed');
      if (text) setFormMessage({ kind: 'error', text });
    } finally {
      setSaving(false);
    }
  };

  const send = async (contact) => {
    if (!window.confirm(`Send the birthday wish to ${contact.name} on WhatsApp now?`)) return;
    setBusyId(contact.id);
    setListMessage({ kind: '', text: '' });
    try {
      await sendBirthdayWish(contact.id);
      setListMessage({ kind: 'success', text: `Birthday wish sent to ${contact.name}.` });
      await load();
    } catch (err) {
      const text = handleError(err, 'Send failed');
      if (text) setListMessage({ kind: 'error', text });
      await load();
    } finally {
      setBusyId('');
    }
  };

  const toggleReplies = async (contact) => {
    const allow = !contact.allowReplies;
    const question = allow
      ? `Allow ${contact.name} to reply? Their messages will be received and the WhatsApp assistant can answer them.`
      : `Block replies from ${contact.name}? Their messages will be ignored.`;
    if (!window.confirm(question)) return;
    setBusyId(contact.id);
    setListMessage({ kind: '', text: '' });
    try {
      await setBirthdayReplies(contact.id, allow);
      setListMessage({ kind: 'success', text: `${contact.name}: replies ${allow ? 'allowed' : 'blocked'}.` });
      await load();
    } catch (err) {
      const text = handleError(err, 'Could not change replies');
      if (text) setListMessage({ kind: 'error', text });
    } finally {
      setBusyId('');
    }
  };

  const remove = async (contact) => {
    if (!window.confirm(`Remove ${contact.name} from the birthday list?`)) return;
    setBusyId(contact.id);
    setListMessage({ kind: '', text: '' });
    try {
      await deleteBirthday(contact.id);
      setListMessage({ kind: 'success', text: `Removed ${contact.name}.` });
      await load();
    } catch (err) {
      const text = handleError(err, 'Delete failed');
      if (text) setListMessage({ kind: 'error', text });
    } finally {
      setBusyId('');
    }
  };

  const todays = info.contacts.filter((contact) => isBirthdayToday(contact.birthday, info.today));

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-msline bg-surface p-5 shadow-soft space-y-3">
        <h2 className="text-sm font-bold uppercase tracking-wide text-msmuted">How birthday wishes work</h2>
        <ul className="list-disc space-y-1 pl-5 text-sm text-msmuted">
          <li>
            On each contact&apos;s birthday a WhatsApp wish goes out from {info.hour}:00 India time, addressed by name and signed
            by Lavu Sri Krishna Devarayulu, Member of Parliament, Narasaraopet.
          </li>
          <li>
            Automatic sending is{' '}
            <span className={`font-semibold ${info.automatic ? 'text-emerald-600' : 'text-amber-600'}`}>
              {info.automatic ? 'on' : 'off'}
            </span>
            {info.automatic ? '.' : ' (WhatsApp is not configured on the API, or BIRTHDAY_WISHES_ENABLED=false).'}
          </li>
          <li>
            One-way by default: replies are ignored, not stored, and the chatbot does not answer them. Click{' '}
            <span className="font-semibold">Blocked</span> in the Replies column to let a person reply.
          </li>
        </ul>
      </section>

      <section className="rounded-2xl border border-msline bg-surface p-5 shadow-soft space-y-4">
        <h2 className="text-sm font-bold uppercase tracking-wide text-msmuted">Add a contact</h2>
        <form onSubmit={submit} className="grid gap-4 md:grid-cols-3">
          <label className="block text-sm">
            <span className="text-msmuted">Name (used in the wish) *</span>
            <input className="input-field mt-1 w-full" value={form.name} onChange={setField('name')} maxLength={80} required />
          </label>
          <label className="block text-sm">
            <span className="text-msmuted">WhatsApp number *</span>
            <input
              className="input-field mt-1 w-full"
              value={form.phone}
              onChange={setField('phone')}
              maxLength={20}
              inputMode="tel"
              placeholder="10-digit mobile"
              required
            />
          </label>
          <label className="block text-sm">
            <span className="text-msmuted">Birthday *</span>
            <input
              className="input-field mt-1 w-full"
              value={form.birthday}
              onChange={setField('birthday')}
              maxLength={10}
              placeholder="DD-MM-YYYY or DD-MM"
              required
            />
          </label>
          <label className="block text-sm">
            <span className="text-msmuted">Place</span>
            <input className="input-field mt-1 w-full" value={form.place} onChange={setField('place')} maxLength={120} />
          </label>
          <label className="block text-sm">
            <span className="text-msmuted">Designation</span>
            <input className="input-field mt-1 w-full" value={form.designation} onChange={setField('designation')} maxLength={120} />
          </label>
          <label className="block text-sm">
            <span className="text-msmuted">Wish language</span>
            <select className="input-field mt-1 w-full" value={form.language} onChange={setField('language')}>
              <option value="en">English</option>
              <option value="te">Telugu</option>
            </select>
          </label>
          <label className="block text-sm md:col-span-3">
            <span className="text-msmuted">Notes</span>
            <input className="input-field mt-1 w-full" value={form.notes} onChange={setField('notes')} maxLength={500} />
          </label>
          <div className="md:col-span-3 flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-white hover:bg-primary-hover disabled:opacity-60"
            >
              <UserPlus className="h-4 w-4" aria-hidden />
              {saving ? 'Saving…' : 'Add contact'}
            </button>
            <Message message={formMessage} />
          </div>
        </form>
      </section>

      <section className="rounded-2xl border border-msline bg-surface p-5 shadow-soft">
        <div className="flex items-center justify-between gap-3 mb-4">
          <h2 className="text-sm font-bold uppercase tracking-wide text-msmuted">
            Birthday contacts{info.contacts.length ? ` (${info.contacts.length})` : ''}
            {todays.length ? ` · ${todays.length} today` : ''}
          </h2>
          <button type="button" onClick={load} className="rounded-md border border-msline bg-surface px-3 py-1.5 text-sm font-medium">
            Refresh
          </button>
        </div>
        <Message message={listMessage} />
        {loading && info.contacts.length === 0 ? (
          <p className="text-sm text-msmuted">Loading…</p>
        ) : info.contacts.length === 0 ? (
          <p className="text-sm text-msmuted">No contacts yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-msmuted border-b border-msline">
                  <th className="py-2 pr-3">Name</th>
                  <th className="py-2 pr-3">Birthday</th>
                  <th className="py-2 pr-3">WhatsApp</th>
                  <th className="py-2 pr-3">Place / designation</th>
                  <th className="py-2 pr-3">Language</th>
                  <th className="py-2 pr-3">Last wish</th>
                  <th className="py-2 pr-3">Replies</th>
                  <th className="py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {info.contacts.map((contact) => {
                  const today = isBirthdayToday(contact.birthday, info.today);
                  return (
                    <tr key={contact.id} className={`border-b border-msline/60 align-top ${today ? 'bg-primary/5' : ''}`}>
                      <td className="py-2.5 pr-3 font-medium text-app">
                        {contact.name}
                        {contact.notes ? <span className="block text-xs font-normal text-msmuted">{contact.notes}</span> : null}
                      </td>
                      <td className="py-2.5 pr-3 whitespace-nowrap">
                        {formatBirthday(contact.birthday, contact.birthYear)}
                        {today ? (
                          <span className="ml-2 inline-flex items-center gap-1 rounded-md bg-primary/15 px-1.5 py-0.5 text-xs font-semibold text-primary">
                            <Cake className="h-3 w-3" aria-hidden /> Today
                          </span>
                        ) : null}
                      </td>
                      <td className="py-2.5 pr-3 whitespace-nowrap">+{contact.phone}</td>
                      <td className="py-2.5 pr-3 text-msmuted">
                        {[contact.place, contact.designation].filter(Boolean).join(' · ') || '—'}
                      </td>
                      <td className="py-2.5 pr-3">{contact.language === 'te' ? 'Telugu' : 'English'}</td>
                      <td className="py-2.5 pr-3 whitespace-nowrap">
                        <WishCell wish={contact.lastWish} today={info.today} />
                      </td>
                      <td className="py-2.5 pr-3 whitespace-nowrap">
                        <button
                          type="button"
                          onClick={() => toggleReplies(contact)}
                          disabled={busyId === contact.id}
                          title={contact.allowReplies ? 'Click to block replies' : 'Click to allow replies'}
                          className={`rounded-md px-2 py-0.5 text-xs font-semibold disabled:opacity-60 ${
                            contact.allowReplies ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-600'
                          }`}
                        >
                          {contact.allowReplies ? 'Allowed' : 'Blocked'}
                        </button>
                      </td>
                      <td className="py-2.5 whitespace-nowrap">
                        <div className="flex items-center gap-3">
                          <button
                            type="button"
                            onClick={() => send(contact)}
                            disabled={busyId === contact.id}
                            className="inline-flex items-center gap-1 text-primary font-medium hover:underline disabled:opacity-60"
                          >
                            <Send className="h-4 w-4" aria-hidden />
                            {busyId === contact.id ? 'Working…' : 'Send now'}
                          </button>
                          <button
                            type="button"
                            onClick={() => remove(contact)}
                            disabled={busyId === contact.id}
                            className="inline-flex items-center gap-1 text-red-500 font-medium hover:underline disabled:opacity-60"
                          >
                            <Trash2 className="h-4 w-4" aria-hidden /> Remove
                          </button>
                        </div>
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
