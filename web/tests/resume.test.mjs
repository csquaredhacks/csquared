import { test } from "node:test";
import assert from "node:assert/strict";
import { parseResumeText } from "../src/resume.ts";

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
});
