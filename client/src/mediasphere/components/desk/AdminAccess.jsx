import { useEffect, useState } from 'react';
import { getDemoData, getMpAccess, grantMpAccess, revokeMpAccess, setDemoData } from '../../services/adminApi';

export default function AdminAccess({ onUnauthorized }) {
  const [name, setName] = useState('Sri Lavu Sri Krishna Devarayulu');
  const [numbers, setNumbers] = useState([]);
  const [phone, setPhone] = useState('');
  const [demo, setDemo] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const [access, setting] = await Promise.all([getMpAccess(), getDemoData()]);
      setName(access.name || name);
      setNumbers(access.numbers || []);
      setDemo(setting.enabled !== false);
    } catch (err) {
      if (err?.response?.status === 401) onUnauthorized?.();
      else setError(err?.response?.data?.message || err?.message || 'Could not load MP access.');
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const add = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await grantMpAccess(phone.trim());
      setPhone('');
      await load();
    } catch (err) {
      if (err?.response?.status === 401) onUnauthorized?.();
      else setError(err?.response?.data?.message || err?.message || 'The number was not saved.');
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id) => {
    setBusy(true);
    setError('');
    try {
      await revokeMpAccess(id);
      await load();
    } catch (err) {
      if (err?.response?.status === 401) onUnauthorized?.();
      else setError(err?.response?.data?.message || err?.message || 'The number was not removed.');
    } finally {
      setBusy(false);
    }
  };

  const toggleDemo = async () => {
    const next = !demo;
    setDemo(next);
    setError('');
    try {
      const saved = await setDemoData(next);
      setDemo(saved.enabled !== false);
    } catch (err) {
      setDemo(!next);
      if (err?.response?.status === 401) onUnauthorized?.();
      else setError(err?.response?.data?.message || err?.message || 'Demo data was not changed.');
    }
  };

  return (
    <div className="space-y-5">
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      <section className="rounded-2xl border border-msline bg-surface p-5 shadow-soft">
        <h2 className="text-lg font-bold text-app">MP access</h2>
        <p className="mt-1 text-sm text-msmuted">
          {name} can use the WhatsApp menu from a number added here. The bot answers that number as soon as it is saved.
        </p>
        <form onSubmit={(event) => void add(event)} className="mt-4 flex flex-col gap-3 sm:flex-row">
          <input
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
            required
            inputMode="tel"
            autoComplete="tel"
            placeholder="Phone number"
            className="h-10 flex-1 rounded-lg border border-msline bg-msbg px-3 text-sm"
          />
          <button
            type="submit"
            disabled={busy}
            className="h-10 rounded-lg bg-primary px-4 text-sm font-medium text-white hover:bg-primary-hover disabled:opacity-60"
          >
            {busy ? 'Saving....' : 'Give access'}
          </button>
        </form>
        <ul className="mt-4 divide-y divide-msline">
          {numbers.length ? numbers.map((item) => (
            <li key={item.id} className="flex items-center justify-between gap-3 py-2 text-sm">
              <span>{item.phone}</span>
              <button type="button" onClick={() => void remove(item.id)} className="text-red-600">Remove</button>
            </li>
          )) : <li className="py-2 text-sm text-msmuted">No MP number saved yet.</li>}
        </ul>
      </section>
      <section className="rounded-2xl border border-msline bg-surface p-5 shadow-soft">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-app">Demo data</h2>
            <p className="mt-1 text-sm text-msmuted">On shows the sample rows. Off leaves those lists blank. Nothing is deleted.</p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={demo}
            onClick={() => void toggleDemo()}
            className={`relative h-7 w-12 rounded-full ${demo ? 'bg-primary' : 'bg-slate-300'}`}
          >
            <span className={`absolute top-0.5 h-6 w-6 rounded-full bg-white ${demo ? 'left-5' : 'left-0.5'}`} />
          </button>
        </div>
      </section>
    </div>
  );
}
