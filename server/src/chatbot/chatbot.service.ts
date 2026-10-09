import { Injectable, Logger, Optional } from '@nestjs/common';
import { DatabaseService } from '../database/database.service';
import { ArticleRepository } from '../database/repositories/article.repository';
import { hasAssemblySegment } from '../pipeline/native/constituency';
import { FOLLOW_UP_SENT } from '../visits/visit-followup';
import { VisitFollowupService } from '../visits/visit-followup.service';
import { formatVisitTime } from '../visits/visits-import';
import { parseWebhookPayload, type WhatsAppEvent } from '../whatsapp/whatsapp.parser';
import { replyRecipients, staffDirectoryLoaded } from '../whatsapp/whatsapp.audience';
import { normalizePhone, sendReplyList, type MenuRow } from '../whatsapp/whatsapp.send';
import { newestFirst, toBrief, type NewsBrief } from './news-context';

const RECORDS = 'jv_records';
const TOP = 5;
const NEWS_CACHE_MS = 60_000;
const CONVERSATION_GAP_MS = 4 * 60 * 60 * 1000;
const DEFAULT_ADDRESSEE = 'Sri. Lavu Sri Krishna Devarayalu Sir';
const MENU_PROMPT = 'Tap a section. The reply stays in this chat.';
export const MAIN_MENU_TEXT = '*Main menu*\n\nHere are the options.';
export const MORE_MENU_TEXT = '*More options*\n\nHere are the options available.';

export const MORE_BUTTON: MenuRow = { id: 'more', title: 'More', description: 'Constituency, campaigns, analytics' };
export const HOME_BUTTON: MenuRow = { id: 'home', title: 'Main menu', description: 'News, visits, and grievances' };
export const FOLLOW_UP_ROW: MenuRow = { id: 'follow_up', title: 'Follow up', description: 'Message the visit leads' };
export const MAIN_BUTTONS: MenuRow[] = [
  { id: 'news', title: 'News', description: 'Latest stories' },
  { id: 'visits', title: 'Visits', description: 'Scheduled visits' },
  { id: 'grievances', title: 'Grievances', description: 'Saved grievances' },
  { id: 'projects', title: 'Projects & reports', description: 'Projects and reports' },
  MORE_BUTTON,
];
export const MORE_BUTTONS: MenuRow[] = [
  { id: 'constituency', title: 'Constituency', description: 'People and places' },
  { id: 'campaigns', title: 'Campaigns', description: 'Campaign updates' },
  { id: 'analytics', title: 'Analytics', description: 'What the news is about' },
  HOME_BUTTON,
];
export const VISIT_BUTTONS: MenuRow[] = [FOLLOW_UP_ROW, ...MAIN_BUTTONS];

const CHOICE_BUTTONS: MenuRow[] = [
  ...MAIN_BUTTONS,
  ...MORE_BUTTONS,
  FOLLOW_UP_ROW,
  { id: 'menu', title: 'More' },
];

export type MenuId = 'grievances' | 'projects' | 'news' | 'constituency' | 'campaigns' | 'analytics' | 'visits';
export type MenuChoice = MenuId | 'more' | 'home' | 'menu' | 'follow_up';

const RECORD_SECTION: Partial<Record<MenuId, 'grievances' | 'projects' | 'people' | 'campaigns' | 'visits'>> = {
  grievances: 'grievances',
  projects: 'projects',
  constituency: 'people',
  campaigns: 'campaigns',
  visits: 'visits',
};

const SECTION_TITLE: Record<MenuId, string> = {
  grievances: 'Grievances',
  projects: 'Projects & reports',
  news: 'News',
  constituency: 'Constituency',
  campaigns: 'Campaigns',
  analytics: 'Analytics',
  visits: 'Visits',
};

const TEXT_ALIASES: Record<string, MenuChoice> = {
  grievance: 'grievances',
  grievances: 'grievances',
  project: 'projects',
  projects: 'projects',
  'projects & reports': 'projects',
  'projects and reports': 'projects',
  report: 'projects',
  reports: 'projects',
  news: 'news',
  'latest news': 'news',
  update: 'news',
  updates: 'news',
  'latest updates': 'news',
  visit: 'visits',
  visits: 'visits',
  'main menu': 'home',
  menu: 'home',
  'follow up': 'follow_up',
  followup: 'follow_up',
  constituency: 'constituency',
  people: 'constituency',
  more: 'more',
  campaign: 'campaigns',
  campaigns: 'campaigns',
  analytic: 'analytics',
  analytics: 'analytics',
};

export interface MenuRecord {
  title: string;
  detail: string;
  status: string;
  date: string;
}

export interface ChatbotDeps {
  env?: NodeJS.ProcessEnv;
  fetchImpl?: typeof fetch;
  news?: NewsBrief[];
  records?: Partial<Record<'grievances' | 'projects' | 'people' | 'campaigns' | 'visits', MenuRecord[]>>;
  now?: () => Date;
}

@Injectable()
export class ChatbotService {
  private readonly logger = new Logger(ChatbotService.name);
  private readonly answered = new Set<string>();
  private readonly inflight = new Set<string>();
  private readonly queues = new Map<string, Promise<void>>();
  private readonly lastReplyAt = new Map<string, number>();
  /** Visit messages go out after the menu reply, so a Follow up tap cannot freeze this chat. */
  private followUps: Promise<void> = Promise.resolve();
  private newsCache: { at: number; briefs: NewsBrief[] } | null = null;

  constructor(
    @Optional() private readonly articles?: ArticleRepository,
    @Optional() private readonly db?: DatabaseService,
    @Optional() private readonly followUp?: VisitFollowupService,
  ) {}

  /** Starts a reply after the webhook has already been acknowledged. Never throws. */
  consider(payload: unknown, deps: ChatbotDeps = {}): void {
    void this.handle(payload, deps).catch((err) => {
      this.logger.warn(err instanceof Error ? err.message : 'Chatbot reply failed.');
    });
  }

  async handle(payload: unknown, deps: ChatbotDeps = {}): Promise<void> {
    const env = deps.env || process.env;
    if (!chatbotEnabled(env)) return;
    const allowed = allowlist(env);
    if (!allowed.length) {
      this.logger.warn(staffDirectoryLoaded()
        ? 'Chatbot replies are off because no admin numbers are set.'
        : 'Chatbot replies are off because WHATSAPP_RECIPIENTS is empty.');
      return;
    }
    let events: WhatsAppEvent[] = [];
    try {
      if (payload && typeof payload === 'object') {
        events = parseWebhookPayload(payload as Record<string, unknown>);
      }
    } catch {
      return;
    }
    for (const event of events) {
      if (event.event_category !== 'message' || !event.sender_wa_id || !event.message_id) continue;
      if (!allowed.includes(digits(event.sender_wa_id))) {
        this.logger.warn(`Ignored chatbot message from ${maskPhone(event.sender_wa_id)}.`);
        continue;
      }
      await this.enqueue(event.sender_wa_id, () => this.replyTo(event, env, deps));
    }
  }

  private async replyTo(event: WhatsAppEvent, env: NodeJS.ProcessEnv, deps: ChatbotDeps): Promise<void> {
    const messageId = event.message_id || '';
    if (!messageId || this.answered.has(messageId) || this.inflight.has(messageId)) return;
    this.inflight.add(messageId);
    const sender = event.sender_wa_id || '';
    const now = (deps.now || (() => new Date()))();
    const last = this.lastReplyAt.get(sender);
    const opening = last === undefined || now.getTime() - last > CONVERSATION_GAP_MS;
    const fetchImpl = replyFetch(deps.fetchImpl || fetch);
    try {
      const choice = menuChoice(event);
      if (choice === 'follow_up') {
        await this.replyFollowUp(sender, fetchImpl, env, deps);
      } else if (choice === 'more') {
        await this.sendMore(sender, fetchImpl, env);
      } else if (choice === 'home' || choice === 'menu') {
        await this.sendMenu(sender, MAIN_MENU_TEXT, fetchImpl, env);
      } else if (choice) {
        const body = await this.renderSection(choice, deps);
        const rows = choice === 'visits' ? VISIT_BUTTONS : MAIN_BUTTONS;
        await sendReplyList(sender, body, rows, { fetchImpl, env });
      } else {
        const lead = opening ? `${openingLine(now, env)}\n\n${MENU_PROMPT}` : MAIN_MENU_TEXT;
        await this.sendMenu(sender, lead, fetchImpl, env);
      }
      this.answered.add(messageId);
      this.lastReplyAt.set(sender, now.getTime());
      this.logger.log(`Chatbot replied to ${maskPhone(sender)}.`);
    } catch (err) {
      this.logger.warn(
        `Chatbot reply was not delivered to ${maskPhone(sender)}: ${err instanceof Error ? err.message : 'send failed'}`,
      );
    } finally {
      this.inflight.delete(messageId);
    }
  }

  private async replyFollowUp(
    sender: string,
    fetchImpl: typeof fetch,
    env: NodeJS.ProcessEnv,
    deps: ChatbotDeps,
  ): Promise<void> {
    if (this.followUp && typeof this.followUp.readyToSend === 'function') {
      let ready = false;
      try {
        ready = await this.followUp.readyToSend();
      } catch (err) {
        this.logger.warn(`Visit follow-up failed: ${err instanceof Error ? err.message : 'send failed'}`);
      }
      if (!ready) {
        const body = await this.renderSection('visits', deps);
        await sendReplyList(sender, body, VISIT_BUTTONS, { fetchImpl, env });
        return;
      }
      await this.sendMenu(sender, FOLLOW_UP_SENT, fetchImpl, env);
      const followUp = this.followUp;
      this.followUps = this.followUps.then(() => followUp.sendAll(fetchImpl).then((result) => {
        if (!result.sent) this.logger.warn('Visit follow-up was not accepted.');
      }, (err) => {
        this.logger.warn(`Visit follow-up failed: ${err instanceof Error ? err.message : 'send failed'}`);
      }));
      return;
    }
    let sent = 0;
    try {
      if (this.followUp && this.followUp.sendAll) sent = (await this.followUp.sendAll(fetchImpl)).sent;
    } catch (err) {
      this.logger.warn(`Visit follow-up failed: ${err instanceof Error ? err.message : 'send failed'}`);
    }
    if (sent > 0) {
      await this.sendMenu(sender, FOLLOW_UP_SENT, fetchImpl, env);
      return;
    }
    const body = await this.renderSection('visits', deps);
    await sendReplyList(sender, body, VISIT_BUTTONS, { fetchImpl, env });
  }

  private async sendMenu(
    sender: string,
    lead: string,
    fetchImpl: typeof fetch,
    env: NodeJS.ProcessEnv,
  ): Promise<void> {
    await sendReplyList(sender, lead, MAIN_BUTTONS, { fetchImpl, env });
  }

  private async sendMore(
    sender: string,
    fetchImpl: typeof fetch,
    env: NodeJS.ProcessEnv,
  ): Promise<void> {
    await sendReplyList(sender, MORE_MENU_TEXT, MORE_BUTTONS, {
      button: 'More',
      header: 'More options',
      section: 'More options',
      fetchImpl,
      env,
    });
  }

  private async renderSection(choice: MenuId, deps: ChatbotDeps): Promise<string> {
    const title = SECTION_TITLE[choice];
    if (choice === 'news') return formatSection(title, (await this.newsBriefs(deps)).map(newsLine));
    if (choice === 'analytics') return formatSection(title, (await this.newsBriefs(deps)).map(analyticsLine));
    const section = RECORD_SECTION[choice];
    const rows = section ? await this.sectionRecords(section, deps) : [];
    return formatSection(title, rows.map(recordLine));
  }

  private async newsBriefs(deps: ChatbotDeps): Promise<NewsBrief[]> {
    const briefs = deps.news || await this.loadNews();
    return newestFirst(briefs).slice(0, TOP);
  }

  private async sectionRecords(
    section: 'grievances' | 'projects' | 'people' | 'campaigns' | 'visits',
    deps: ChatbotDeps,
  ): Promise<MenuRecord[]> {
    if (deps.records) return latestRecords(deps.records[section] || []);
    if (!this.db) return [];
    try {
      const ok = await this.db.ensureConnected();
      if (!ok) return [];
      const rows = await this.db.collection(RECORDS).find({ section }).sort({ createdAt: -1 }).limit(TOP).toArray();
      return rows.map((row) => ({
        title: text(row.title),
        detail: [formatVisitTime(text(row.visitTime)), text(row.place), text(row.detail)].filter(Boolean).join(' – '),
        status: text(row.status),
        date: text(row.visitDate) || text(row.createdAt),
      }));
    } catch (err) {
      this.logger.warn(`Chatbot could not load ${section}: ${err instanceof Error ? err.message : 'database error'}`);
      return [];
    }
  }

  private async loadNews(): Promise<NewsBrief[]> {
    if (!this.articles) return [];
    if (this.newsCache && Date.now() - this.newsCache.at < NEWS_CACHE_MS) return this.newsCache.briefs;
    try {
      const docs = await this.articles.findAll();
      const briefs = docs
        .filter((doc) => hasAssemblySegment(doc))
        .map((doc) => toBrief(doc as Record<string, unknown>))
        .filter((brief): brief is NewsBrief => brief !== null);
      this.newsCache = { at: Date.now(), briefs };
      this.logger.log(`Chatbot news loaded (${briefs.length} articles).`);
      return briefs;
    } catch (err) {
      this.logger.warn(`Chatbot could not load news: ${err instanceof Error ? err.message : 'database error'}`);
      return this.newsCache?.briefs || [];
    }
  }

  private enqueue(sender: string, work: () => Promise<void>): Promise<void> {
    const previous = this.queues.get(sender) ?? Promise.resolve();
    const current = previous.then(work, work);
    this.queues.set(sender, current.then(() => undefined, () => undefined));
    return current;
  }
}

export function chatbotEnabled(env: NodeJS.ProcessEnv): boolean {
  const flag = (env.CHATBOT_ENABLED ?? 'true').trim().toLowerCase();
  const whatsapp = (env.WHATSAPP_ENABLED || '').trim().toLowerCase();
  return ['1', 'true', 'yes', 'on'].includes(flag)
    && ['1', 'true', 'yes', 'on'].includes(whatsapp);
}

export function menuChoice(event: WhatsAppEvent): MenuChoice | null {
  const reply = event.interactive_response?.list_reply || event.interactive_response?.button_reply;
  if (reply && typeof reply === 'object') {
    const row = reply as Record<string, unknown>;
    const id = text(row.id).toLowerCase();
    const match = CHOICE_BUTTONS.find((button) => button.id === id);
    if (match) return match.id as MenuChoice;
    const fromTitle = menuFromText(text(row.title) || event.message_text || '');
    if (fromTitle) return fromTitle;
  }
  if (event.event_type === 'text' || event.event_type === 'button' || event.event_type === 'interactive') {
    return menuFromText(event.message_text || '');
  }
  return null;
}

export function menuFromText(value: string): MenuChoice | null {
  const key = value.toLowerCase().replace(/[^\p{L}\p{N}&]+/gu, ' ').replace(/\s+/g, ' ').trim();
  return TEXT_ALIASES[key] || null;
}

export function formatSection(title: string, items: string[]): string {
  if (!items.length) return `*${title}*\nNothing saved yet.`;
  const lines = items.slice(0, TOP).map((item, index) => `${index + 1}. ${item}`);
  return `*${title}*\nLatest ${lines.length}\n\n${lines.join('\n\n')}`;
}

function newsLine(brief: NewsBrief): string {
  const meta = [plain(brief.place), shortWhen(brief.publishedAt || brief.collectedAt)].filter(Boolean).join(' · ');
  return [bold(brief.title), plain(brief.summary), meta].filter(Boolean).join('\n');
}

function analyticsLine(brief: NewsBrief): string {
  const signal = [plain(brief.sentiment), plain(brief.category), brief.severity ? `severity ${plain(brief.severity)}` : '']
    .filter(Boolean)
    .join(' · ');
  const meta = [plain(brief.place), shortWhen(brief.publishedAt || brief.collectedAt)].filter(Boolean).join(' · ');
  return [bold(brief.title), signal, meta].filter(Boolean).join('\n');
}

function recordLine(row: MenuRecord): string {
  const meta = [plain(row.status), shortWhen(row.date)].filter(Boolean).join(' · ');
  return [bold(row.title), plain(row.detail), meta].filter(Boolean).join('\n');
}

function latestRecords(rows: MenuRecord[]): MenuRecord[] {
  return [...rows].sort((left, right) => timeOf(right.date) - timeOf(left.date)).slice(0, TOP);
}

function bold(value: string): string {
  const cleaned = plain(value);
  return cleaned ? `*${cleaned}*` : '';
}

function plain(value: string): string {
  return clip(value.replace(/https?:\/\/\S+/gi, ' ').replace(/\s+/g, ' ').trim(), 180);
}

function clip(value: string, max: number): string {
  return value.length <= max ? value : `${value.slice(0, max - 1).trimEnd()}…`;
}

function shortWhen(value: string): string {
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return '';
  return new Date(parsed).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'Asia/Kolkata',
  });
}

function timeOf(value: string): number {
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

const REPLY_TIMEOUT_MS = 20_000;

/** A stuck WhatsApp call must not hold later replies from the same admin. */
function replyFetch(fetchImpl: typeof fetch): typeof fetch {
  return (async (input, init) => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), REPLY_TIMEOUT_MS);
    try {
      return await fetchImpl(input, { ...init, signal: controller.signal });
    } finally {
      clearTimeout(timer);
    }
  }) as typeof fetch;
}

function allowlist(env: NodeJS.ProcessEnv): string[] {
  if (staffDirectoryLoaded()) return replyRecipients();
  const numbers: string[] = [];
  for (const item of (env.WHATSAPP_RECIPIENTS || '').split(',')) {
    const trimmed = item.trim();
    if (!trimmed) continue;
    try {
      numbers.push(normalizePhone(trimmed));
    } catch {
      // Invalid entries are ignored. They are not logged.
    }
  }
  return numbers;
}

function digits(value: string): string {
  try {
    return normalizePhone(value);
  } catch {
    return '';
  }
}

function maskPhone(value: string): string {
  const phone = value.replace(/\D/g, '');
  if (phone.length < 6) return '******';
  return `${phone.slice(0, 2)}***${phone.slice(-2)}`;
}

export function timeGreeting(now: Date): string {
  const hour = Number(new Intl.DateTimeFormat('en-GB', { hour: 'numeric', hourCycle: 'h23', timeZone: 'Asia/Kolkata' }).format(now));
  if (hour >= 5 && hour < 12) return 'Good morning';
  if (hour >= 12 && hour < 17) return 'Good afternoon';
  return 'Good evening';
}

export function openingLine(now: Date, env: NodeJS.ProcessEnv): string {
  const addressee = (env.CHATBOT_ADDRESSEE || DEFAULT_ADDRESSEE).trim() || DEFAULT_ADDRESSEE;
  return `${timeGreeting(now)}, ${addressee}! I'm your Media Assistant.`;
}

const GREETING_WORDS = new Set([
  'hi', 'hii', 'hiii', 'hello', 'helo', 'hey', 'hai', 'namaste', 'namasthe', 'namaskaram', 'namaskar',
  'good', 'morning', 'afternoon', 'evening', 'gm', 'sir', 'garu', 'there', 'assistant', 'bot',
  'నమస్కారం', 'నమస్తే', 'హాయ్', 'హలో', 'శుభోదయం', 'సార్', 'గారు',
]);

/** True for a bare greeting such as "Hi", "Hello sir", "Good evening", or "నమస్కారం". */
export function isGreetingOnly(text: string): boolean {
  const words = text.toLowerCase().replace(/[^\p{L}\p{M}\p{N}\s]/gu, ' ').split(/\s+/).filter(Boolean);
  return words.length > 0 && words.length <= 4 && words.every((word) => GREETING_WORDS.has(word));
}

export function toWhatsAppFormat(value: string): string {
  return value
    .replace(/\*\*(.+?)\*\*/g, '*$1*')
    .replace(/__(.+?)__/g, '_$1_')
    .replace(/^#{1,6}\s+/gm, '')
    .trim();
}
