import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const read = (relative) => readFile(path.join(root, relative), "utf8");

// Los Themes se cargan después de base.css: cada preset debe conservar reduced-motion.
for (const relative of [
  "src/ui/themes/dimensional.css",
  "src/ui/themes/clean.css",
  "src/ui/themes/immersive.css"
]) {
  const css = await read(relative);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/, `${relative} debe preservar reduced motion`);
  for (const token of ["fast", "normal", "slow"]) {
    assert.match(css, new RegExp(`--motion-${token}: var\\(--hache-f-motion-instant\\)`), `${relative} debe poner --motion-${token} en instant`);
  }
}

const immersive = await read("src/ui/themes/immersive.css");
assert.match(immersive, /--advanced-effects-enabled: 0/);

globalThis.CustomEvent = class CustomEvent {
  constructor(type, options) { this.type = type; this.detail = options?.detail; }
};
const interactions = await import(pathToFileURL(path.join(root, "src/ui/core/interactions.js")));

// Un scope Element debe escuchar pointerdown exterior en ownerDocument sin tratar el panel controlado como exterior.
const documentListeners = {};
const triggerListeners = {};
const triggerAttributes = new Map([["aria-controls", "menu"], ["aria-expanded", "false"]]);
const panelControl = {};
const panel = {
  hidden: false,
  contains: (target) => target === panelControl
};
const trigger = {
  getAttribute: (name) => triggerAttributes.get(name),
  setAttribute: (name, value) => triggerAttributes.set(name, value),
  addEventListener: (type, callback) => { triggerListeners[type] = callback; },
  focus: () => {}
};
const container = {
  dataset: { hacheDismiss: "outside" },
  querySelector: () => trigger,
  addEventListener: () => {},
  contains: (target) => target === trigger
};
const ownerDocument = {
  getElementById: (id) => id === "menu" ? panel : null,
  addEventListener: (type, callback) => { documentListeners[type] = callback; },
  removeEventListener: () => {}
};
const elementScope = {
  ownerDocument,
  querySelectorAll: (selector) => selector === "[data-hache-disclosure]" ? [container] : [],
  contains: (candidate) => candidate === panel || candidate === container
};
interactions.initDisclosures(elementScope);
assert.equal(typeof documentListeners.pointerdown, "function", "outside dismiss debe escucharse en ownerDocument para scopes Element");
triggerListeners.click();
assert.equal(panel.hidden, false);
documentListeners.pointerdown({ target: panelControl });
assert.equal(panel.hidden, false, "interactuar con un panel hermano controlado no debe cerrar el disclosure");
documentListeners.pointerdown({ target: {} });
assert.equal(panel.hidden, true, "un pointerdown realmente exterior debe cerrar el disclosure");

// Si submit fue emitido, el guard no debe revalidar: novalidate/formnovalidate son válidos.
const formListeners = {};
const formAttributes = new Map();
const submitAttributes = new Map();
const submit = {
  formNoValidate: true,
  getAttribute: (name) => submitAttributes.get(name) ?? null,
  setAttribute: (name, value) => submitAttributes.set(name, value),
  removeAttribute: (name) => submitAttributes.delete(name)
};
const form = {
  noValidate: true,
  querySelectorAll: () => [submit],
  checkValidity: () => { throw new Error("initSubmissionGuards no debe revalidar un submit ya emitido"); },
  getAttribute: (name) => formAttributes.get(name),
  setAttribute: (name, value) => formAttributes.set(name, value),
  removeAttribute: (name) => formAttributes.delete(name),
  addEventListener: (type, callback) => { formListeners[type] = callback; }
};
interactions.initSubmissionGuards({ querySelectorAll: () => [form] });
assert.doesNotThrow(() => formListeners.submit({ submitter: submit, preventDefault: () => {} }));
assert.equal(formAttributes.get("aria-busy"), "true");
assert.equal(submitAttributes.get("aria-disabled"), "true");
let duplicatePrevented = false;
formListeners.submit({ submitter: submit, preventDefault: () => { duplicatePrevented = true; } });
assert.equal(duplicatePrevented, true, "el segundo submit debe bloquearse también con novalidate/formnovalidate");

console.log("DESIGN_SYSTEM_REVIEW_REGRESSIONS_OK");
