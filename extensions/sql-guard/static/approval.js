"use strict";
const b64ToBytes = (value) => {
  const raw = atob(value.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(value.length/4)*4, "="));
  return Uint8Array.from(raw, ch => ch.charCodeAt(0));
};
const bytesToB64 = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf)))
  .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");

async function post(path, body) {
  const response = await fetch(path, {
    method: "POST", headers: {"Content-Type": "application/json"},
    credentials: "same-origin", body: JSON.stringify(body)
  });
  if (!response.ok) throw new Error("Operación rechazada o caducada.");
  return response.json();
}
function serializeCredential(c) {
  const r = c.response;
  const response = {
    clientDataJSON: bytesToB64(r.clientDataJSON),
  };
  if (r.attestationObject) response.attestationObject = bytesToB64(r.attestationObject);
  if (r.authenticatorData) response.authenticatorData = bytesToB64(r.authenticatorData);
  if (r.signature) response.signature = bytesToB64(r.signature);
  if (r.userHandle) response.userHandle = bytesToB64(r.userHandle);
  return {
    id: c.id, rawId: bytesToB64(c.rawId), type: c.type,
    response, clientExtensionResults: c.getClientExtensionResults(),
  };
}
const result = document.querySelector("#result");
const button = document.querySelector("button");
const mode = document.body.dataset.mode;
const requestId = document.body.dataset.requestId;

async function enroll() {
  const bootstrap_token = document.querySelector("#bootstrap").value;
  const o = await post("/api/enroll/start", {bootstrap_token});
  const publicKey = {...o,
    challenge: b64ToBytes(o.challenge),
    user: {...o.user, id: b64ToBytes(o.user.id)},
    excludeCredentials: (o.excludeCredentials || []).map(x => ({...x, id: b64ToBytes(x.id)}))
  };
  const credential = await navigator.credentials.create({publicKey});
  await post("/api/enroll/finish", {challenge: o.challenge, credential: serializeCredential(credential)});
  document.querySelector("#bootstrap").value = "";
  result.textContent = "Passkey registrada.";
}
async function approve() {
  const o = await post("/api/approve/start", {request_id: requestId});
  const publicKey = {...o,
    challenge: b64ToBytes(o.challenge),
    allowCredentials: (o.allowCredentials || []).map(x => ({...x, id: b64ToBytes(x.id)}))
  };
  const credential = await navigator.credentials.get({publicKey});
  await post("/api/approve/finish", {
    request_id: requestId, challenge: o.challenge, credential: serializeCredential(credential)
  });
  result.textContent = "Operación autorizada. Regresa a ChatGPT.";
}
async function loadOperation() {
  const response = await fetch("/api/pending/" + encodeURIComponent(requestId),
    {credentials: "same-origin", cache: "no-store"});
  if (!response.ok) throw new Error("La solicitud ya no está disponible.");
  document.querySelector("#operation").textContent = JSON.stringify(await response.json(), null, 2);
}
button.addEventListener("click", async () => {
  button.disabled = true;
  result.textContent = "Verificando…";
  try {
    if (!window.PublicKeyCredential) throw new Error("Tu navegador no soporta passkeys.");
    if (mode === "enroll") await enroll();
    else await approve();
  } catch (err) {
    result.textContent = err.message || "No se pudo completar.";
    button.disabled = false;
  }
});
if (mode === "approve") loadOperation().catch(err => {
  result.textContent = err.message;
  button.disabled = true;
});
