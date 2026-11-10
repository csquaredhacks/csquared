import { test } from "node:test";
import assert from "node:assert/strict";
import { deflateRawSync } from "node:zlib";
import { nameFromFilename, parseResumeText } from "../src/resume.ts";
import { docxXmlToText, layoutPdfText, readResumeFile, ResumeFileError } from "../src/resumeFile.ts";

test("extracts skills, education and stated goals from a resume", () => {
  const result = parseResumeText("Amira Flores\nSUMMARY\nCloud developer and student.\nSKILLS\nPython, Kubernetes, Docker\nEDUCATION\nUniversity of Utah\nGOALS: Find a mentor");
  assert.equal(result.name, "Amira Flores");
  assert.ok(result.tags.some((tag) => tag.toLowerCase() === "python"));
  assert.match(result.offers, /Python/i);
  assert.match(result.asks, /mentor/i);
  assert.equal(result.groups[0], "University of Utah");
});

test("finds skills in experience without inventing an ask", () => {
  const result = parseResumeText("María García\nEXPERIENCE\nBuilt Docker systems using Python.");
  assert.equal(result.name, "María García");
  assert.ok(result.tags.includes("Docker"));
  assert.equal(result.asks, "");
  assert.ok(!parseResumeText("We go to conferences").tags.includes("Go"));
});

test("goal headings stop earlier sections", () => {
  for (const heading of ["LOOKING FOR", "INTERESTS", "GOALS"]) {
    const summary = parseResumeText(`Amira Flores\nSUMMARY\nBuilding useful tools.\n${heading}\nFind a mentor.`);
    assert.equal(summary.working_on, "Building useful tools.");
    assert.equal(summary.asks, "Find a mentor.");

    const skills = parseResumeText(`Amira Flores\nSKILLS\nPython, Rust\n${heading}\nFind a mentor.`);
    assert.deepEqual(skills.tags, ["Python", "Rust"]);
    assert.equal(skills.asks, "Find a mentor.");
  }

  const skills = parseResumeText("SKILLS\nPython\nLooking for\nan internship\nExperience\nBuilt apps");
  assert.deepEqual(skills.tags, ["Python"]);
  assert.equal(skills.asks, "an internship");
  assert.doesNotMatch(skills.offers, /internship|looking for/i);

  const summary = parseResumeText("SUMMARY\nCloud developer.\nGOALS\nFind a mentor");
  assert.equal(summary.working_on, "Cloud developer.");
  assert.equal(summary.asks, "Find a mentor");
});

test("reads a typical one-page resume: capitals name, grouped skills, dated entries", () => {
  const result = parseResumeText([
    "JORDAN M. RIVERA",
    "Salt Lake City, UT | (801) 555-0134 | jordan.rivera@example.com | linkedin.com/in/jordanrivera",
    "EDUCATION",
    "University of Utah, Salt Lake City, UT\tExpected May 2027",
    "B.S. in Computer Science, GPA 3.8",
    "TECHNICAL SKILLS",
    "Languages: Python, TypeScript, Go, C++, SQL",
    "Frameworks: React, FastAPI (async), Node.js",
    "EXPERIENCE",
    "Software Engineering Intern, Acme Cloud\tMay 2026 \u2013 Aug 2026",
    "Built a real-time observability pipeline with OpenTelemetry that cut alert latency",
    "by 40%.",
    "Shipped a React dashboard used by 200 engineers.",
  ].join("\n"));
  assert.equal(result.name, "Jordan M. Rivera");
  assert.deepEqual(result.tags.slice(0, 8), ["Python", "TypeScript", "Go", "C++", "SQL", "React", "FastAPI", "Node.js"]);
  assert.ok(result.tags.every((tag) => !tag.includes(":")), "category labels are not skills");
  assert.equal(result.working_on, "Software Engineering Intern, Acme Cloud. Built a real-time observability pipeline with OpenTelemetry that cut alert latency by 40%.");
  assert.equal(result.offers, "I can help with Python, TypeScript, Go, C++, SQL, React.");
  assert.deepEqual(result.groups, ["University of Utah"]);
  assert.equal(result.asks, "");
});

test("a summary wins over experience, and prose that mentions a heading word stays in its section", () => {
  const result = parseResumeText("Priya Natarajan | priya@example.com\nPROFESSIONAL SUMMARY\nPlatform engineer building tools.\nExperience with Kubernetes at scale.\nWORK EXPERIENCE\nStripe\n\u2022 Led a migration\nEDUCATION\nB.S. Computer Science, University of Washington\t2014 \u2013 2018");
  assert.equal(result.name, "Priya Natarajan");
  assert.equal(result.working_on, "Platform engineer building tools. Experience with Kubernetes at scale.");
  assert.deepEqual(result.groups, ["University of Washington"]);
});

test("falls back to a project, then a degree, for what someone is working on", () => {
  const project = parseResumeText("Alex Chen\nProjects\nStudyBuddy\n- Mobile app that matches students for study sessions\n- 500 weekly users");
  assert.equal(project.working_on, "StudyBuddy. Mobile app that matches students for study sessions.");
  const degree = parseResumeText("Alex Chen\nEducation\nMaster of Science in Data Science\nMassachusetts Institute of Technology, Cambridge, MA\nExpected June 2027");
  assert.equal(degree.working_on, "Master of Science in Data Science at Massachusetts Institute of Technology.");
  assert.deepEqual(degree.groups, ["Massachusetts Institute of Technology"]);
});

test("a list of interests becomes tags, never a need", () => {
  const result = parseResumeText("Alex Chen\nSkills\nPython, SQL\nInterests: AI agents, hiking");
  assert.deepEqual(result.tags, ["Python", "SQL", "AI agents", "hiking"]);
  assert.equal(result.asks, "");
  assert.equal(result.offers, "I can help with Python, SQL.");
});

test("does not mistake a sentence or a job title for a name", () => {
  assert.equal(parseResumeText("nothing useful here").name, "");
  assert.equal(parseResumeText("Software Developer\nSkills: Python").name, "");
  assert.equal(parseResumeText("Resume\nAna de la Cruz\nSkills: Python").name, "Ana de la Cruz");
});

test("takes a name from the file name when the text has none", () => {
  assert.equal(nameFromFilename("Jordan_Rivera_Resume_2026 (1).pdf"), "Jordan Rivera");
  assert.equal(nameFromFilename("priya-natarajan-cv.docx"), "Priya Natarajan");
  assert.equal(nameFromFilename("resume.pdf"), "");
  assert.equal(nameFromFilename("CV-final-v2.docx"), "");
});

test("PDF text is put back in reading order, with wide gaps kept apart", () => {
  // Drawing order: the right-aligned date first, then the name, as real PDFs often do.
  const text = layoutPdfText([
    { str: "Expected May 2027", x: 476, y: 633, width: 100, height: 12 },
    { str: "JORDAN RIVERA", x: 190, y: 740, width: 200, height: 24 },
    { str: "University of Utah", x: 30, y: 633, width: 103, height: 12 },
    { str: ", Salt Lake City, UT", x: 133, y: 633, width: 110, height: 12 },
    { str: "Languages:", x: 30, y: 554, width: 67, height: 12 },
    { str: " ", x: 97, y: 554, width: 4, height: 12 },
    { str: "Python, Go", x: 101, y: 554, width: 60, height: 12 },
  ]);
  assert.equal(text, "JORDAN RIVERA\nUniversity of Utah, Salt Lake City, UT\tExpected May 2027\nLanguages: Python, Go");
});

/** A minimal zip archive with one or more files, as Word writes a .docx. */
function zip(files) {
  const locals = [];
  const central = [];
  let offset = 0;
  for (const [name, text] of Object.entries(files)) {
    const body = deflateRawSync(Buffer.from(text));
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0); local.writeUInt16LE(8, 8);
    local.writeUInt32LE(body.length, 18); local.writeUInt32LE(Buffer.byteLength(text), 22); local.writeUInt16LE(name.length, 26);
    const entry = Buffer.alloc(46);
    entry.writeUInt32LE(0x02014b50, 0); entry.writeUInt16LE(8, 10);
    entry.writeUInt32LE(body.length, 20); entry.writeUInt32LE(Buffer.byteLength(text), 24); entry.writeUInt16LE(name.length, 28);
    entry.writeUInt32LE(offset, 42);
    locals.push(local, Buffer.from(name), body);
    central.push(entry, Buffer.from(name));
    offset += 30 + name.length + body.length;
  }
  const directory = Buffer.concat(central);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0); end.writeUInt16LE(central.length / 2, 8); end.writeUInt16LE(central.length / 2, 10);
  end.writeUInt32LE(directory.length, 12); end.writeUInt32LE(offset, 16);
  return Buffer.concat([...locals, directory, end]);
}

test("reads a Word .docx resume", async () => {
  const xml = '<w:document><w:body>'
    + '<w:p><w:r><w:t>Priya Natarajan</w:t></w:r></w:p>'
    + '<w:p><w:r><w:t>SUMMARY</w:t></w:r></w:p>'
    + '<w:p><w:r><w:t xml:space="preserve">Builds tools for R&amp;D </w:t></w:r><w:r><w:t>teams.</w:t></w:r></w:p>'
    + '<w:p><w:r><w:t>EDUCATION</w:t></w:r></w:p>'
    + '<w:p><w:r><w:t>University of Washington</w:t></w:r><w:r><w:tab/></w:r><w:r><w:t>2018</w:t></w:r></w:p>'
    + '<w:p><w:r><w:t>SKILLS</w:t></w:r></w:p><w:p><w:r><w:t>Go, Rust</w:t></w:r></w:p>'
    + '</w:body></w:document>';
  assert.equal(docxXmlToText(xml).split("\n")[4], "University of Washington\t2018");

  const file = new File([zip({ "[Content_Types].xml": "<Types/>", "word/document.xml": xml })], "cv.docx");
  const result = parseResumeText(await readResumeFile(file));
  assert.equal(result.name, "Priya Natarajan");
  assert.equal(result.working_on, "Builds tools for R&D teams.");
  assert.deepEqual(result.tags, ["Go", "Rust"]);
  assert.deepEqual(result.groups, ["University of Washington"]);
});

test("explains files it cannot read, and reads plain text as it is", async () => {
  await assert.rejects(readResumeFile(new File([zip({ "hello.txt": "hi" })], "archive.zip")), ResumeFileError);
  await assert.rejects(readResumeFile(new File([Buffer.from([0xd0, 0xcf, 0x11, 0xe0, 0, 0])], "old.doc")), ResumeFileError);
  assert.equal(await readResumeFile(new File(["Sam Lee\nSkills: Python"], "notes.txt")), "Sam Lee\nSkills: Python");
});
