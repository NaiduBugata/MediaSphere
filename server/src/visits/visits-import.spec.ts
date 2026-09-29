import { execFileSync } from 'node:child_process';
import path from 'node:path';
import ExcelJS from 'exceljs';
import JSZip from 'jszip';
import { gridFromPdfItems, headerColumns, parseVisitDate, readVisitRows, rowsFromGrids } from './visits-import';
import { excelTemplate, wordTemplate } from './visits-template';

async function excelFile(rows: unknown[][], sheetName = 'Visits'): Promise<Buffer> {
  const workbook = new ExcelJS.Workbook();
  const sheet = workbook.addWorksheet(sheetName);
  rows.forEach((row) => sheet.addRow(row));
  return Buffer.from(await workbook.xlsx.writeBuffer());
}

async function wordFile(tables: string[][][], before = 'Visits list'): Promise<Buffer> {
  const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const cell = (text: string) =>
    `<w:tc><w:p>${text
      .split('\n')
      .map((line, i) => `${i ? '<w:br/>' : ''}<w:r><w:t xml:space="preserve">${esc(line)}</w:t></w:r>`)
      .join('')}</w:p></w:tc>`;
  const body = tables
    .map((rows) => `<w:tbl>${rows.map((cells) => `<w:tr>${cells.map(cell).join('')}</w:tr>`).join('')}</w:tbl>`)
    .join('<w:p/>');
  const zip = new JSZip();
  zip.file(
    'word/document.xml',
    `<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>${before}</w:t></w:r></w:p>${body}</w:body></w:document>`,
  );
  return zip.generateAsync({ type: 'nodebuffer' });
}

/** Tiny PDF writer: each row is drawn at fixed column positions, optionally with ruled cell borders. */
function pdfFile(rows: string[][], ruled: boolean): Buffer {
  const xs = [40, 90, 190, 300, 520, 800];
  const top = 540;
  const height = 24;
  const esc = (s: string) => s.replace(/\\/g, '\\\\').replace(/\(/g, '\\(').replace(/\)/g, '\\)');
  let content = '';
  rows.forEach((cells, r) => {
    const y = top - r * height;
    cells.forEach((text, c) => {
      if (text) content += `BT /F1 9 Tf ${xs[c] + 4} ${y - 16} Td (${esc(text)}) Tj ET\n`;
    });
  });
  if (ruled) {
    content += '0.5 w\n';
    for (let r = 0; r <= rows.length; r++) content += `${xs[0]} ${top - r * height} m ${xs[xs.length - 1]} ${top - r * height} l S\n`;
    for (const x of xs) content += `${x} ${top} m ${x} ${top - rows.length * height} l S\n`;
  }
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
    `<< /Length ${Buffer.byteLength(content, 'latin1')} >>\nstream\n${content}endstream`,
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
  ];
  let out = '%PDF-1.4\n';
  const offsets: number[] = [];
  objects.forEach((body, i) => {
    offsets.push(Buffer.byteLength(out, 'latin1'));
    out += `${i + 1} 0 obj\n${body}\nendobj\n`;
  });
  const xref = Buffer.byteLength(out, 'latin1');
  out += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n${offsets.map((o) => `${String(o).padStart(10, '0')} 00000 n \n`).join('')}`;
  out += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(out, 'latin1');
}

/**
 * pdf.js is ESM-only and Jest's CommonJS sandbox cannot import it, so real PDFs are read by
 * the same module in a plain Node child process.
 */
function readPdfInNode(pdf: Buffer): { rows?: Array<Record<string, string>>; rejected?: unknown[]; error?: string } {
  const script = `
    const { readVisitRows } = require(${JSON.stringify(path.join(__dirname, 'visits-import'))});
    readVisitRows('pdf', 'pdf', Buffer.from(process.env.VISITS_PDF_B64, 'base64')).then(
      (result) => process.stdout.write(JSON.stringify(result)),
      (err) => process.stdout.write(JSON.stringify({ error: err.message })),
    );`;
  const out = execFileSync(process.execPath, ['-r', 'ts-node/register/transpile-only', '-e', script], {
    encoding: 'utf8',
    env: {
      ...process.env,
      VISITS_PDF_B64: pdf.toString('base64'),
      TS_NODE_PROJECT: path.join(__dirname, '..', '..', 'tsconfig.spec.json'),
    },
  });
  return JSON.parse(out);
}

const HEADER = ['S.No', 'Date', 'Place', 'Purpose', 'Details'];
const PDF_ROWS = [
  HEADER,
  ['1', '12-09-2026', 'Macherla', 'Road inspection', 'Checked the bypass works'],
  ['2', '15/09/2026', 'Gurazala', 'Farmers meeting', 'Heard crop loss complaints'],
];

describe('parseVisitDate', () => {
  it('reads Indian day-first dates, ISO dates, month names, and Excel serial numbers', () => {
    expect(parseVisitDate('28-09-2026')).toBe('2026-09-28');
    expect(parseVisitDate('5/10/2026')).toBe('2026-10-05');
    expect(parseVisitDate('05.10.26')).toBe('2026-10-05');
    expect(parseVisitDate('2026-09-28')).toBe('2026-09-28');
    expect(parseVisitDate('28 Sep 2026')).toBe('2026-09-28');
    expect(parseVisitDate('28th September, 2026')).toBe('2026-09-28');
    expect(parseVisitDate('Sept 28, 2026')).toBe('2026-09-28');
    expect(parseVisitDate('46293')).toBe('2026-09-28');
    expect(parseVisitDate('  ')).toBe('');
  });

  it('refuses text and impossible dates', () => {
    expect(parseVisitDate('next week')).toBeNull();
    expect(parseVisitDate('31-02-2026')).toBeNull();
    expect(parseVisitDate('12-13-2026')).toBeNull();
  });
});

describe('headerColumns', () => {
  it('matches English and Telugu headers and ignores the serial column', () => {
    expect(headerColumns(['S.No', 'Date (DD-MM-YYYY)', 'Place', 'Purpose / Title', 'Details'])).toEqual({
      date: 1,
      place: 2,
      title: 3,
      detail: 4,
    });
    expect(headerColumns(['క్రమ సంఖ్య', 'తేదీ', 'గ్రామం', 'కార్యక్రమం', 'వివరాలు'])).toEqual({ date: 1, place: 2, title: 3, detail: 4 });
    expect(headerColumns(['Visit date', 'Place of visit', 'Visit details'])).toEqual({ date: 0, place: 1, detail: 2 });
  });

  it('does not treat a data row as a header', () => {
    expect(headerColumns(['1', '28-09-2026', 'Vinukonda', 'Hospital visit', 'Met staff'])).toBeNull();
    expect(headerColumns(['Date', 'Remarks'])).toBeNull();
  });
});

describe('readVisitRows', () => {
  it('reads an Excel sheet: real date cells, typed dates, place-only rows, and bad dates', async () => {
    const buffer = await excelFile([
      ['Monthly visits'],
      ['S.No', 'Date', 'Place', 'Purpose / Title', 'Details'],
      [1, new Date(Date.UTC(2026, 8, 28)), 'Vinukonda', 'Hospital visit', 'Met the staff'],
      [2, '02-10-2026', 'Macherla', '', 'Gandhi Jayanti programme'],
      [3, 'someday', 'Gurazala', 'Farmers meet', ''],
      [4, '', '', '', ''],
      [5, '', 'Chilakaluripet', 'Temple festival', ''],
    ]);
    const { rows, rejected } = await readVisitRows('excel', 'xlsx', buffer);
    expect(rows).toEqual([
      { where: 'Row 3', title: 'Hospital visit', place: 'Vinukonda', visitDate: '2026-09-28', detail: 'Met the staff' },
      { where: 'Row 4', title: 'Visit to Macherla', place: 'Macherla', visitDate: '2026-10-02', detail: 'Gandhi Jayanti programme' },
      { where: 'Row 7', title: 'Temple festival', place: 'Chilakaluripet', visitDate: '', detail: '' },
    ]);
    expect(rejected).toEqual([{ where: 'Row 5', reason: 'Date "someday" is not a date like 28-09-2026.' }]);
  });

  it('reads the downloaded templates without importing the example row', async () => {
    await expect(readVisitRows('excel', 'xlsx', await excelTemplate())).resolves.toEqual({ rows: [], rejected: [] });
    await expect(readVisitRows('word', 'docx', await wordTemplate())).resolves.toEqual({ rows: [], rejected: [] });
  });

  it('reads a filled Excel template', async () => {
    const workbook = new ExcelJS.Workbook();
    await workbook.xlsx.load((await excelTemplate()) as unknown as ArrayBuffer);
    const sheet = workbook.getWorksheet('Visits')!;
    sheet.spliceRows(2, 1);
    sheet.addRow([1, new Date(Date.UTC(2026, 8, 20)), 'Pedakurapadu', 'School visit', 'Mid-day meal check']);
    const buffer = Buffer.from(await workbook.xlsx.writeBuffer());
    const { rows } = await readVisitRows('excel', 'xlsx', buffer);
    expect(rows).toEqual([
      { where: 'Row 2', title: 'School visit', place: 'Pedakurapadu', visitDate: '2026-09-20', detail: 'Mid-day meal check' },
    ]);
  });

  it('reads Word tables, keeps line breaks in details, and uses Telugu headers', async () => {
    const buffer = await wordFile([
      [
        ['క్రమ సంఖ్య', 'తేదీ', 'గ్రామం', 'కార్యక్రమం', 'వివరాలు'],
        ['1', '28-09-2026', 'నరసరావుపేట', 'ఆసుపత్రి సందర్శన', 'కొత్త వార్డు\nసిబ్బందితో సమావేశం'],
        ['2', '', '', '', ''],
      ],
    ]);
    const { rows } = await readVisitRows('word', 'docx', buffer);
    expect(rows).toEqual([
      {
        where: 'Row 2',
        title: 'ఆసుపత్రి సందర్శన',
        place: 'నరసరావుపేట',
        visitDate: '2026-09-28',
        detail: 'కొత్త వార్డు\nసిబ్బందితో సమావేశం',
      },
    ]);
  });

  it('reads real PDF files with pdf.js, with and without table borders', () => {
    const expected = [
      { where: 'Page 1, row 1', title: 'Road inspection', place: 'Macherla', visitDate: '2026-09-12', detail: 'Checked the bypass works' },
      { where: 'Page 1, row 2', title: 'Farmers meeting', place: 'Gurazala', visitDate: '2026-09-15', detail: 'Heard crop loss complaints' },
    ];
    expect(readPdfInNode(pdfFile(PDF_ROWS, true))).toEqual({ rows: expected, rejected: [] });
    expect(readPdfInNode(pdfFile(PDF_ROWS, false))).toEqual({ rows: expected, rejected: [] });
    expect(readPdfInNode(Buffer.from('%PDF-1.4 broken')).error).toMatch(/^The file could not be read/);
  }, 60000);

  it('joins wrapped PDF cell text into its row and repeats the header on the next page', () => {
    const at = (page: number, y: number, x: number, text: string) => ({ page, y, x, text, width: text.length * 4.5 });
    const items = [
      at(1, 800, 40, 'Visits'),
      ...['S.No', 'Date', 'Place', 'Purpose / Title', 'Details'].map((text, i) => at(1, 760, [40, 90, 190, 300, 520][i], text)),
      at(1, 740, 40, '1'),
      at(1, 740, 90, '12-09-2026'),
      at(1, 740, 190, 'Macherla'),
      at(1, 740, 300, 'Road inspection'),
      at(1, 740, 520, 'Checked the bypass'),
      at(1, 729, 520, 'and the drains'),
      at(1, 200, 520, 'Page 1 of 2'),
      ...['S.No', 'Date', 'Place', 'Purpose / Title', 'Details'].map((text, i) => at(2, 760, [40, 90, 190, 300, 520][i], text)),
      at(2, 740, 40, '2'),
      at(2, 740, 90, '15-09-2026'),
      at(2, 740, 190, 'Gurazala'),
      at(2, 740, 300, 'Farmers'),
      at(2, 729, 300, 'meeting'),
    ];
    const grid = gridFromPdfItems(items)!;
    const { rows } = rowsFromGrids([grid]);
    expect(rows).toEqual([
      { where: 'Page 1, row 1', title: 'Road inspection', place: 'Macherla', visitDate: '2026-09-12', detail: 'Checked the bypass\nand the drains' },
      { where: 'Page 2, row 1', title: 'Farmers meeting', place: 'Gurazala', visitDate: '2026-09-15', detail: '' },
    ]);
  });

  it('explains what is wrong with files it cannot use', async () => {
    await expect(readVisitRows('excel', 'xls', Buffer.alloc(8))).rejects.toThrow('Save As > Excel Workbook');
    await expect(readVisitRows('word', 'doc', Buffer.alloc(8))).rejects.toThrow('Save As > Word Document');
    await expect(readVisitRows('word', 'docx', await wordFile([]))).rejects.toThrow('No table was found');
    await expect(readVisitRows('excel', 'xlsx', await excelFile([['Name', 'Phone'], ['A', '1']]))).rejects.toThrow(
      'header row was not found',
    );
  });
});
