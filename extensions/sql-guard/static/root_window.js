"use strict";
const state=document.getElementById("status"), expiry=document.getElementById("expiry"),
 message=document.getElementById("message"), enable=document.getElementById("enable"),
 disable=document.getElementById("disable");
function b64bytes(s){return Uint8Array.from(atob(s.replace(/-/g,"+").replace(/_/g,"/").padEnd(Math.ceil(s.length/4)*4,"=")),c=>c.charCodeAt(0));}
function b64str(b){return btoa(String.fromCharCode(...new Uint8Array(b))).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/g,"");}
async function post(path,body){
 const r=await fetch(path,{method:"POST",credentials:"same-origin",cache:"no-store",
 headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
 if(!r.ok)throw Error("Solicitud rechazada o servicio no disponible.");
 return r.json();
}
async function refresh(){
 const response=await fetch("/api/root-window/status",{credentials:"same-origin",cache:"no-store"});
 if(!response.ok)throw Error("El estado no está disponible.");
 const data=await response.json();
 state.textContent=data.enabled?"ENCENDIDO":"APAGADO";
 expiry.textContent=data.enabled?"Cierre automático: "+new Date(data.expires_at*1000).toLocaleString():"No hay permisos temporales activos.";
 enable.disabled=!!data.enabled;disable.disabled=!data.enabled;
}
async function toggle(action){
 enable.disabled=disable.disabled=true;
 message.textContent="Solicitando verificación...";
 try{
  if(!window.PublicKeyCredential)throw Error("Navegador sin soporte de passkey.");
  const o=await post("/api/root-window/start",{action});
  const options={...o,challenge:b64bytes(o.challenge),
   allowCredentials:(o.allowCredentials||[]).map(c=>({...c,id:b64bytes(c.id)}))};
  const c=await navigator.credentials.get({publicKey:options});
  if(!c)throw Error("No se verificó la passkey.");
  const r=c.response;
  await post("/api/root-window/finish",{action,challenge:o.challenge,credential:{
    id:c.id,rawId:b64str(c.rawId),type:c.type,clientExtensionResults:c.getClientExtensionResults(),
    response:{authenticatorData:b64str(r.authenticatorData),clientDataJSON:b64str(r.clientDataJSON),
      signature:b64str(r.signature),userHandle:r.userHandle?b64str(r.userHandle):null}}});
  message.textContent=action==="enable"?"Ventana activada.":"Ventana desactivada.";
 }catch(e){message.textContent=e.message||"No se pudo completar.";}
 try{await refresh();}catch(e){state.textContent="NO DISPONIBLE";enable.disabled=disable.disabled=true;}
}
enable.addEventListener("click",()=>toggle("enable"));
disable.addEventListener("click",()=>toggle("disable"));
refresh().catch(()=>{state.textContent="NO DISPONIBLE";enable.disabled=disable.disabled=true;});
