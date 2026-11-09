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

const HEADINGS = ["summary", "about", "profile", "objective", "skills", "technologies", "technical skills", "experience", "work experience", "education", "projects", "contact", "looking for", "interests", "goals"];

/** The lines under a heading, up to the next heading. Also handles "Skills: a, b" on one line. */
function sectionText(text: string, names: string[]): string {
  const inline = new RegExp(`^\\s*(?:${names.join("|")})\\s*[:\u2014-]\\s*(.+)$`, "im");
  const inlineMatch = text.match(inline);
  if (inlineMatch) return inlineMatch[1].trim();
  const head = new RegExp(`^\\s*(?:${names.join("|")})\\s*$`, "im");
  const headMatch = text.match(head);
  if (!headMatch || headMatch.index === undefined) return "";
  const rest = text.slice(headMatch.index + headMatch[0].length);
  const lines = rest.split(/\r?\n/);
  const out: string[] = [];
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed && HEADINGS.some((h) => new RegExp(`^${h}\\b`, "i").test(trimmed))) break;
    out.push(line);
  }
  return out.join("\n").trim();
}

export function parseResumeText(raw: string): ResumeData {
  const lines = raw.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);

  let name = "";
  for (const line of lines.slice(0, 6)) {
    if (/resume|cv|curriculum|linkedin|github\.com|@|https?:|www\.|\d{3}[-. ]\d{3}/i.test(line)) continue;
    const words = line.split(/\s+/);
    if (words.length >= 2 && words.length <= 4 && !/^(?:software|senior|junior|cloud|technical|professional|work|education|computer|data)\b/i.test(line) && /^[\p{L}][\p{L}'’.-]+(?:\s+[\p{L}][\p{L}'’.-]+)+$/u.test(line)) {
      name = line;
      break;
    }
  }

  let working_on = "";
  const summary = sectionText(raw, ["summary", "about", "profile", "objective"]);
  if (summary) {
    working_on = summary.replace(/\s+/g, " ").split(/(?<=[.!?])\s+/).slice(0, 2).join(" ").slice(0, 500);
  }

  let tags: string[] = [];
  const skills = sectionText(raw, ["skills", "technologies", "technical skills"]);
  if (skills) {
    tags = skills.split(/[,•\n;|]/).map((s) => s.trim().replace(/^[-–]\s*/, ""))
      .filter((s) => s.length > 1 && s.length < 30 && !/^(and|with|including|etc)$/i.test(s))
      .slice(0, 10);
  }

  // Also find common technical skills when a resume has no dedicated skills section.
  const commonSkills = ["Kubernetes", "Docker", "Python", "TypeScript", "JavaScript", "Java", "Rust", "AWS", "Azure", "Terraform", "OpenTelemetry", "Elasticsearch", "React", "SQL", "Git", "Linux"];
  const known = commonSkills.filter((skill) => new RegExp(`(?<![\\w])${skill}(?![\\w])`, "i").test(raw));
  tags = [...new Map([...tags, ...known].map((tag) => [tag.toLowerCase(), tag])).values()].slice(0, 10);

  const groups: string[] = [];
  const edu = sectionText(raw, ["education"]);
  if (edu) {
    const first = edu.split("\n").map((s) => s.trim()).filter(Boolean)[0];
    if (first && first.length > 2 && first.length < 60) groups.push(first.replace(/,.*$/, ""));
  }

  const asks = sectionText(raw, ["looking for", "interests", "goals"]).replace(/\s+/g, " ").slice(0, 500);
  const offerText = tags.length ? `I can help with ${tags.join(", ")}.` : "";
  if (!working_on && tags.length) working_on = `Working with ${tags.join(", ")}.`;
  return { name, working_on, offers: offerText, asks, tags, groups };
}

