import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const read = (relative) => readFile(path.join(rootDir, relative), "utf8");

globalThis.CustomEvent = class CustomEvent {
  constructor(type, options) { this.type = type; this.detail = options?.detail; }
};

const interactions = await import(pathToFileURL(path.join(rootDir, "src/ui/core/interactions.js")));
const listeners = new Map();
const addListener = (type, callback) => {
  if (!listeners.has(type)) listeners.set(type, new Set());
  listeners.get(type).add(callback);
};
const removeListener = (type, callback) => listeners.get(type)?.delete(callback);
const emit = (type, event) => {
  for (const callback of [...(listeners.get(type) || [])]) callback(event);
};

const attributes = new Map();
const themeEvents = [];
const root = {
  setAttribute: (name, value) => attributes.set(name, value),
  removeAttribute: (name) => attributes.delete(name),
  dispatchEvent: (event) => { themeEvents.push(event); return true; }
};

const lightAttrs = new Map();
const darkAttrs = new Map();
const makeControl = (value, attrs) => ({
  dataset: { hacheThemeValue: value },
  setAttribute: (name, next) => attrs.set(name, next),
  addEventListener: () => {}
});
const lightControl = makeControl("light", lightAttrs);
const darkControl = makeControl("dark", darkAttrs);

const values = new Map([["hache-theme", "dark"]]);
let writes = 0;
const storage = {
  getItem: (key) => values.get(key) ?? null,
  setItem: (key, value) => { writes += 1; values.set(key, value); }
};
const view = {
  addEventListener: addListener,
  removeEventListener: removeListener
};
const scope = {
  defaultView: view,
  querySelectorAll: (selector) => selector === "[data-hache-theme-value]" ? [lightControl, darkControl] : []
};

const controller = interactions.initThemePreference({ root, scope, storage });
assert.equal(controller.get(), "dark");
assert.equal(darkAttrs.get("aria-pressed"), "true");
assert.equal(listeners.get("storage")?.size, 1, "debe escuchar cambios de storage del contexto");

emit("storage", { key: "hache-theme", newValue: "light", storageArea: storage });
assert.equal(controller.get(), "light", "otro contexto same-origin debe actualizar el tema sin refresh");
assert.equal(attributes.get("data-theme"), "light");
assert.equal(lightAttrs.get("aria-pressed"), "true");
assert.equal(writes, 0, "un storage event no debe volver a persistir y crear loops");
assert.equal(themeEvents.at(-1)?.detail?.preference, "light");

const eventCount = themeEvents.length;
emit("storage", { key: "hache-theme", newValue: "light", storageArea: storage });
assert.equal(themeEvents.length, eventCount, "el mismo valor no debe emitir trabajo duplicado");

emit("storage", { key: "hache-theme", newValue: "dark", storageArea: {} });
assert.equal(controller.get(), "light", "un storageArea distinto no debe contaminar la preferencia");

values.delete("hache-theme");
emit("storage", { key: null, newValue: null, storageArea: storage });
assert.equal(controller.get(), "system", "localStorage.clear debe restaurar system");
assert.equal(attributes.has("data-theme"), false);
assert.equal(writes, 0, "sincronizar clear tampoco debe persistir de vuelta");

controller.destroy();
assert.equal(listeners.get("storage")?.size || 0, 0, "destroy debe retirar el listener de storage");
emit("storage", { key: "hache-theme", newValue: "dark", storageArea: storage });
assert.equal(controller.get(), "system", "después de destroy no debe reaccionar a otros contextos");

const emailDocs = await read("integrations/email/README.md");
assert.match(emailDocs, /evento de negocio confirmado/);
assert.match(emailDocs, /después del `commit` o usar un outbox/);
assert.match(emailDocs, /regresión de cobertura/);
assert.match(emailDocs, /no debe deshacer la operación ya confirmada/);

const checklist = await read("docs/CHECKLIST-NUEVO-PROYECTO.md");
assert.match(checklist, /tabs\/iframes same-origin ya abiertos se actualizan sin refresh y sin loops de persistencia/);
assert.match(checklist, /dropdowns, autocompletes, popovers/);
assert.match(checklist, /inventariar todos los entry points capaces de confirmarlo/);
assert.match(checklist, /regresión que cubra los entry points capaces de confirmar el evento/);

console.log("REUSE_HARDENING_REGRESSION_OK");
