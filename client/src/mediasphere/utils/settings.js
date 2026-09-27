const STORAGE_KEY = 'mediasphere.settings.v1';

export const DEFAULT_SETTINGS = {
  constituencyName: 'Narasaraopet',
  timezoneLabel: 'Asia/Kolkata (IST)',
  sources: {
    lokal: true,
    youtube: true,
    sakshi: true,
  },
  refreshIntervalMinutes: 5,
};

export function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_SETTINGS, sources: { ...DEFAULT_SETTINGS.sources } };
    const parsed = JSON.parse(raw);
    return {
      ...DEFAULT_SETTINGS,
      ...parsed,
      sources: { ...DEFAULT_SETTINGS.sources, ...(parsed.sources || {}) },
    };
  } catch {
    return { ...DEFAULT_SETTINGS, sources: { ...DEFAULT_SETTINGS.sources } };
  }
}

export function saveSettings(settings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}
