import { BadRequestException } from '@nestjs/common';
import { load } from 'cheerio';
import ExcelJS from 'exceljs';
import JSZip from 'jszip';
import type { VisitFileKind } from './visits.service';

export type VisitField = 'date' | 'place' | 'title' | 'detail';

export interface ImportedVisitRow {
  where: string;
  title: string;
  place: string;
  visitDate: string;
  detail: string;
}

export interface RejectedRow {
  where: string;
  reason: string;
}

/** The template's example row; left in by mistake it must not become a visit. */
export const TEMPLATE_EXAMPLE = {
  date: '28-09-2026',
  place: 'Vinukonda',
  title: 'Visit to Government Hospital (example row, delete it)',
  detail: 'Reviewed the new ward and met the doctors and staff.',
};

export const TEMPLATE_HEADERS = ['S.No', 'Date (DD-MM-YYYY)', 'Place', 'Purpose / Title', 'Details'];

export const MAX_IMPORT_ROWS = 5000;

interface Grid {
  label: (row: number) => string;
  rows: string[][];
}

const SERIAL_HEADER = /^(s\.?\s*no\.?|sl\.?\s*no\.?|no\.?|#|serial( no\.?)?|sr\.?\s*no\.?|క్రమ\s*సంఖ్య|వరుస\s*సంఖ్య|సంఖ్య)$/;

/** Checked in this order, so "Visit date" is a date and "Place of visit" is a place. */
const FIELD_WORDS: Array<[VisitField, string[]]> = [
  ['date', ['date', 'తేదీ', 'తేది']],
  ['detail', ['detail', 'description', 'remark', 'note', 'summary', 'outcome', 'వివరాలు', 'వివరణ', 'వ్యాఖ్య', 'గమనిక']],
  ['place', ['place', 'village', 'mandal', 'location', 'venue', 'area', 'town', 'ప్రదేశం', 'గ్రామం', 'మండలం', 'స్థలం', 'ప్రాంతం', 'ఊరు']],
  ['title', ['title', 'purpose', 'programme', 'program', 'event', 'subject', 'visit', 'activity', 'agenda', 'కార్యక్రమం', 'ఉద్దేశ్యం', 'ఉద్దేశం', 'విషయం', 'పర్యటన']],
];

function clean(value: string): string {
  return value.replace(/\u00a0/g, ' ').replace(/[ \t]+/g, ' ').replace(/\s*\n\s*/g, '\n').trim();
}

function fieldOf(header: string): VisitField | 'serial' | null {
  const text = clean(header).toLowerCase();
  if (!text) return null;
  if (SERIAL_HEADER.test(text)) return 'serial';
  for (const [field, words] of FIELD_WORDS) {
    if (words.some((word) => text.includes(word))) return field;
  }
  return null;
}

/** Column index per field, or null when this row is not a header. */
export function headerColumns(cells: string[]): Partial<Record<VisitField, number>> | null {
  const columns: Partial<Record<VisitField, number>> = {};
  cells.forEach((cell, index) => {
    if (cell.length > 60) return;
    const field = fieldOf(cell);
    if (field && field !== 'serial' && columns[field] === undefined) columns[field] = index;
  });
  const found = Object.keys(columns).length;
  const named = columns.title !== undefined || columns.place !== undefined;
  return named && found >= 2 ? columns : null;
}

const MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];

function monthOf(word: string): number {
  return MONTHS.indexOf(word.slice(0, 3).toLowerCase()) + 1;
}

function isoFrom(year: number, month: number, day: number): string | null {
  if (year < 100) year += 2000;
  if (year < 1990 || year > 2100 || month < 1 || month > 12 || day < 1 || day > 31) return null;
  const date = new Date(Date.UTC(year, month - 1, day));
  if (date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
  return date.toISOString().slice(0, 10);
}

/**
 * Day comes before month, as written in India: 05-10-2026 is 5 October.
 * Returns '' for an empty cell and null for text that is not a date.
 */
export function parseVisitDate(raw: string): string | null {
  const text = clean(raw).replace(/(\d)(st|nd|rd|th)\b/gi, '$1');
  if (!text) return '';
  let m = text.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[ T].*)?$/);
  if (m) return isoFrom(+m[1], +m[2], +m[3]);
  m = text.match(/^(\d{1,2})[-/. ](\d{1,2})[-/. ](\d{2}|\d{4})$/);
  if (m) return isoFrom(+m[3], +m[2], +m[1]);
  m = text.match(/^(\d{1,2})[-/ ]?([a-z]{3,9})\.?[-/ ,]*(\d{2}|\d{4})$/i);
  if (m && monthOf(m[2])) return isoFrom(+m[3], monthOf(m[2]), +m[1]);
  m = text.match(/^([a-z]{3,9})\.?[ -](\d{1,2}),?[ -](\d{2}|\d{4})$/i);
  if (m && monthOf(m[1])) return isoFrom(+m[3], monthOf(m[1]), +m[2]);
  if (/^\d{5}(\.\d+)?$/.test(text)) {
    const serial = Math.floor(Number(text));
    if (serial > 30000 && serial < 80000) return new Date(Date.UTC(1899, 11, 30) + serial * 86400000).toISOString().slice(0, 10);
  }
  return null;
}

function isExampleRow(row: ImportedVisitRow): boolean {
  return row.title === TEMPLATE_EXAMPLE.title && row.place === TEMPLATE_EXAMPLE.place;
}

/** Finds the header in each table and turns every following row into a visit, or a reason it was refused. */
export function rowsFromGrids(grids: Grid[]): { rows: ImportedVisitRow[]; rejected: RejectedRow[]; headerFound: boolean } {
  const rows: ImportedVisitRow[] = [];
  const rejected: RejectedRow[] = [];
  let columns: Partial<Record<VisitField, number>> | null = null;
  let width = 0;
  let headerFound = false;

  for (const grid of grids) {
    let start = 0;
    const headerAt = grid.rows.slice(0, 15).findIndex((cells) => headerColumns(cells));
    if (headerAt >= 0) {
      columns = headerColumns(grid.rows[headerAt]);
      width = grid.rows[headerAt].length;
      start = headerAt + 1;
      headerFound = true;
    } else if (!columns || Math.abs((grid.rows[0]?.length ?? 0) - width) > 1) {
      // A table without a header continues the previous one only when it has the same columns (PDF page breaks).
      continue;
    }
    const cols = columns as Partial<Record<VisitField, number>>;
    const cell = (cells: string[], field: VisitField) => (cols[field] === undefined ? '' : clean(cells[cols[field]] || ''));

    for (let index = start; index < grid.rows.length; index++) {
      const cells = grid.rows[index];
      if (!cells.some((value) => clean(value))) continue;
      if (headerColumns(cells)) continue;
      const where = grid.label(index);
      const rawDate = cell(cells, 'date');
      const place = cell(cells, 'place').slice(0, 120);
      const detail = cell(cells, 'detail').slice(0, 2000);
      let title = cell(cells, 'title').replace(/\n/g, ' ').slice(0, 200);
      if (!title && !place && !rawDate && !detail) continue;
      const visitDate = parseVisitDate(rawDate);
      if (visitDate === null) {
        rejected.push({ where, reason: `Date "${rawDate.slice(0, 40)}" is not a date like 28-09-2026.` });
        continue;
      }
      if (!title && place) title = `Visit to ${place.replace(/\n/g, ' ')}`.slice(0, 200);
      if (!title) {
        rejected.push({ where, reason: 'Purpose / Title and Place are both empty.' });
        continue;
      }
      const row = { where, title, place: place.replace(/\n/g, ', '), visitDate, detail };
      if (!isExampleRow(row)) rows.push(row);
      if (rows.length > MAX_IMPORT_ROWS) {
        throw new BadRequestException(`The file has more than ${MAX_IMPORT_ROWS} visits. Split it into smaller files.`);
      }
    }
  }
  return { rows, rejected, headerFound };
}

function excelCellText(value: ExcelJS.CellValue): string {
  if (value == null) return '';
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === 'object') {
    if ('richText' in value) return value.richText.map((part) => part.text).join('');
    if ('result' in value) return excelCellText(value.result as ExcelJS.CellValue);
    if ('text' in value) return String(value.text);
    if ('error' in value) return '';
  }
  return String(value);
}

async function excelGrids(buffer: Buffer): Promise<Grid[]> {
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.load(buffer as unknown as ArrayBuffer);
  const sheets = workbook.worksheets
    .filter((sheet) => sheet.state === 'visible' || !sheet.state)
    .map((sheet) => {
      const rows: string[][] = [];
      const rowNumbers: number[] = [];
      sheet.eachRow({ includeEmpty: false }, (row, rowNumber) => {
        const cells: string[] = [];
        for (let col = 1; col <= Math.max(row.cellCount, 1); col++) cells.push(excelCellText(row.getCell(col).value));
        rows.push(cells);
        rowNumbers.push(rowNumber);
      });
      return { name: sheet.name, rows, rowNumbers };
    });
  const withHeader = sheets.filter((sheet) => sheet.rows.slice(0, 15).some((cells) => headerColumns(cells))).length;
  return sheets.map(({ name, rows, rowNumbers }) => {
    const prefix = withHeader > 1 ? `Sheet "${name}", row ` : 'Row ';
    return { rows, label: (index: number) => `${prefix}${rowNumbers[index]}` };
  });
}

async function wordGrids(buffer: Buffer): Promise<Grid[]> {
  const zip = await JSZip.loadAsync(buffer);
  const xml = await zip.file('word/document.xml')?.async('string');
  if (!xml) throw new BadRequestException('The Word file could not be read. Save it as .docx and try again.');
  const $ = load(xml, { xml: true });
  const tables = $('w\\:tbl').filter((_, table) => $(table).parents('w\\:tbl').length === 0);
  const grids: Grid[] = [];
  tables.each((tableIndex, table) => {
    const rows: string[][] = [];
    $(table)
      .children('w\\:tr')
      .each((_, tr) => {
        const cells: string[] = [];
        $(tr)
          .children('w\\:tc')
          .each((__, tc) => {
            const paragraphs = $(tc)
              .find('w\\:p')
              .map((___, p) =>
                $(p)
                  .find('w\\:t, w\\:tab, w\\:br')
                  .map((____, node) => (node.tagName === 'w:t' ? $(node).text() : node.tagName === 'w:tab' ? ' ' : '\n'))
                  .get()
                  .join(''),
              )
              .get();
            cells.push(paragraphs.join('\n'));
            const span = Number($(tc).find('w\\:tcPr > w\\:gridSpan').attr('w:val') || 1);
            for (let extra = 1; extra < span; extra++) cells.push('');
          });
        rows.push(cells);
      });
    const prefix = tables.length > 1 ? `Table ${tableIndex + 1}, row ` : 'Row ';
    grids.push({ rows, label: (index) => `${prefix}${index + 1}` });
  });
  return grids;
}

export interface PdfTextItem {
  text: string;
  x: number;
  y: number;
  width: number;
  page: number;
}

/** pdf.js is ESM-only; this keeps a real import() even where TypeScript compiles to require() (the Jest config). */
const importEsm = new Function('specifier', 'return import(specifier)') as (specifier: string) => Promise<unknown>;

async function pdfTextItems(buffer: Buffer): Promise<PdfTextItem[]> {
  const pdfjs = (await importEsm('pdfjs-dist/legacy/build/pdf.mjs')) as typeof import('pdfjs-dist/legacy/build/pdf.mjs');
  const task = pdfjs.getDocument({ data: new Uint8Array(buffer), disableFontFace: true, useSystemFonts: false, verbosity: 0 });
  try {
    const doc = await task.promise;
    const items: PdfTextItem[] = [];
    for (let page = 1; page <= doc.numPages; page++) {
      const content = await (await doc.getPage(page)).getTextContent();
      for (const item of content.items) {
        if (!('str' in item) || !item.str.trim()) continue;
        items.push({ text: item.str, x: item.transform[4], y: item.transform[5], width: item.width, page });
      }
    }
    return items;
  } finally {
    await task.destroy();
  }
}

interface PdfLine {
  page: number;
  y: number;
  items: PdfTextItem[];
}

function joinItems(items: PdfTextItem[]): string {
  let text = '';
  let end: number | null = null;
  for (const item of items) {
    if (end !== null && item.x - end > 1.5 && !text.endsWith(' ') && !item.text.startsWith(' ')) text += ' ';
    text += item.text;
    end = item.x + item.width;
  }
  return text.trim();
}

/** Text pieces on one baseline, split where the gap is wider than normal word spacing. */
function lineChunks(line: PdfLine): PdfTextItem[][] {
  const chunks: PdfTextItem[][] = [];
  for (const item of line.items) {
    const last = chunks[chunks.length - 1];
    const prev = last?.[last.length - 1];
    if (prev && item.x - (prev.x + prev.width) < 6) last.push(item);
    else chunks.push([item]);
  }
  return chunks;
}

/**
 * Rebuilds the visits table from text positions, which works for ruled and unruled tables alike.
 * Column edges come from the header; a line with an empty S.No/Date cell continues the row above (wrapped text).
 */
export function gridFromPdfItems(items: PdfTextItem[]): Grid | null {
  const sorted = [...items].sort((a, b) => a.page - b.page || b.y - a.y || a.x - b.x);
  const lines: PdfLine[] = [];
  for (const item of sorted) {
    const line = lines[lines.length - 1];
    if (line && line.page === item.page && Math.abs(line.y - item.y) <= 3) line.items.push(item);
    else lines.push({ page: item.page, y: item.y, items: [item] });
  }
  lines.forEach((line) => line.items.sort((a, b) => a.x - b.x));

  let starts: number[] | null = null;
  let header: string[] | null = null;
  let anchor = -1;
  const rows: string[][] = [];
  const labels: string[] = [];
  let lastLine: PdfLine | null = null;
  const perPage = new Map<number, number>();

  for (const line of lines) {
    const chunks = lineChunks(line);
    const cells = chunks.map(joinItems);
    const columns = headerColumns(cells);
    if (columns) {
      if (!header) header = cells;
      starts = chunks.map((chunk, i) => (i === 0 ? -Infinity : (chunks[i - 1].at(-1)!.x + chunks[i - 1].at(-1)!.width + chunk[0].x) / 2));
      const serial = cells.findIndex((cell) => fieldOf(cell) === 'serial');
      anchor = serial >= 0 ? serial : (columns.date ?? -1);
      lastLine = null;
      continue;
    }
    if (!starts || !header) continue;
    const bounds = starts;
    const grouped: PdfTextItem[][] = bounds.map(() => []);
    for (const item of line.items) {
      let column = 0;
      for (let i = 0; i < bounds.length; i++) if (item.x + 1 >= bounds[i]) column = i;
      grouped[column].push(item);
    }
    const lineCells = grouped.map(joinItems);
    const near = lastLine && lastLine.page === line.page && lastLine.y - line.y < 30;
    if (anchor >= 0 && !lineCells[anchor] && rows.length) {
      if (!near) continue;
      const row = rows[rows.length - 1];
      lineCells.forEach((cell, i) => {
        if (cell) row[i] = row[i] ? `${row[i]}\n${cell}` : cell;
      });
      lastLine = line;
      continue;
    }
    if (anchor >= 0 && !lineCells[anchor]) continue;
    const count = (perPage.get(line.page) || 0) + 1;
    perPage.set(line.page, count);
    rows.push(lineCells);
    labels.push(`Page ${line.page}, row ${count}`);
    lastLine = line;
  }
  if (!header) return null;
  // Wrapped Place/Title lines were joined with line breaks; only Details keeps them.
  const detail = headerColumns(header)?.detail;
  const tidy = rows.map((row) => row.map((cell, i) => (i === detail ? cell : cell.replace(/\n/g, ' '))));
  return { rows: [header, ...tidy], label: (index) => (index === 0 ? 'Header' : labels[index - 1]) };
}

async function pdfGrids(buffer: Buffer): Promise<Grid[]> {
  const grid = gridFromPdfItems(await pdfTextItems(buffer));
  return grid ? [grid] : [];
}

export async function readVisitRows(
  kind: VisitFileKind,
  ext: string,
  buffer: Buffer,
): Promise<{ rows: ImportedVisitRow[]; rejected: RejectedRow[] }> {
  if (ext === 'xls') throw new BadRequestException('Old .xls files cannot be read. In Excel choose File > Save As > Excel Workbook (.xlsx) and upload that.');
  if (ext === 'doc') throw new BadRequestException('Old .doc files cannot be read. In Word choose File > Save As > Word Document (.docx) and upload that.');
  let grids: Grid[];
  try {
    grids = kind === 'excel' ? await excelGrids(buffer) : kind === 'word' ? await wordGrids(buffer) : await pdfGrids(buffer);
  } catch (err) {
    if (err instanceof BadRequestException) throw err;
    throw new BadRequestException(`The file could not be read (${err instanceof Error ? err.message.slice(0, 120) : 'unknown error'}).`);
  }
  const result = rowsFromGrids(grids);
  if (!result.headerFound) {
    throw new BadRequestException(
      kind === 'word' && !grids.length
        ? 'No table was found in the Word file. Put the visits in a table like the Word template.'
        : 'The header row was not found. The table needs columns like Date, Place, Purpose / Title and Details. Download the template to see the exact layout.',
    );
  }
  return { rows: result.rows, rejected: result.rejected };
}
