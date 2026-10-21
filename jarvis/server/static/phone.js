"use strict";
const $ = id => document.getElementById(id);
let socket, partial, audio, recorder, media, recordChunks = [];
function status(text, error=false) { $('status').textContent=text; $('status').className=error?'error':''; }
function message(role, text) {
  const item=document.createElement('div'); item.className='message '+role;
  const body=document.createElement('span'); body.textContent=text; item.append(body);
  if(role==='assistant') {
    const button=document.createElement('button');button.textContent='Felolvasás';button.onclick=()=>void play(body.textContent);item.append(document.createElement('br'),button);
  }
  $('messages').append(item); $('messages').scrollTop=$('messages').scrollHeight; return body;
}
async function play(text) {
  if(audio)audio.pause();
  try { const r=await fetch('/api/tts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});if(!r.ok)throw Error('Nem sikerült a felolvasás.');
    const url=URL.createObjectURL(await r.blob());audio=new Audio(url);audio.onended=()=>URL.revokeObjectURL(url);await audio.play();
  }catch(e){status(e.message,true);}
}
function send(data){if(socket?.readyState===WebSocket.OPEN)socket.send(JSON.stringify(data));else status('Nincs kapcsolat.',true);}
async function connect(){
  const check=await fetch('/api/health');
  if(!check.ok){$('chat').style.display='none';$('login').style.display='block';status('Párosítás szükséges.');return;}
  $('login').style.display='none';$('chat').style.display='block';
  socket=new WebSocket(`${location.protocol==='https:'?'wss:':'ws:'}//${location.host}/ws`);
  socket.onopen=()=>status('Kapcsolódva.');
  socket.onclose=()=>{status('A kapcsolat megszakadt. Újracsatlakozás…',true);setTimeout(()=>void connect().catch(e=>status(e.message,true)),2000);};
  socket.onmessage=e=>{
    const m=JSON.parse(e.data);
    if(m.type==='session_state'){$('messages').replaceChildren();partial=null;for(const h of m.messages||[])if(['user','assistant'].includes(h.role)&&typeof h.content==='string'&&h.content&&!h.content.startsWith('<tool_result')&&!h.content.startsWith('(internal protocol'))message(h.role,h.content);}
    else if(m.type==='stream_begin')partial=message('assistant','');
    else if(m.type==='stream_delta'&&partial)partial.textContent+=m.text;
    else if(m.type==='assistant'){if(partial){partial.textContent=m.text;partial=null;}else message('assistant',m.text);}
    else if(m.type==='user')message('user',m.text);
    else if(m.type==='error'||m.type==='info')message(m.type,m.text||'');
    else if(m.type==='confirm_request'){
      const box=$('confirm');box.replaceChildren();box.hidden=false;const p=document.createElement('p');p.textContent=m.preview;box.append(p);
      for(const [label,approved]of[['Engedélyezem',true],['Elutasítom',false]]){const b=document.createElement('button');b.textContent=label;b.onclick=()=>{send({type:'confirm',id:m.id,approved});box.hidden=true;};box.append(b);}
    }
  };
}
$('pair').onsubmit=async e=>{e.preventDefault();try{const r=await fetch('/api/phone/pair',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:$('token').value.trim()})});$('token').value='';if(!r.ok)throw Error('Hibás vagy lejárt párosítási kód.');await connect();}catch(e){status(e.message,true);}};
$('send').onsubmit=e=>{e.preventDefault();const text=$('text').value.trim();if(text){send({type:'chat',text});$('text').value='';}};
$('cancel').onclick=()=>send({type:'cancel'});
$('stop').onclick=()=>{if(audio)audio.pause();};
$('logout').onclick=async()=>{await fetch('/api/phone/logout',{method:'POST'});location.reload();};
$('mic').onclick=async()=>{
  if(recorder&&recorder.state==='recording'){recorder.stop();return;}
  try{media=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}});recordChunks=[];recorder=new MediaRecorder(media);recorder.ondataavailable=e=>recordChunks.push(e.data);recorder.onstop=async()=>{
    media.getTracks().forEach(t=>t.stop());$('mic').textContent='Mikrofon';
    try{const form=new FormData();form.append('audio',new Blob(recordChunks,{type:recorder.mimeType}),'speech.webm');const r=await fetch('/api/stt',{method:'POST',body:form});const j=await r.json();if(!r.ok)throw Error(j.detail||'Nem sikerült a felismerés.');$('text').value=j.text||'';}catch(e){status(e.message,true);}
  };recorder.start();$('mic').textContent='Felvétel leállítása';}catch(e){status('Mikrofon: '+e.message,true);}
};
void connect().catch(e=>status(e.message,true));
