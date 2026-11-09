// Run from web: node --test tests/product-theme.test.mjs
// Uses the CSS parser already installed by Vite; no browser or API needed.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import postcss from "postcss";

const css = postcss.parse(readFileSync(new URL("../src/product-theme.css", import.meta.url), "utf8"));
const palette = Object.fromEntries(css.nodes.find((node) => node.selector === ".product-theme")
  .nodes.filter((node) => node.type === "decl").map((node) => [node.prop, node.value]));

function color(value) {
  return value.replace(/var\((--[\w-]+)\)/g, (_, name) => palette[name]);
}

function declaration(selector, property) {
  let value;
  css.walkRules(selector, (rule) => rule.walkDecls(property, (decl) => { value = decl.value; }));
  assert.ok(value, `${selector} must declare ${property}`);
  return color(value);
}

function luminance(hex) {
  assert.match(hex, /^#[0-9a-f]{6}$/i);
  const rgb = hex.slice(1).match(/../g).map((part) => {
    const value = parseInt(part, 16) / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
  return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
}

function contrast(foreground, background, minimum, label) {
  const a = luminance(color(foreground));
  const b = luminance(color(background));
  const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  assert.ok(ratio >= minimum, `${label}: ${ratio.toFixed(2)}:1, expected ${minimum}:1`);
}

test("supplemental rules cannot leak into the Graph or kiosk via global selectors", () => {
  css.walkRules((rule) => {
    // Split only selector lists, not commas inside :is() or :not().
    for (const selector of postcss.list.comma(rule.selector)) {
      assert.match(selector, /^\.product-theme(?:[\s:]|$)/, selector);
      assert.doesNotMatch(selector, /:global|\b(?:html|body)\b/);
    }
  });
  css.walkAtRules((rule) => assert.equal(rule.name, "media", "No remote imports, global fonts or animations"));
});

test("product text and action states meet WCAG AA normal-text contrast", () => {
  const backgrounds = ["--ink", "--surface", "--raised"];
  for (const text of ["--text", "--muted", "--accent-deep", "--good"]) {
    for (const background of backgrounds) contrast(palette[text], palette[background], 4.5, `${text} on ${background}`);
  }
  contrast(palette["--on-accent"], palette["--accent"], 4.5, "Primary action / active navigation");
  contrast(declaration(".product-theme .button:hover", "color"), declaration(".product-theme .button:hover", "background"), 4.5, "Primary hover");
  contrast(declaration(".product-theme .provider-btn", "color"), declaration(".product-theme .provider-btn", "background"), 4.5, "Get started");
  contrast(declaration(".product-theme .provider-btn", "color"), declaration(".product-theme .provider-btn:hover", "background"), 4.5, "Get started hover");
  contrast(palette["--muted"], declaration('.product-theme [data-page="/plan"] section[aria-labelledby="recovery"]', "background"), 4.5, "Recovery explanation");
});

test("input boundaries and keyboard focus meet non-text contrast", () => {
  for (const background of ["--ink", "--surface", "--raised"]) {
    contrast(palette["--field"], palette[background], 3, `Input boundary on ${background}`);
    contrast(palette["--accent-deep"], palette[background], 3, `Focus on ${background}`);
  }
  contrast(palette["--accent-deep"], palette["--accent"], 3, "Focus against primary action");
});
