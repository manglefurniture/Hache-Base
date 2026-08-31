import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const read = (relative) => readFile(path.join(root, relative), "utf8");

// Los Themes se cargan después de base.css: cada preset debe conservar reduced-motion
// sin elevar la especificidad por encima de un :root de proyecto cargado después.
for (const [relative, level] of [
  ["src/ui/themes/dimensional.css", "dimensional"],
  ["src/ui/themes/clean.css", "clean"],
  ["src/ui/themes/immersive.css", "immersive"]
]) {
  const css = await read(relative);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/, `${relative} debe preservar reduced motion`);
  assert.match(css, new RegExp(`:root:where\\(\\[data-visual-level="${level}"\\]\\)`), `${relative} debe mantener especificidad compatible con overrides de proyecto`);
  assert.doesNotMatch(css, /:root\[data-visual-level=/, `${relative} no debe usar selector de preset con especificidad superior a :root`);
  for (const token of ["fast", "normal", "slow"]) {
    assert.match(css, new RegExp(`--motion-${token}: var\\(--hache-f-motion-instant\\)`), `${relative} debe poner --motion-${token} en instant`);
  }
}

const semantic = await read("src/ui/core/semantic.css");
assert.match(semantic, /:root:where\(:not\(\[data-theme="light"\]\)\)/, "system dark debe mantener especificidad compatible con overrides");
assert.match(semantic, /:root:where\(\[data-theme="dark"\]\)/, "dark manual debe mantener especificidad compatible con overrides");
assert.match(semantic, /:root:where\(\[data-theme="light"\]\)/, "light manual debe mantener especificidad compatible con overrides");
assert.match(semantic, /:root:where\(\[data-density="compact"\]\)/, "density compact debe mantener especificidad compatible con overrides");
assert.doesNotMatch(semantic, /:root\[data-(?:theme|density)=/, "los estados semánticos no deben superar la especificidad de :root");

const immersive = await read("src/ui/themes/immersive.css");
assert.match(immersive, /--advanced-effects-enabled: 0/);

globalThis.CustomEvent = class CustomEvent {
  constructor(type, options) { this.type = type; this.detail = options?.detail; }
};
const interactions = await import(pathToFileURL(path.join(root, "src/ui/core/interactions.js")));

// Un scope Element debe escuchar pointerdown exterior en ownerDocument sin tratar el panel controlado como exterior.
// Escape debe funcionar tanto desde el contenedor como desde un panel hermano controlado.
// destroy() debe limpiar el click del trigger para permitir reinicialización sin handlers duplicados.
const documentListeners = new Map();
const triggerListeners = new Map();
const containerListeners = new Map();
const panelListeners = new Map();
const addListener = (registry, type, callback) => {
  if (!registry.has(type)) registry.set(type, new Set());
  registry.get(type).add(callback);
};
const removeListener = (registry, type, callback) => registry.get(type)?.delete(callback);
const emit = (registry, type, event = {}) => {
  for (const callback of [...(registry.get(type) || [])]) callback(event);
};

const triggerAttributes = new Map([["aria-controls", "menu"], ["aria-expanded", "false"]]);
let focusReturned = false;
const panelControl = {};
const panel = {
  hidden: false,
  contains: (target) => target === panelControl,
  addEventListener: (type, callback) => addListener(panelListeners, type, callback),
  removeEventListener: (type, callback) => removeListener(panelListeners, type, callback)
};
const trigger = {
  getAttribute: (name) => triggerAttributes.get(name),
  setAttribute: (name, value) => triggerAttributes.set(name, value),
  addEventListener: (type, callback) => addListener(triggerListeners, type, callback),
  removeEventListener: (type, callback) => removeListener(triggerListeners, type, callback),
  focus: () => { focusReturned = true; }
};
const container = {
  dataset: { hacheDismiss: "outside" },
  querySelector: () => trigger,
  addEventListener: (type, callback) => addListener(containerListeners, type, callback),
  removeEventListener: (type, callback) => removeListener(containerListeners, type, callback),
  contains: (target) => target === trigger
};
const ownerDocument = {
  getElementById: (id) => id === "menu" ? panel : null,
  addEventListener: (type, callback) => addListener(documentListeners, type, callback),
  removeEventListener: (type, callback) => removeListener(documentListeners, type, callback)
};
const elementScope = {
  ownerDocument,
  querySelectorAll: (selector) => selector === "[data-hache-disclosure]" ? [container] : [],
  contains: (candidate) => candidate === panel || candidate === container
};
const firstDisclosureInstances = interactions.initDisclosures(elementScope);
assert.equal(documentListeners.get("pointerdown")?.size, 1, "outside dismiss debe escucharse en ownerDocument para scopes Element");
assert.equal(panelListeners.get("keydown")?.size, 1, "Escape debe escucharse también en un panel hermano controlado");
assert.equal(triggerListeners.get("click")?.size, 1, "debe existir un único click handler del trigger");
emit(triggerListeners, "click");
assert.equal(panel.hidden, false);
emit(documentListeners, "pointerdown", { target: panelControl });
assert.equal(panel.hidden, false, "interactuar con un panel hermano controlado no debe cerrar el disclosure");
emit(panelListeners, "keydown", { key: "Escape" });
assert.equal(panel.hidden, true, "Escape desde un control del panel hermano debe cerrar el disclosure");
assert.equal(focusReturned, true, "Escape desde el panel hermano debe devolver foco al trigger");
emit(triggerListeners, "click");
emit(documentListeners, "pointerdown", { target: {} });
assert.equal(panel.hidden, true, "un pointerdown realmente exterior debe cerrar el disclosure");

firstDisclosureInstances[0].destroy();
assert.equal(triggerListeners.get("click")?.size || 0, 0, "destroy debe retirar el click handler del trigger");
assert.equal(panelListeners.get("keydown")?.size || 0, 0, "destroy debe retirar Escape del panel hermano");
assert.equal(documentListeners.get("pointerdown")?.size || 0, 0, "destroy debe retirar outside dismiss");
const secondDisclosureInstances = interactions.initDisclosures(elementScope);
assert.equal(triggerListeners.get("click")?.size, 1, "reinicializar no debe acumular click handlers");
emit(triggerListeners, "click");
assert.equal(panel.hidden, false, "un solo click tras destroy + reinit debe alternar una sola vez");
secondDisclosureInstances[0].destroy();

// Si submit fue emitido, el guard no debe revalidar: novalidate/formnovalidate son válidos.
// También debe incluir <button> sin type, cuyo tipo HTML predeterminado es submit.
const formListeners = {};
const formAttributes = new Map();
const submitAttributes = new Map();
const implicitSubmitAttributes = new Map();
const submit = {
  formNoValidate: true,
  getAttribute: (name) => submitAttributes.get(name) ?? null,
  setAttribute: (name, value) => submitAttributes.set(name, value),
  removeAttribute: (name) => submitAttributes.delete(name)
};
const implicitSubmit = {
  getAttribute: (name) => implicitSubmitAttributes.get(name) ?? null,
  setAttribute: (name, value) => implicitSubmitAttributes.set(name, value),
  removeAttribute: (name) => implicitSubmitAttributes.delete(name)
};
const form = {
  noValidate: true,
  querySelectorAll: (selector) => {
    assert.match(selector, /button:not\(\[type\]\)/, "el guard debe seleccionar botones con submit implícito");
    return [submit, implicitSubmit];
  },
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
assert.equal(implicitSubmitAttributes.get("aria-busy"), "true", "button sin type debe recibir estado busy");
assert.equal(implicitSubmitAttributes.get("aria-disabled"), "true", "button sin type debe anunciar estado disabled");
let duplicatePrevented = false;
formListeners.submit({ submitter: submit, preventDefault: () => { duplicatePrevented = true; } });
assert.equal(duplicatePrevented, true, "el segundo submit debe bloquearse también con novalidate/formnovalidate");

console.log("DESIGN_SYSTEM_REVIEW_REGRESSIONS_OK");
