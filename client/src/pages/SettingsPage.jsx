import { useEffect, useState } from 'react';
import { useNewsContext } from '../context/NewsContext';
import { DEFAULT_SETTINGS, loadSettings, saveSettings } from '../utils/settings';
import {
  PrefSection,
  PrefField,
  PrefInput,
  PrefToggle,
} from '../components/settings/PrefControls';

export default function SettingsPage() {
  const { dataRevision, lastUpdated } = useNewsContext();
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setSettings(loadSettings());
  }, []);

  const update = (patch) => {
    setSettings((prev) => ({ ...prev, ...patch }));
    setSaved(false);
  };

  const updateSource = (key, value) => {
    setSettings((prev) => ({
      ...prev,
      sources: { ...prev.sources, [key]: value },
    }));
    setSaved(false);
  };

  const handleSave = () => {
    saveSettings(settings);
    setSaved(true);
  };

  return (
    <div className="space-y-4 max-w-3xl">
      <div>
        <h2 className="text-lg font-bold text-primary">Settings</h2>
        <p className="text-sm text-muted">Control briefing preferences for this device</p>
      </div>

      <PrefSection title="Constituency" description="Display labels used across the platform.">
        <PrefField label="Constituency name">
          <PrefInput
            value={settings.constituencyName}
            onChange={(e) => update({ constituencyName: e.target.value })}
          />
        </PrefField>
        <PrefField label="Timezone label">
          <PrefInput
            value={settings.timezoneLabel}
            onChange={(e) => update({ timezoneLabel: e.target.value })}
          />
        </PrefField>
      </PrefSection>

      <PrefSection title="Sources" description="Default visibility filters for news browsing.">
        <PrefToggle
          label="Lokal"
          checked={!!settings.sources.lokal}
          onChange={(v) => updateSource('lokal', v)}
        />
        <PrefToggle
          label="YouTube"
          checked={!!settings.sources.youtube}
          onChange={(v) => updateSource('youtube', v)}
        />
        <PrefToggle
          label="Sakshi"
          checked={!!settings.sources.sakshi}
          onChange={(v) => updateSource('sakshi', v)}
        />
      </PrefSection>

      <PrefSection title="Refresh" description="Silent refresh interval (applied on next session).">
        <PrefField label="Interval (minutes)">
          <PrefInput
            type="number"
            min={1}
            max={60}
            value={settings.refreshIntervalMinutes}
            onChange={(e) =>
              update({ refreshIntervalMinutes: Math.max(1, Number(e.target.value) || 5) })
            }
          />
        </PrefField>
      </PrefSection>

      <PrefSection
        title="Alerts"
        description="Email report delivery is managed on the server. Wire recipients via backend env."
      >
        <p className="text-sm text-muted">
          Daily executive reports and incremental alerts use SMTP / Resend configuration on the API.
          A dedicated in-app recipient editor will appear here in a future release.
        </p>
      </PrefSection>

      <PrefSection title="About">
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-xs font-medium text-muted">App</dt>
            <dd className="text-app">MediaSphere Executive Platform v1.0.0</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-muted">Last updated</dt>
            <dd className="text-app">
              {lastUpdated ? lastUpdated.toLocaleString('en-IN') : '—'}
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs font-medium text-muted">Data revision</dt>
            <dd className="text-app break-all">{dataRevision || '—'}</dd>
          </div>
        </dl>
      </PrefSection>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handleSave}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover"
        >
          Save preferences
        </button>
        {saved && <span className="text-sm text-green-700">Saved on this device.</span>}
      </div>
    </div>
  );
}
