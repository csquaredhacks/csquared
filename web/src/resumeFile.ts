/** Turns a resume file into plain text, on this device. Nothing here talks to a server. */

/** A problem we can explain to the person in plain words. */
export class ResumeFileError extends Error {}

const MAX_BYTES = 10 * 1024 * 1024;

export interface PdfTextItem { str: string; x: number; y: number; width: number; height: number }

/** PDF text arrives in drawing order, which is often not reading order (right-aligned dates
    come first, the name comes third). Rebuild the lines from where each piece sits on the page.
    A wide gap on one line becomes a tab, so "Acme Cloud        May 2026" stays two things. */
export function layoutPdfText(items: PdfTextItem[]): string {
  const rows: PdfTextItem[][] = [];
  const sorted = items.filter((item) => item.str.trim()).sort((a, b) => b.y - a.y || a.x - b.x);
  for (const item of sorted) {
    const row = rows[rows.length - 1];
    if (row && Math.abs(row[0].y - item.y) <= Math.max(2, item.height * 0.5)) row.push(item);
    else rows.push([item]);
  }
  return rows.map((row) => {
    row.sort((a, b) => a.x - b.x);
    let line = "";
    let end = 0;
    row.forEach((item, index) => {
      if (index > 0) {
        const gap = item.x - end;
        const size = item.height || 10;
        if (gap > size * 2.5) line += "\t";
        else if (gap > size * 0.15 && !line.endsWith(" ") && !item.str.startsWith(" ")) line += " ";
      }
      line += item.str;
      end = item.x + item.width;
    });
    return line.trim();
  }).join("\n");
}

/** Loaded on demand so the main bundle stays small. */
async function extractPdfText(data: Uint8Array): Promise<string> {
  const pdfjs = await import("pdfjs-dist");
  const worker = (await import("pdfjs-dist/build/pdf.worker.min.mjs?url")).default;
  pdfjs.GlobalWorkerOptions.workerSrc = worker;
  const pdf = await pdfjs.getDocument({ data }).promise;
  const pages: string[] = [];
  for (let i = 1; i <= pdf.numPages; i++) {
    const content = await (await pdf.getPage(i)).getTextContent();
    const items: PdfTextItem[] = [];
    for (const item of content.items) {
      if ("str" in item) items.push({ str: item.str, x: item.transform[4], y: item.transform[5], width: item.width, height: item.height });
    }
    pages.push(layoutPdfText(items));
  }
  return pages.join("\n");
}

async function inflateRaw(data: Uint8Array): Promise<Uint8Array> {
  const stream = new Blob([data as BlobPart]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

/** One file out of a zip archive, or null when it is not there. A .docx is a zip. */
export async function unzipEntry(zip: Uint8Array, wanted: string): Promise<Uint8Array | null> {
  const view = new DataView(zip.buffer, zip.byteOffset, zip.byteLength);
  let end = -1;
  for (let i = zip.length - 22; i >= Math.max(0, zip.length - 65557); i--) {
    if (view.getUint32(i, true) === 0x06054b50) { end = i; break; }
  }
  if (end < 0) return null;
  const count = view.getUint16(end + 10, true);
  let offset = view.getUint32(end + 16, true);
  for (let n = 0; n < count; n++) {
    if (view.getUint32(offset, true) !== 0x02014b50) return null;
    const method = view.getUint16(offset + 10, true);
    const size = view.getUint32(offset + 20, true);
    const nameLength = view.getUint16(offset + 28, true);
    const name = new TextDecoder().decode(zip.subarray(offset + 46, offset + 46 + nameLength));
    if (name === wanted) {
      const local = view.getUint32(offset + 42, true);
      const start = local + 30 + view.getUint16(local + 26, true) + view.getUint16(local + 28, true);
      const body = zip.subarray(start, start + size);
      if (method === 0) return body;
      return method === 8 ? inflateRaw(body) : null;
    }
    offset += 46 + nameLength + view.getUint16(offset + 30, true) + view.getUint16(offset + 32, true);
  }
  return null;
}

const ENTITIES: Record<string, string> = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'" };

/** The text of a Word document body: one line per paragraph, tabs kept. */
export function docxXmlToText(xml: string): string {
  let out = "";
  for (const match of xml.matchAll(/<w:t\b[^>]*>([^<]*)<\/w:t>|<w:tab\b[^>]*\/>|<w:(?:br|cr)\b[^>]*\/>|<\/w:p>/g)) {
    if (match[1] !== undefined) out += match[1];
    else if (match[0].startsWith("<w:tab")) out += "\t";
    else out += "\n";
  }
  return out.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (whole, code: string) => {
    if (code[0] !== "#") return ENTITIES[code.toLowerCase()] ?? whole;
    const point = code[1].toLowerCase() === "x" ? parseInt(code.slice(2), 16) : parseInt(code.slice(1), 10);
    return Number.isFinite(point) && point <= 0x10ffff ? String.fromCodePoint(point) : whole;
  });
}

/** The text of a PDF, Word (.docx), plain text or Markdown resume. */
export async function readResumeFile(file: File): Promise<string> {
  if (file.size > MAX_BYTES) throw new ResumeFileError("That file is over 10 MB. Try a smaller PDF, or paste the text below.");
  const bytes = new Uint8Array(await file.arrayBuffer());
  const magic = String.fromCharCode(...bytes.subarray(0, 4));
  const name = file.name.toLowerCase();

  if (magic === "%PDF" || name.endsWith(".pdf")) {
    const text = await extractPdfText(bytes);
    if (text.replace(/\s/g, "").length < 20) {
      throw new ResumeFileError("That PDF has no text we can read. It may be a scan. Paste the text below instead.");
    }
    return text;
  }
  if (magic.startsWith("PK")) {
    const xml = await unzipEntry(bytes, "word/document.xml");
    if (!xml) throw new ResumeFileError("That file is not a Word document we can read. Try a PDF, or paste the text below.");
    return docxXmlToText(new TextDecoder().decode(xml));
  }
  if (magic === "\xd0\xcf\x11\xe0" || name.endsWith(".doc")) {
    throw new ResumeFileError("Older .doc files cannot be read here. Save it as PDF or .docx, or paste the text below.");
  }
  return new TextDecoder().decode(bytes);
}
