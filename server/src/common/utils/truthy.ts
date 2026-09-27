export function truthy(value: unknown): boolean {
  if (typeof value === 'boolean') return value;
  if (value == null) return false;
  const s = String(value).trim().toLowerCase();
  return s === '1' || s === 'true' || s === 'yes' || s === 'on';
}
