"use strict";
function b64ToBytes(value) {
  const raw = atob(value.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(value.length/4)*4, "="));
  return Uint8Array.from(raw, ch => ch.charCodeAt(0));
}
function bytesToB64(bytes) {
  return btoa(String.fromCharCode(...new Uint8Array(bytes)))
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}
async function post(path, body) {
  const response = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: {"Content-Type": "application/json"},
    cache: "no-store",
    body: JSON.stringify(body)
  });
  if (!response.ok) throw new Error("Verificación rechazada o caducada.");
  return response.json();
}
const button = document.querySelector("#verify-passkey");
const result = document.querySelector("#result");
button.addEventListener("click", async () => {
  button.disabled = true;
  result.textContent = "Solicitando verificación…";
  try {
    if (!window.PublicKeyCredential) throw new Error("Tu navegador no soporta passkeys.");
    const options = await post("/api/passkey-check/start", {});
    const publicKey = {
      ...options,
      challenge: b64ToBytes(options.challenge),
      allowCredentials: (options.allowCredentials || []).map(
        x => ({...x, id: b64ToBytes(x.id)})
      )
    };
    const credential = await navigator.credentials.get({publicKey});
    if (!credential) throw new Error("No se completó la verificación.");
    const response = credential.response;
    const payload = {
      challenge: options.challenge,
      credential: {
        id: credential.id,
        rawId: bytesToB64(credential.rawId),
        type: credential.type,
        response: {
          authenticatorData: bytesToB64(response.authenticatorData),
          clientDataJSON: bytesToB64(response.clientDataJSON),
          signature: bytesToB64(response.signature),
          userHandle: response.userHandle ? bytesToB64(response.userHandle) : null
        },
        clientExtensionResults: credential.getClientExtensionResults()
      }
    };
    const outcome = await post("/api/passkey-check/finish", payload);
    if (outcome.status !== "verified" || outcome.grants_issued !== 0) {
      throw new Error("Respuesta de verificación inesperada.");
    }
    result.textContent = "Passkey verificada. No se autorizó ninguna operación.";
  } catch (e) {
    result.textContent = e.message || "No se pudo verificar la passkey.";
    button.disabled = false;
  }
});
