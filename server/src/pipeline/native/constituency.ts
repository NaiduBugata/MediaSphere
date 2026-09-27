import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { discoverGroqApiKeys } from '../../ai/groq-keys';

interface Dict {
  scoring?: Record<string, number>;
  primary_keywords?: string[];
  assembly_segments?: string[];
  mandals?: string[];
  villages?: string[];
  district_aliases?: string[];
  negative_keywords?: string[];
  negative_categories?: string[];
  constituency?: string;
  ai_validation?: { enabled?: boolean };
}

export interface ScoreResult {
  valid: boolean;
  score: number;
  reason: string;
  ai_decision?: string | null;
}

let cached: Dict | null = null;

export function loadDictionary(): Dict {
  if (cached) return cached;
  const path = process.env.LOCATION_DICTIONARY_PATH
    ? resolve(process.cwd(), process.env.LOCATION_DICTIONARY_PATH)
    : resolve(__dirname, '../data/location_dictionary.json');
  cached = JSON.parse(readFileSync(path, 'utf8')) as Dict;
  return cached;
}

function findMatches(haystack: string, keywords: string[]): string[] {
  const found: string[] = [];
  const hayLower = haystack.toLowerCase();
  for (const keyword of keywords) {
    if (!keyword) continue;
    if ([...keyword].some((ch) => ch.charCodeAt(0) > 127)) {
      if (haystack.includes(keyword) || hayLower.includes(keyword)) found.push(keyword);
      continue;
    }
    const pattern = keyword.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp(`(?<!\\w)${pattern}(?!\\w)`, 'i');
    if (re.test(hayLower) || (keyword.includes(' ') && hayLower.includes(keyword.toLowerCase()))) {
      found.push(keyword);
    }
  }
  return found;
}

/** Port of ConstituencyValidator.score_text. */
export function scoreConstituency(text: string, category = ''): ScoreResult {
  const data = loadDictionary();
  const weights = {
    primary: data.scoring?.primary ?? 10,
    assembly: data.scoring?.assembly ?? 6,
    mandal: data.scoring?.mandal ?? 4,
    village: data.scoring?.village ?? 3,
    district_alias: data.scoring?.district_alias ?? 2,
    negative_penalty: data.scoring?.negative_penalty ?? 8,
  };
  const accept = Number(
    process.env.CONSTITUENCY_SCORE_THRESHOLD ||
      process.env.SAKSHI_CONSTITUENCY_SCORE_THRESHOLD ||
      data.scoring?.accept_threshold ||
      6,
  );
  const borderline = data.scoring?.borderline_low ?? 3;
  const override = data.scoring?.negative_override_score ?? 12;

  const primary = findMatches(text, data.primary_keywords || []);
  const assembly = findMatches(text, data.assembly_segments || []);
  const mandals = findMatches(text, data.mandals || []);
  const villages = findMatches(text, data.villages || []);
  const district = findMatches(text, data.district_aliases || []);
  const negative = findMatches(text, data.negative_keywords || []);
  for (const neg of data.negative_categories || []) {
    if (neg && category.toLowerCase().includes(neg.toLowerCase()) && !negative.includes(neg)) {
      negative.push(neg);
    }
  }

  let score = 0;
  if (primary.length) score += weights.primary;
  if (assembly.length) {
    score += weights.assembly;
    if (assembly.length > 1) score += Math.min(4, (assembly.length - 1) * 2);
  }
  if (mandals.length) {
    score += weights.mandal;
    if (mandals.length > 1) score += Math.min(4, (mandals.length - 1) * 2);
  }
  if (villages.length) {
    score += weights.village;
    if (villages.length > 1) score += Math.min(3, villages.length - 1);
  }
  if (district.length && !primary.length && !assembly.length && !mandals.length) {
    score += weights.district_alias;
  }
  if (negative.length && score < override) {
    return { valid: false, score: Math.max(0, score - weights.negative_penalty), reason: 'negative_filter' };
  }
  if (score >= accept) return { valid: true, score, reason: 'score_accept' };
  if (score >= borderline) return { valid: false, score, reason: 'borderline' };
  return { valid: false, score, reason: 'score_below_threshold' };
}

export function buildSearchableText(raw: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const key of ['title', 'description', 'summary', 'og_description', 'content', 'article', 'category']) {
    const value = raw[key];
    if (typeof value === 'string' && value.trim()) parts.push(value.trim());
  }
  if (Array.isArray(raw.tags)) parts.push(...raw.tags.map((item) => String(item).trim()).filter(Boolean));
  if (Array.isArray(raw.breadcrumb)) parts.push(...raw.breadcrumb.map((item) => String(item).trim()).filter(Boolean));
  else if (typeof raw.breadcrumb === 'string' && raw.breadcrumb.trim()) parts.push(raw.breadcrumb.trim());
  const location = raw.location;
  if (location && typeof location === 'object' && !Array.isArray(location)) {
    for (const key of ['district', 'mandal', 'village', 'town', 'state']) {
      const value = (location as Record<string, unknown>)[key];
      if (value) parts.push(String(value));
    }
  }
  return parts.join('\n');
}

function constituencyAiEnabled(useAi?: boolean): boolean {
  if (useAi !== undefined) return useAi;
  const env = (process.env.CONSTITUENCY_AI_VALIDATION || process.env.SAKSHI_AI_VALIDATION || '')
    .trim()
    .toLowerCase();
  if (['1', 'true', 'yes', 'on'].includes(env)) return true;
  if (['0', 'false', 'no', 'off'].includes(env)) return false;
  return loadDictionary().ai_validation?.enabled !== false;
}

function parseAiDecision(content: string): 'YES' | 'NO' | 'UNCERTAIN' {
  const upper = content.trim().toUpperCase();
  for (const token of ['YES', 'NO', 'UNCERTAIN'] as const) {
    if (upper.includes(token)) return token;
  }
  return 'UNCERTAIN';
}

/** Groq YES/NO/UNCERTAIN for scores between borderline_low and the accept threshold. */
export async function checkBorderlineConstituency(
  raw: Record<string, unknown>,
  text: string,
  fetchImpl: typeof fetch = fetch,
): Promise<'YES' | 'NO' | 'UNCERTAIN'> {
  const keys = discoverGroqApiKeys();
  if (!keys.length) return 'UNCERTAIN';
  const data = loadDictionary();
  const name = data.constituency || 'Narasaraopet Parliamentary Constituency';
  const title = String(raw.title || '').slice(0, 300);
  const prompt =
    `Does this Telugu/English news article primarily belong to the ` +
    `${name} in Andhra Pradesh (Palnadu district), ` +
    `including its assembly segments (Pedakurapadu, Chilakaluripet, ` +
    `Narasaraopet, Sattenapalle, Vinukonda, Gurazala, Macherla) and ` +
    `their mandals/villages?\n\n` +
    `Answer with exactly one word: YES, NO, or UNCERTAIN.\n\n` +
    `Title: ${title}\n\nArticle excerpt:\n${text.slice(0, 2500)}`;
  try {
    const response = await fetchImpl('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${keys[0]}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model:
          process.env.CONSTITUENCY_AI_VALIDATION_MODEL ||
          process.env.SAKSHI_AI_VALIDATION_MODEL ||
          'openai/gpt-oss-20b',
        temperature: 0,
        max_tokens: 10,
        messages: [
          {
            role: 'system',
            content:
              'You classify whether a news article is primarily about the Narasaraopet Parliamentary Constituency. Reply with only YES, NO, or UNCERTAIN.',
          },
          { role: 'user', content: prompt },
        ],
      }),
    });
    if (!response.ok) return 'UNCERTAIN';
    const body = (await response.json()) as { choices?: Array<{ message?: { content?: string } }> };
    return parseAiDecision(body.choices?.[0]?.message?.content || '');
  } catch {
    return 'UNCERTAIN';
  }
}

/** Full dictionary score plus the optional borderline Groq check. */
export async function validateConstituency(
  raw: Record<string, unknown>,
  fetchImpl: typeof fetch = fetch,
  useAi?: boolean,
): Promise<ScoreResult> {
  const category = String(raw.category || '');
  const result = scoreConstituency(buildSearchableText(raw), category);
  if (result.valid || result.reason !== 'borderline') return result;
  if (!constituencyAiEnabled(useAi)) return { ...result, reason: 'borderline_no_ai' };
  const decision = await checkBorderlineConstituency(raw, buildSearchableText(raw), fetchImpl);
  if (decision === 'YES') return { ...result, valid: true, reason: 'ai_yes', ai_decision: decision };
  if (decision === 'NO') return { ...result, valid: false, reason: 'ai_no', ai_decision: decision };
  return { ...result, valid: false, reason: 'ai_uncertain', ai_decision: decision };
}
