/**
 * Timestamp helpers that reproduce Python's
 * `datetime.now(timezone.utc).isoformat()` string shape.
 *
 * Parity matters: Flask writes `+00:00`-suffixed strings into
 * `scheduler_state` / `pipeline_history`, and `get_data_revision()` picks the
 * max by *string* comparison. A `Z` suffix would sort after `+00:00`.
 */
export function pythonUtcIso(date: Date = new Date()): string {
  // 2026-09-26T13:25:00.123Z -> 2026-09-26T13:25:00.123000+00:00
  return date.toISOString().replace(/Z$/, '000+00:00');
}

/**
 * Shape of `datetime.isoformat()` for a value read back from Mongo by pymongo,
 * which decodes BSON dates as *naive* UTC (no offset suffix). Used for
 * `lock.expires_at` / `lock.acquired_at` so the JSON matches Flask byte for byte.
 */
export function pythonNaiveIso(date: Date): string {
  return date.toISOString().replace(/Z$/, '000');
}

/** Match `datetime.fromisoformat(value.replace("Z", "+00:00"))`, loosely. */
export function parseIsoOrNull(value: unknown): Date | null {
  if (value instanceof Date) return value;
  if (!value) return null;
  const parsed = Date.parse(String(value).replace(/Z$/i, '+00:00'));
  return Number.isNaN(parsed) ? null : new Date(parsed);
}

/** Seconds since `iso`, clamped at 0. Null when unparseable. */
export function agoSeconds(
  iso: unknown,
  now: Date = new Date(),
): number | null {
  const dt = parseIsoOrNull(iso);
  if (!dt) return null;
  return Math.max(0, (now.getTime() - dt.getTime()) / 1000);
}

/** Python `round(value, 3)` for durations. */
export function round3(value: number): number {
  return Math.round(value * 1000) / 1000;
}
