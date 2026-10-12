/** When this is off, mock rows stay stored and are left out of every list. */
let enabled = true;

export function isDemoDataEnabled(): boolean {
  return enabled;
}

export function setDemoDataEnabled(value: boolean): void {
  enabled = value;
}

export function isDemoDoc(row: { source?: unknown; title?: unknown; detail?: unknown }): boolean {
  const source = String(row.source || '');
  const title = String(row.title || '');
  const detail = String(row.detail || '');
  return source === 'mock' || title.startsWith('MOCK') || detail.includes('MOCK-VISIT');
}
