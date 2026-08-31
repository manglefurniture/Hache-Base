const THEME_PREFERENCES = new Set(["light", "dark", "system"]);

function resolveScopedId(scope, id) {
  if (!id) return null;
  if (typeof scope.getElementById === "function") return scope.getElementById(id);

  const candidate = scope.ownerDocument?.getElementById?.(id) || null;
  if (!candidate) return null;
  if (typeof scope.contains === "function" && !scope.contains(candidate)) return null;
  return candidate;
}

function restoreAttribute(element, name, previous) {
  if (previous === null) element.removeAttribute(name);
  else element.setAttribute(name, previous);
}

function isSubmitControl(control) {
  const tagName = control?.tagName?.toLowerCase?.() || "";
  const type = String(control?.type || "").toLowerCase();
  return (tagName === "button" && type === "submit") ||
    (tagName === "input" && (type === "submit" || type === "image"));
}

export function applyThemePreference(root, preference) {
  const next = THEME_PREFERENCES.has(preference) ? preference : "system";
  if (next === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", next);
  return next;
}

export function initThemePreference({
  root = document.documentElement,
  scope = document,
  storage,
  storageKey = "hache-theme"
} = {}) {
  let resolvedStorage = storage;
  if (resolvedStorage === undefined) {
    try { resolvedStorage = globalThis.localStorage; } catch { resolvedStorage = null; }
  }

  let stored = "system";
  try { stored = resolvedStorage?.getItem(storageKey) || "system"; } catch { /* storage may be unavailable */ }
  let current = applyThemePreference(root, stored);

  const updateControls = () => {
    scope.querySelectorAll("[data-hache-theme-value]").forEach((control) => {
      control.setAttribute("aria-pressed", String(control.dataset.hacheThemeValue === current));
    });
  };

  const set = (value) => {
    current = applyThemePreference(root, value);
    try { resolvedStorage?.setItem(storageKey, current); } catch { /* preference remains valid for this page */ }
    updateControls();
    root.dispatchEvent(new CustomEvent("hache:theme-change", { detail: { preference: current } }));
    return current;
  };

  scope.querySelectorAll("[data-hache-theme-value]").forEach((control) => {
    control.addEventListener("click", () => set(control.dataset.hacheThemeValue));
  });
  updateControls();
  return { get: () => current, set };
}

export function initDisabledControls(scope = document) {
  const blockDisabledActivation = (event) => {
    const control = event.target?.closest?.("[aria-disabled='true']");
    if (!control) return;
    if (typeof scope.contains === "function" && !scope.contains(control)) return;
    event.preventDefault();
    event.stopPropagation();
  };

  scope.addEventListener("click", blockDisabledActivation, true);
  return { destroy: () => scope.removeEventListener("click", blockDisabledActivation, true) };
}

export function initDisclosures(scope = document) {
  const instances = [];
  const outsideTarget = scope.ownerDocument?.addEventListener ? scope.ownerDocument : scope;

  scope.querySelectorAll("[data-hache-disclosure]").forEach((container) => {
    const trigger = container.querySelector("[aria-controls]");
    const panel = trigger && resolveScopedId(scope, trigger.getAttribute("aria-controls"));
    if (!trigger || !panel) return;

    const setOpen = (open, returnFocus = false) => {
      trigger.setAttribute("aria-expanded", String(open));
      panel.hidden = !open;
      if (returnFocus) trigger.focus();
    };
    setOpen(trigger.getAttribute("aria-expanded") === "true");

    const onTriggerClick = () => setOpen(trigger.getAttribute("aria-expanded") !== "true");
    trigger.addEventListener("click", onTriggerClick);

    const onEscape = (event) => {
      if (event.key === "Escape" && trigger.getAttribute("aria-expanded") === "true") setOpen(false, true);
    };
    container.addEventListener("keydown", onEscape);
    if (panel !== container && typeof panel.addEventListener === "function") panel.addEventListener("keydown", onEscape);

    const outside = (event) => {
      if (
        container.dataset.hacheDismiss === "outside" &&
        !container.contains(event.target) &&
        !panel.contains?.(event.target)
      ) setOpen(false);
    };
    outsideTarget.addEventListener("pointerdown", outside);
    instances.push({
      close: () => setOpen(false),
      destroy: () => {
        trigger.removeEventListener?.("click", onTriggerClick);
        outsideTarget.removeEventListener("pointerdown", outside);
        container.removeEventListener?.("keydown", onEscape);
        if (panel !== container) panel.removeEventListener?.("keydown", onEscape);
      }
    });
  });
  return instances;
}

export function initDialogs(scope = document) {
  const openers = new Map();
  scope.querySelectorAll("[data-hache-dialog-open]").forEach((trigger) => {
    const dialog = resolveScopedId(scope, trigger.dataset.hacheDialogOpen);
    if (!(dialog instanceof HTMLDialogElement)) return;
    trigger.addEventListener("click", () => {
      openers.set(dialog, trigger);
      if (!dialog.open) dialog.showModal();
    });
  });
  scope.querySelectorAll("[data-hache-dialog-close]").forEach((trigger) => {
    const dialog = trigger.closest("dialog");
    if (dialog) trigger.addEventListener("click", () => dialog.close());
  });
  scope.querySelectorAll("dialog").forEach((dialog) => {
    dialog.addEventListener("close", () => openers.get(dialog)?.focus());
  });
}

export function initSubmissionGuards(scope = document) {
  scope.querySelectorAll("form[data-hache-prevent-double-submit]").forEach((form) => {
    const controls = (submitter) => {
      const associated = form.elements
        ? [...form.elements].filter(isSubmitControl)
        : [...form.querySelectorAll("button:not([type]), button[type='submit'], input[type='submit'], input[type='image']")];
      if (submitter && !associated.includes(submitter)) associated.push(submitter);
      return associated;
    };
    const previousStates = new Map();

    const markBusy = (control) => {
      if (!previousStates.has(control)) {
        previousStates.set(control, {
          ariaBusy: control.getAttribute?.("aria-busy") ?? null,
          ariaDisabled: control.getAttribute?.("aria-disabled") ?? null
        });
      }
      control.setAttribute("aria-busy", "true");
      control.setAttribute("aria-disabled", "true");
    };

    const unlock = () => {
      form.removeAttribute("aria-busy");
      previousStates.forEach((previous, control) => {
        restoreAttribute(control, "aria-busy", previous.ariaBusy);
        restoreAttribute(control, "aria-disabled", previous.ariaDisabled);
      });
      previousStates.clear();
    };

    form.addEventListener("submit", (event) => {
      if (form.getAttribute("aria-busy") === "true") { event.preventDefault(); return; }
      /* Si se emitió submit, el navegador ya resolvió validación o una omisión válida
         mediante novalidate/formnovalidate. El guard no debe revalidar. */
      form.setAttribute("aria-busy", "true");
      controls(event.submitter).forEach(markBusy);
    });
    form.addEventListener("hache:submit-complete", unlock);
  });
}
