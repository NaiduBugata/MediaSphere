/** Worship, prayer services, and devotional items. A civic story that only mentions a place of worship is kept. */

const PHRASES = [
  'ఆరాధన',
  'భజన',
  'భక్తి గీత',
  'ప్రవచనం',
  'అభిషేకం',
  'నమాజ్',
  'ఖురాన్',
  'బైబిల్',
  'sunday worship',
  'church service',
  'prayer meeting',
  'devotional',
  'bible study',
  'gospel',
  'bhajan',
  'sermon',
];

/** పూజ, but not the honorific పూజ్యులు. */
const PUJA = /పూజ(?!్య)/u;

export function isReligionStory(...parts: string[]): boolean {
  const text = parts.join(' ').toLowerCase();
  if (!text.trim()) return false;
  if (PUJA.test(text)) return true;
  return PHRASES.some((phrase) => text.includes(phrase.toLowerCase()));
}
