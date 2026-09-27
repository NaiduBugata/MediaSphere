import { createHash } from 'node:crypto';

/** Port of ProblemIDGenerator.generate — deterministic PROB-<12 hex>. */
export function problemId(
  category: string,
  district: string,
  problem: string,
): string {
  const payload = [category, district, problem].map(sanitize).join('|');
  const digest = createHash('sha256')
    .update(payload, 'utf8')
    .digest('hex')
    .slice(0, 12)
    .toUpperCase();
  return `PROB-${digest}`;
}

function sanitize(value: string): string {
  return (value || '')
    .normalize('NFC')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .replace(/[\p{P}\p{S}\p{Cf}]/gu, '')
    .replace(/\s+/g, '');
}
