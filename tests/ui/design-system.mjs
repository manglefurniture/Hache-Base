import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const files = {
  foundation: "src/ui/core/foundation.css", semantic: "src/ui/core/semantic.css",
  base: "src/ui/core/base.css", components: "src/ui/core/components.css",
  interactions: "src/ui/core/interactions.js", dimensional: "src/ui/themes/dimensional.css",
  clean: "src/ui/themes/clean.css", immersive: "src/ui/themes/immersive.css",
  extensions: "src/ui/extensions/README.md"
};
const content = {};
for (const [name, relative] of Object.entries(files)) content[name] = await readFile(path.join(root, relative), "utf8");

function balanced(css) {
  let depth = 0;
  for (const char of css.replace(/\/\*[\s\S]*?\*\//g, "")) {
    if (char === "{") depth += 1;
    if (char === "}") depth -= 1;
    assert.ok(depth >= 0, "CSS cierra una llave antes de abrirla");
  }
  assert.equal(depth, 0, "CSS con llaves desbalanceadas");
}
for (const name of ["foundation", "semantic", "base", "components", "dimensional", "clean", "immersive"]) balanced(content[name]);

assert.match(content.foundation, /--hache-f-space-1:/);
assert.match(content.semantic, /--color-primary: var\(--hache-f-color-blue-700\)/);
assert.match(content.components, /--button-primary-bg: var\(--color-primary\)/);
assert.doesNotMatch(content.components, /#[0-9a-f]{3,8}|rgba?\(/i);
assert.match(content.semantic, /prefers-color-scheme: dark/);
assert.match(content.semantic, /:root\[data-theme="dark"\]/);
assert.match(content.semantic, /:root\[data-theme="light"\] \{ color-scheme: light; \}/);
assert.match(content.base, /prefers-reduced-motion: reduce/);
assert.match(content.base, /forced-colors: active/);
assert.match(content.base, /@container \(max-width: 30rem\)/);
assert.match(content.components, /@container \(min-width: 36rem\)/);
assert.match(content.components, /min-block-size: var\(--target-size\)/);
assert.match(content.components, /aria-current="page"/);
assert.match(content.components, /aria-invalid="true"/);
assert.match(content.components, /aria-busy="true"/);
for (const variant of ["secondary", "ghost", "destructive"]) assert.match(content.components, new RegExp(`hache-button--${variant}`));
assert.match(content.dimensional, /:root,/);
assert.match(content.clean, /data-visual-level="clean"/);
assert.match(content.immersive, /data-visual-level="immersive"/);
assert.match(content.immersive, /--advanced-effects-enabled: 0/);
assert.doesNotMatch(content.immersive.replace(/\/\*[\s\S]*?\*\//g, ""), /canvas|webgl|perspective|parallax/i);
assert.match(content.extensions, /fallback estático o funcional/);

const hexToRgb = (hex) => [0, 2, 4].map((offset) => Number.parseInt(hex.replace("#", "").slice(offset, offset + 2), 16));
const luminance = (hex) => hexToRgb(hex).map((channel) => channel / 255).map((value) => value <= .03928 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4).reduce((sum, value, index) => sum + value * [.2126, .7152, .0722][index], 0);
const contrast = (a, b) => { const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x); return (high + .05) / (low + .05); };
for (const [foreground, background, minimum] of [
  ["#0f172a", "#f8fafc", 4.5], ["#475569", "#ffffff", 4.5], ["#1d4ed8", "#ffffff", 4.5],
  ["#b91c1c", "#ffffff", 4.5], ["#f8fafc", "#0b1220", 4.5], ["#93b4ff", "#0f172a", 4.5],
  ["#ffb4ab", "#0f172a", 4.5]
]) assert.ok(contrast(foreground, background) >= minimum, `${foreground} no alcanza ${minimum}:1 sobre ${background}`);

globalThis.CustomEvent = class CustomEvent { constructor(type, options) { this.type = type; this.detail = options?.detail; } };
const interactions = await import(pathToFileURL(path.join(root, files.interactions)));
const attributes = new Map();
const rootStub = { setAttribute: (name, value) => attributes.set(name, value), removeAttribute: (name) => attributes.delete(name), dispatchEvent: () => true };
assert.equal(interactions.applyThemePreference(rootStub, "dark"), "dark");
assert.equal(attributes.get("data-theme"), "dark");
assert.equal(interactions.applyThemePreference(rootStub, "light"), "light");
assert.equal(attributes.get("data-theme"), "light");
assert.equal(interactions.applyThemePreference(rootStub, "invalid"), "system");
assert.equal(attributes.has("data-theme"), false);

let persisted = null;
const controlListeners = {};
const controlAttributes = new Map();
const themeControl = { dataset: { hacheThemeValue: "light" }, setAttribute: (name, value) => controlAttributes.set(name, value), addEventListener: (type, callback) => { controlListeners[type] = callback; } };
const themeScope = { querySelectorAll: () => [themeControl] };
const storage = { getItem: () => "dark", setItem: (_key, value) => { persisted = value; } };
const controller = interactions.initThemePreference({ root: rootStub, scope: themeScope, storage });
assert.equal(controller.get(), "dark");
controlListeners.click();
assert.equal(controller.get(), "light");
assert.equal(persisted, "light");
assert.equal(controlAttributes.get("aria-pressed"), "true");

const triggerListeners = {}, containerListeners = {}, scopeListeners = {};
let focusReturned = false;
const triggerAttributes = new Map([["aria-controls", "menu"], ["aria-expanded", "false"]]);
const trigger = { dataset: {}, getAttribute: (name) => triggerAttributes.get(name), setAttribute: (name, value) => triggerAttributes.set(name, value), addEventListener: (type, callback) => { triggerListeners[type] = callback; }, focus: () => { focusReturned = true; } };
const panel = { hidden: false };
const container = { dataset: { hacheDismiss: "outside" }, querySelector: () => trigger, addEventListener: (type, callback) => { containerListeners[type] = callback; }, contains: () => false };
const scope = { querySelectorAll: (selector) => selector === "[data-hache-disclosure]" ? [container] : [], getElementById: () => panel, addEventListener: (type, callback) => { scopeListeners[type] = callback; }, removeEventListener: () => {} };
interactions.initDisclosures(scope);
assert.equal(panel.hidden, true);
triggerListeners.click(); assert.equal(panel.hidden, false);
containerListeners.keydown({ key: "Escape" }); assert.equal(panel.hidden, true); assert.equal(focusReturned, true);
triggerListeners.click(); scopeListeners.pointerdown({ target: {} }); assert.equal(panel.hidden, true);

globalThis.HTMLDialogElement = class HTMLDialogElement {};
const dialogListeners = {}, openerListeners = {}, closerListeners = {};
let dialogOpened = false, openerFocused = false;
const dialog = Object.assign(new HTMLDialogElement(), {
  open: false,
  showModal() { this.open = true; dialogOpened = true; },
  close() { this.open = false; dialogListeners.close?.(); },
  addEventListener(type, callback) { dialogListeners[type] = callback; }
});
const opener = { dataset: { hacheDialogOpen: "dialog" }, addEventListener: (type, callback) => { openerListeners[type] = callback; }, focus: () => { openerFocused = true; } };
const closer = { closest: () => dialog, addEventListener: (type, callback) => { closerListeners[type] = callback; } };
const dialogScope = {
  querySelectorAll(selector) { if (selector === "[data-hache-dialog-open]") return [opener]; if (selector === "[data-hache-dialog-close]") return [closer]; if (selector === "dialog") return [dialog]; return []; },
  getElementById: () => dialog
};
interactions.initDialogs(dialogScope);
openerListeners.click(); assert.equal(dialogOpened, true);
closerListeners.click(); assert.equal(openerFocused, true);

const formListeners = {}, submitAttributes = new Map(), formAttributes = new Map();
const submit = { disabled: false, setAttribute: (name, value) => submitAttributes.set(name, value), removeAttribute: (name) => submitAttributes.delete(name) };
const form = {
  querySelectorAll: () => [submit], checkValidity: () => true,
  getAttribute: (name) => formAttributes.get(name), setAttribute: (name, value) => formAttributes.set(name, value), removeAttribute: (name) => formAttributes.delete(name),
  addEventListener: (type, callback) => { formListeners[type] = callback; }
};
interactions.initSubmissionGuards({ querySelectorAll: () => [form] });
let duplicatePrevented = false;
formListeners.submit({ preventDefault: () => { duplicatePrevented = true; } });
assert.equal(formAttributes.get("aria-busy"), "true"); assert.equal(submit.disabled, true);
formListeners.submit({ preventDefault: () => { duplicatePrevented = true; } }); assert.equal(duplicatePrevented, true);
formListeners["hache:submit-complete"](); assert.equal(formAttributes.has("aria-busy"), false); assert.equal(submit.disabled, false);

const cssBytes = (await Promise.all(["foundation", "semantic", "base", "components", "dimensional", "clean", "immersive"].map((name) => stat(path.join(root, files[name]))))).reduce((sum, item) => sum + item.size, 0);
const jsBytes = (await stat(path.join(root, files.interactions))).size;
assert.ok(cssBytes <= 40 * 1024, `Core + presets excede 40 KiB: ${cssBytes}`);
assert.ok(jsBytes <= 12 * 1024, `Helper opcional excede 12 KiB: ${jsBytes}`);
console.log(`DESIGN_SYSTEM_UI_OK css=${cssBytes}B js=${jsBytes}B`);
