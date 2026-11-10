/** What a resume gives us, and nothing else. The parser is deliberately
    conservative: it only fills a field when it finds something that looks
    like that field, and the person can fix anything before submitting. */
export interface ResumeData {
  name: string;
  working_on: string;
  offers: string;
  asks: string;
  tags: string[];
  groups: string[];
}

type SectionKey = "summary" | "skills" | "experience" | "education" | "projects" | "asks" | "interests" | "other";

/** Every heading we recognise, by the part of the form it feeds. "other" only ends the section before it. */
const SECTION_NAMES: Record<SectionKey, string[]> = {
  summary: ["summary", "professional summary", "career summary", "executive summary", "summary of qualifications",
    "about", "about me", "profile", "professional profile", "objective", "career objective"],
  skills: ["skills", "technical skills", "technologies", "core skills", "key skills", "core competencies",
    "skills and technologies", "skills and tools", "tools", "tech stack", "programming languages",
    "languages and technologies", "technical proficiencies"],
  experience: ["experience", "work experience", "professional experience", "relevant experience", "industry experience",
    "employment", "employment history", "work history", "internships", "internship experience", "research experience"],
  education: ["education", "academic background", "education and training"],
  projects: ["projects", "personal projects", "selected projects", "academic projects", "technical projects", "side projects"],
  asks: ["looking for", "goals", "career goals"],
  interests: ["interests", "areas of interest"],
  other: ["contact", "contact information", "certifications", "certificates", "licenses", "awards", "honors",
    "honors and awards", "awards and honors", "achievements", "publications", "leadership", "leadership experience",
    "activities", "extracurricular activities", "volunteer", "volunteering", "volunteer experience", "coursework",
    "relevant coursework", "languages", "hobbies", "references", "additional information"],
};

const HEADING_KEYS = new Map<string, SectionKey>(
  (Object.entries(SECTION_NAMES) as [SectionKey, string[]][]).flatMap(([key, names]) => names.map((name) => [name, key] as [string, SectionKey])),
);

/** Headings that may carry their content on the same line: "Skills: a, b". */
const INLINE_KEYS = new Set<SectionKey>(["summary", "skills", "education", "asks", "interests"]);

function normaliseHeading(text: string): string {
  let out = text.trim().replace(/\s*:$/, "");
  // "E D U C A T I O N" is a common letter-spaced heading.
  if (/^(?:\p{L}\s){3,}\p{L}$/u.test(out)) out = out.replace(/\s/g, "");
  return out.replace(/\s*&\s*/g, " and ").replace(/\s+/g, " ").toLowerCase();
}

/** Is this line a section heading? `rest` is what follows it on the same line. */
function headingOf(line: string): { key: SectionKey; rest: string } | null {
  const bare = HEADING_KEYS.get(normaliseHeading(line));
  if (bare) return { key: bare, rest: "" };
  const inline = line.match(/^\s*([\p{L}&][\p{L}& ]{2,40}?)\s*(?::|\s[—–-]\s)\s*(\S.*)$/u);
  if (inline) {
    const key = HEADING_KEYS.get(normaliseHeading(inline[1]));
    if (key && INLINE_KEYS.has(key)) return { key, rest: inline[2].trim() };
  }
  return null;
}

/** The lines of a resume, grouped by the section they sit under. "head" is everything above the first heading. */
function splitSections(raw: string): Record<SectionKey | "head", string[]> {
  const sections: Record<SectionKey | "head", string[]> = { head: [], summary: [], skills: [], experience: [], education: [], projects: [], asks: [], interests: [], other: [] };
  let current: SectionKey | "head" = "head";
  for (const line of raw.split(/\r?\n/)) {
    if (!line.trim()) continue;
    const heading = headingOf(line);
    if (heading) {
      current = heading.key;
      if (heading.rest) sections[current].push(heading.rest);
    } else {
      sections[current].push(line.trim());
    }
  }
  return sections;
}

const MONTH = "(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|spring|summer|fall|autumn|winter)\\.?";
const DATE = `(?:${MONTH}\\s+)?(?:19|20)\\d{2}|\\d{1,2}/(?:19|20)?\\d{2}`;
const DATES = new RegExp(`(?:\\b(?:expected|anticipated|graduating|graduation|class of)[:\\s]+)?\\b(?:${DATE})\\b(?:\\s*(?:[-–—]|to)\\s*(?:${DATE}|present|current|now|ongoing)\\b)?`, "gi");
const US_STATES = "AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY";
const PLACE = new RegExp(`(?:^|[,|\\t(–—-])\\s*[A-Z][\\p{L}.' ]{1,30},\\s*(?:${US_STATES})\\b\\)?`, "gu");
const BULLET = /^\s*(?:[-–—*•●▪◦‣·➢∙]|o(?=\s))\s*/;

/** A line without its dates, places and the separators they leave behind. Empty when nothing else was on it. */
function tidyLine(line: string): string {
  return line.replace(DATES, "").replace(PLACE, "").replace(/\(\s*\)/g, "")
    .replace(/\s*\t\s*/g, ", ").replace(/\s+/g, " ")
    .replace(/^[\s,|–—-]+|[\s,|–—-]+$/g, "")
    .replace(/(?:\s*,){2,}/g, ",");
}

/** Prose is a bullet or a sentence. Anything else under a heading is a title, employer or project name. */
function isProse(line: string): boolean {
  const words = line.trim().split(/\s+/).length;
  return BULLET.test(line) || words >= 8 || (words >= 3 && /[.!?]$/.test(line.trim()));
}

function sentence(text: string): string {
  const out = text.trim();
  return !out || /[.!?]$/.test(out) ? out : `${out}.`;
}

/** "Role, Employer. First thing they did there." from the first entry of a section. */
function firstEntry(lines: string[]): string {
  const clean = lines.map((line) => (BULLET.test(line) ? line : tidyLine(line))).filter(Boolean);
  const header: string[] = [];
  let i = 0;
  while (i < clean.length && header.length < 2 && !isProse(clean[i])) header.push(clean[i++]);
  while (i < clean.length && !isProse(clean[i])) i++;
  const body: string[] = [];
  for (let j = i; j < Math.min(clean.length, i + 4); j++) {
    if (j > i && BULLET.test(clean[j])) break;
    body.push(clean[j].replace(BULLET, ""));
    if (/[.!?]$/.test(clean[j])) break;
  }
  const first = body.join(" ").replace(/\s+/g, " ").split(/(?<=[.!?])\s+/)[0] ?? "";
  return [header.join(", "), first].filter(Boolean).map(sentence).join(" ").slice(0, 500);
}

const SCHOOL = /\b(?:university|college|institute|school|academy|polytechnic|universit[éà]|universidad|universität)\b/i;
const DEGREE = /\b(?:b\.?\s?s\.?c?|b\.?\s?a|m\.?\s?s\.?c?|m\.?\s?a|ph\.?\s?d|m\.?b\.?a|b\.?\s?eng|m\.?\s?eng|bachelor(?:'s|s)?|master(?:'s|s)?|associate(?:'s|s)?|doctor(?:ate)?|diploma)\b\.?/i;

function schoolOf(education: string[]): string {
  const lines = education.map(tidyLine).filter(Boolean);
  const line = lines.find((l) => SCHOOL.test(l)) ?? lines[0] ?? "";
  const parts = line.split(/\s*(?:[,|]|\s[–—-]\s)\s*/).filter(Boolean);
  const school = (parts.find((p) => SCHOOL.test(p)) ?? parts[0] ?? "").trim();
  return school.length > 2 && school.length < 60 ? school : "";
}

function degreeOf(education: string[]): string {
  for (const line of education.map(tidyLine)) {
    const part = line.split(/\s*[|]\s*|,\s*(?=\S)/).find((p) => DEGREE.test(p) && !/\b(?:gpa|cgpa)\b/i.test(p));
    if (part && part.length < 80) return part.trim();
  }
  return "";
}

function titleCase(text: string): string {
  return text.toLowerCase().replace(/(^|[\s'’-])(\p{L})/gu, (_, before: string, letter: string) => before + letter.toUpperCase());
}

const NOT_A_NAME = /resume|résumé|\bcv\b|curriculum|vitae|linkedin|github|@|https?:|www\.|\d/i;
const NAME = /^[\p{L}][\p{L}'’.-]*(?:\s+[\p{L}][\p{L}'’.-]*){1,3}$/u;
const TITLE_WORDS = /^(?:software|senior|junior|cloud|technical|professional|work|education|computer|data|full|front|back|product|project|student|engineer|developer|designer)\b/i;

const NAME_PARTICLES = /^(?:de|del|della|da|dos|das|di|du|la|le|van|von|der|den|bin|ibn|al|el|y)$/;

function nameOf(lines: string[]): string {
  for (const line of lines.slice(0, 8)) {
    // "Jordan Rivera | jordan@example.com | 801 555 0134" keeps its name in the first part.
    const candidate = line.split(/\s*[|•·\t]\s*|\s{3,}/)[0].trim().replace(/,$/, "");
    if (!candidate || NOT_A_NAME.test(candidate) || TITLE_WORDS.test(candidate) || !NAME.test(candidate)) continue;
    // Names are capitalised ("Ana de la Cruz"); an ordinary lowercase sentence is not one.
    if (!candidate.split(/\s+/).every((word) => /^[\p{Lu}\p{Lo}]/u.test(word) || NAME_PARTICLES.test(word))) continue;
    return candidate === candidate.toUpperCase() ? titleCase(candidate) : candidate;
  }
  return "";
}

/** "Jordan_Rivera_Resume_2026.pdf" -> "Jordan Rivera". Used only when the text gave no name. */
export function nameFromFilename(filename: string): string {
  const words = filename.replace(/\.[a-z0-9]+$/i, "").replace(/\(\d+\)/g, " ").split(/[\s_.+-]+/)
    .filter((word) => word && !/^\d+$/.test(word) && !/^(?:resume|résumé|cv|curriculum|vitae|final|draft|copy|updated|new|latest|v\d+|swe|sde|intern|internship)$/i.test(word));
  const candidate = words.join(" ");
  return words.length >= 2 && words.length <= 4 && NAME.test(candidate) ? titleCase(candidate) : "";
}

const COMMON_SKILLS = ["Kubernetes", "Docker", "Python", "TypeScript", "JavaScript", "Java", "Rust", "C++", "C#", "AWS", "Azure", "GCP",
  "Terraform", "OpenTelemetry", "Elasticsearch", "React", "Node.js", "Next.js", "FastAPI", "Django", "PyTorch", "TensorFlow",
  "PostgreSQL", "MongoDB", "Redis", "Kafka", "GraphQL", "SQL", "Git", "Linux", "Figma"];
const SKILL_NOISE = /^(?:and|with|including|etc|other|others|more|proficient|familiar|advanced|intermediate|beginner|basic)$/i;

function skillsOf(lines: string[]): string[] {
  const found: string[] = [];
  for (const line of lines) {
    const items = line.replace(BULLET, "")
      .replace(/^[^,:;|]{2,40}:\s*/, "")  // "Languages: Python, Go" is a label, not a skill
      .replace(/\([^)]*\)/g, "")
      .split(/[,;|•·●▪\t]|\s\/\s/);
    for (const item of items) {
      const skill = item.trim().replace(/^[-–]\s*/, "").replace(/^and\s+/i, "").replace(/\.$/, "").trim();
      const fits = (skill.length > 1 || /^[CR]$/.test(skill)) && skill.length < 30 && skill.split(/\s+/).length <= 4;
      if (fits && !SKILL_NOISE.test(skill)) found.push(skill);
    }
  }
  return found;
}

function unique(tags: string[]): string[] {
  const seen = new Set<string>();
  return tags.filter((tag) => !seen.has(tag.toLowerCase()) && seen.add(tag.toLowerCase()));
}

export function parseResumeText(raw: string): ResumeData {
  const sections = splitSections(raw);
  const name = nameOf(sections.head);

  // Skills the resume lists, then well-known ones it mentions anywhere else.
  const mentioned = COMMON_SKILLS.filter((skill) =>
    new RegExp(`(?<![\\w+#])${skill.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![\\w+#])`, "i").test(raw));
  // "Interests: AI agents, hiking" is a list of topics, so it becomes tags. A sentence
  // under the same heading ("Find a mentor.") says what they are after, so it is an ask.
  const interests = sections.interests.join("\n");
  const topics = /[,;|\u2022\n]/.test(interests) && !/[.!?]\s*$/.test(interests) ? skillsOf(sections.interests) : [];
  const skills = unique([...skillsOf(sections.skills), ...mentioned]);
  const tags = unique([...skills.slice(0, topics.length ? 7 : 10), ...topics, ...skills]).slice(0, 10);

  const school = schoolOf(sections.education);
  const groups = school ? [school] : [];

  // Their own summary is best. Without one, say what they did most recently.
  let working_on = "";
  const summary = sections.summary.join(" ").replace(/\s+/g, " ").trim();
  if (summary) working_on = summary.split(/(?<=[.!?])\s+/).slice(0, 2).join(" ").slice(0, 500);
  if (!working_on) working_on = firstEntry(sections.experience) || firstEntry(sections.projects);
  if (!working_on) {
    const degree = degreeOf(sections.education);
    if (degree) working_on = sentence(school && !degree.includes(school) ? `${degree} at ${school}` : degree);
  }
  if (!working_on && skills.length) working_on = `Working with ${skills.slice(0, 6).join(", ")}.`;

  const asks = [...sections.asks, ...(topics.length ? [] : sections.interests)].join(" ").replace(/\s+/g, " ").trim().slice(0, 500);
  const offers = skills.length ? `I can help with ${skills.slice(0, 6).join(", ")}.` : "";
  return { name, working_on, offers, asks, tags, groups };
}
