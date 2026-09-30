import { BadRequestException } from '@nestjs/common';
import { truthy } from '../common/utils/truthy';
import { calendarDay, zoneParts } from '../reports/report-stats';
import { normalizePhone, sendTemplateMessage } from '../whatsapp/whatsapp.send';

export const BIRTHDAY_TIMEZONE = 'Asia/Kolkata';
/** A failed wish is retried on later checks the same day, up to this many tries. */
export const MAX_TRIES_PER_DAY = 3;

export type WishLanguage = 'en' | 'te';

export interface WishRecord {
  day: string;
  status: 'sent' | 'failed';
  tries: number;
  at: string;
  messageId: string | null;
  error: string | null;
  manual: boolean;
}

export interface BirthdayContact {
  id: string;
  name: string;
  phone: string;
  /** "MM-DD" */
  birthday: string;
  birthYear: number | null;
  place: string;
  designation: string;
  notes: string;
  language: WishLanguage;
  createdAt: string;
  lastWish: WishRecord | null;
  /** When this person last wrote to the business number. Only the time is kept, never the message. */
  lastInboundAt: string | null;
}

/** WhatsApp accepts free text only within 24 hours of the person's last message; otherwise a template is needed. */
export const FREE_TEXT_WINDOW_MS = 24 * 60 * 60 * 1000;

export function freeTextOpen(lastInboundAt: string | null, now = new Date()): boolean {
  const at = lastInboundAt ? Date.parse(lastInboundAt) : NaN;
  return Number.isFinite(at) && now.getTime() - at < FREE_TEXT_WINDOW_MS;
}

/** Automatic wishes run wherever WhatsApp can send, unless BIRTHDAY_WISHES_ENABLED=false. */
export function birthdayWishesEnabled(env: NodeJS.ProcessEnv = process.env): boolean {
  const raw = (env.BIRTHDAY_WISHES_ENABLED ?? '').trim();
  return (raw === '' || truthy(raw)) && whatsappSenderReady(env);
}

/** Enough to send one message. WHATSAPP_RECIPIENTS is not needed: wishes go to the contact list. */
export function whatsappSenderReady(env: NodeJS.ProcessEnv = process.env): boolean {
  return truthy(env.WHATSAPP_ENABLED)
    && Boolean((env.WHATSAPP_ACCESS_TOKEN || '').trim())
    && Boolean((env.WHATSAPP_PHONE_NUMBER_ID || '').trim());
}

/** Local hour (India time) from which the day's wishes go out. */
export function wishHour(env: NodeJS.ProcessEnv = process.env): number {
  const raw = (env.BIRTHDAY_HOUR ?? '').trim();
  const hour = Number(raw || '7');
  return Number.isInteger(hour) && hour >= 0 && hour <= 20 ? hour : 7;
}

/** A 10-digit Indian mobile gets the 91 country code; anything else must already include its country code. */
export function normalizeContactPhone(value: string): string {
  const cleaned = String(value || '').replace(/[\s()+-]/g, '');
  if (/^[6-9]\d{9}$/.test(cleaned)) return `91${cleaned}`;
  if (/^0[6-9]\d{9}$/.test(cleaned)) return `91${cleaned.slice(1)}`;
  try {
    return normalizePhone(cleaned);
  } catch {
    throw new BadRequestException('Phone must be a 10-digit mobile number, or a number with its country code.');
  }
}

export function maskPhone(phone: string): string {
  const digits = String(phone || '').replace(/\D/g, '');
  return digits.length > 4 ? `${digits.slice(0, 2)}******${digits.slice(-2)}` : '****';
}

/** Accepts 2026-09-30 (date picker), 30-09-1995, 30/09/1995, or 30-09 when the year is unknown. */
export function parseBirthday(value: string): { birthday: string; birthYear: number | null } {
  const text = String(value || '').trim();
  let year: number | null = null;
  let month = 0;
  let day = 0;
  let m = text.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (m) {
    [year, month, day] = [Number(m[1]), Number(m[2]), Number(m[3])];
  } else if ((m = text.match(/^(\d{1,2})[-/.](\d{1,2})(?:[-/.](\d{4}))?$/))) {
    [day, month] = [Number(m[1]), Number(m[2])];
    year = m[3] ? Number(m[3]) : null;
  } else {
    throw new BadRequestException('Birthday must be a date like 30-09-1995, or 30-09 if the year is not known.');
  }
  const checkYear = year ?? 2024;
  const date = new Date(Date.UTC(checkYear, month - 1, day));
  if (month < 1 || month > 12 || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) {
    throw new BadRequestException('Birthday is not a real calendar date.');
  }
  if (year !== null && (year < 1900 || year > new Date().getUTCFullYear())) {
    throw new BadRequestException('Birthday year is out of range.');
  }
  return { birthday: `${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`, birthYear: year };
}

export function todayInIndia(now = new Date()): string {
  return calendarDay(now, BIRTHDAY_TIMEZONE);
}

export function hourInIndia(now = new Date()): number {
  return Number(zoneParts(now, BIRTHDAY_TIMEZONE).hour);
}

/** 29 February birthdays are wished on 28 February in other years. */
export function isBirthdayOn(birthday: string, isoDay: string): boolean {
  const [year, month, day] = isoDay.split('-').map(Number);
  const today = `${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  if (birthday === today) return true;
  const leap = (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
  return birthday === '02-29' && today === '02-28' && !leap;
}

/** Birthday today, not yet wished today, and not out of retries. */
export function isDue(contact: BirthdayContact, isoDay: string): boolean {
  if (!isBirthdayOn(contact.birthday, isoDay)) return false;
  const wish = contact.lastWish;
  if (!wish || wish.day !== isoDay) return true;
  return wish.status !== 'sent' && wish.tries < MAX_TRIES_PER_DAY;
}

/** Approved Meta templates; both take one named parameter, {{name}}, and end with the MP's sign-off. */
export function wishTemplate(language: WishLanguage, env: NodeJS.ProcessEnv = process.env): { name: string; language: string } {
  if (language === 'te') return { name: (env.BIRTHDAY_TEMPLATE_TE || 'bday_wishes').trim(), language: 'te' };
  return { name: (env.BIRTHDAY_TEMPLATE_EN || 'bday_wishes_en').trim(), language: 'en' };
}

export async function sendBirthdayWish(
  contact: Pick<BirthdayContact, 'name' | 'phone' | 'language'>,
  fetchImpl: typeof fetch = fetch,
  env: NodeJS.ProcessEnv = process.env,
): Promise<{ messageId: string | null }> {
  const template = wishTemplate(contact.language, env);
  const data = await sendTemplateMessage(contact.phone, template.name, {
    language: template.language,
    namedParameters: { name: contact.name },
    fetchImpl,
    env,
  });
  const messages = Array.isArray(data.messages) ? data.messages : [];
  const id = messages.length ? (messages[0] as Record<string, unknown>).id : null;
  return { messageId: id ? String(id) : null };
}
