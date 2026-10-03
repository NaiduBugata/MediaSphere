/** India has no daylight-saving time. */
const IST_OFFSET_MS = (5 * 60 + 30) * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;

export const FOLLOW_UP_TEMPLATE = 'visit_followup_en';
export const FOLLOW_UP_SENT = 'Follow-up message sent successfully.';
/** Automatic reminder hour for a visit at or after 7:00 AM, or with no time. */
export const FOLLOW_UP_HOUR = 7;
/** A visit earlier than 7:00 AM is reminded this many hours beforehand. */
export const EARLY_LEAD_HOURS = 3;

export interface FollowUpVisit {
  id: string;
  title: string;
  place: string;
  visitDate: string;
  visitTime: string;
  leadPhone: string;
  /** Extra follow-up numbers. A visit can message more than one person. */
  leadPhones?: string[];
  followUpAutoDay: string;
}

/** Every distinct mobile on the visit. The same number is not messaged twice. */
export function listedPhones(visit: Pick<FollowUpVisit, 'leadPhone' | 'leadPhones'>): string[] {
  const seen = new Set<string>();
  const phones: string[] = [];
  for (const value of [...(visit.leadPhones || []), visit.leadPhone || '']) {
    const digits = String(value || '').replace(/\D/g, '');
    if (digits.length < 10 || seen.has(digits)) continue;
    seen.add(digits);
    phones.push(digits);
  }
  return phones;
}

/** When the automatic reminder for this visit should go out. Null when the visit has no date. */
export function followUpDueAt(visitDate: string, visitTime: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(visitDate)) return null;
  const start = firstMinutes(visitTime);
  let day = visitDate;
  let minutes = FOLLOW_UP_HOUR * 60;
  if (start !== null && start < FOLLOW_UP_HOUR * 60) {
    const shifted = start - EARLY_LEAD_HOURS * 60;
    if (shifted < 0) {
      day = shiftDay(visitDate, -1);
      minutes = shifted + 24 * 60;
    } else {
      minutes = shifted;
    }
  }
  return istDate(day, minutes);
}

/** True once the reminder time has passed and the visit day has not ended, and it has not already been sent. */
export function isAutoDue(visit: FollowUpVisit, now: Date): boolean {
  if (!listedPhones(visit).length || !visit.visitDate || visit.followUpAutoDay === visit.visitDate) return false;
  const due = followUpDueAt(visit.visitDate, visit.visitTime);
  if (!due || now.getTime() < due.getTime()) return false;
  const end = istDate(shiftDay(visit.visitDate, 1), 0);
  return now.getTime() < end.getTime();
}

export function followUpParameters(visit: Pick<FollowUpVisit, 'title' | 'place' | 'visitTime'>): Record<string, string> {
  return {
    title: templateValue(visit.title, 'Scheduled visit'),
    place: templateValue(visit.place, 'as scheduled'),
    time: templateValue(displayTime(visit.visitTime), 'as scheduled'),
  };
}

function templateValue(value: string, fallback: string): string {
  const cleaned = value.replace(/[\r\n\t]+/g, ' ').replace(/ {4,}/g, '   ').trim().slice(0, 1024);
  return cleaned || fallback;
}

function displayTime(value: string): string {
  return value
    .split('-')
    .map((part) => {
      const match = part.match(/^(\d{2}):(\d{2})$/);
      if (!match) return '';
      const hour = Number(match[1]);
      return `${hour % 12 || 12}:${match[2]} ${hour < 12 ? 'AM' : 'PM'}`;
    })
    .filter(Boolean)
    .join(' - ');
}

function firstMinutes(visitTime: string): number | null {
  const match = visitTime.match(/^(\d{2}):(\d{2})/);
  if (!match) return null;
  const minutes = Number(match[1]) * 60 + Number(match[2]);
  return minutes >= 0 && minutes < 24 * 60 ? minutes : null;
}

function shiftDay(iso: string, days: number): string {
  const [year, month, day] = iso.split('-').map(Number);
  const utc = new Date(Date.UTC(year, month - 1, day) + days * DAY_MS);
  return utc.toISOString().slice(0, 10);
}

function istDate(isoDay: string, minutes: number): Date {
  const [year, month, day] = isoDay.split('-').map(Number);
  const hour = Math.floor(minutes / 60);
  const minute = minutes % 60;
  return new Date(Date.UTC(year, month - 1, day, hour, minute) - IST_OFFSET_MS);
}
