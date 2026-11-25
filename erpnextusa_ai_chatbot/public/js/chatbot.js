(() => {
  'use strict';
  if (window.__euChatLoaded) return;
  window.__euChatLoaded = true;
  const script = document.currentScript;
  const base = (script?.dataset.apiBase || location.origin).replace(/\/$/, '');
  const title = script?.dataset.title || 'ERPNextUSA Assistant';
  const privacy = script?.dataset.privacyUrl || base + '/privacy-policy';
  const sid = crypto?.randomUUID?.() || String(Date.now());
  const css = document.createElement('style');
  css.textContent = `
  #eu-launch{position:fixed;right:22px;bottom:22px;z-index:2147483000;background:#155eef;color:#fff;border:0;border-radius:40px;padding:15px 20px;cursor:pointer;font:600 14px Arial;box-shadow:0 10px 30px #0003}
  #eu-panel{position:fixed;right:22px;bottom:80px;z-index:2147483000;width:min(390px,calc(100vw - 24px));height:min(580px,calc(100vh - 100px));background:white;border-radius:16px;box-shadow:0 18px 65px #0004;display:none;flex-direction:column;overflow:hidden;font:14px Arial;color:#172033}
  #eu-head{background:#155eef;color:white;padding:18px;display:flex;justify-content:space-between;font-weight:bold}
  #eu-head button{background:transparent;border:0;color:white;font-size:22px;cursor:pointer}
  #eu-tabs{display:flex;border-bottom:1px solid #ddd}#eu-tabs button{flex:1;padding:12px;border:0;background:#fff;cursor:pointer}#eu-tabs button[aria-selected=true]{color:#155eef;border-bottom:2px solid #155eef;font-weight:bold}
  #eu-messages{flex:1;overflow:auto;padding:14px;background:#f8fafc} .eu-msg{white-space:pre-wrap;line-height:1.45;padding:10px 12px;border-radius:12px;margin-bottom:10px;max-width:86%;background:#fff;border:1px solid #ddd}.eu-user{margin-left:auto;background:#155eef;color:white;border:0}
  #eu-chat-form{display:flex;padding:12px;gap:8px;border-top:1px solid #eee}#eu-chat-form input{flex:1;min-width:0}#eu-panel input,#eu-panel textarea{box-sizing:border-box;border:1px solid #cbd5e1;border-radius:8px;padding:11px;font:14px Arial}#eu-panel button.eu-primary{background:#155eef;color:white;border:0;border-radius:8px;padding:10px 14px;cursor:pointer}#eu-panel button:disabled{opacity:.55}
  #eu-lead{display:none;padding:16px;overflow:auto;flex:1}#eu-lead input,#eu-lead textarea{width:100%;margin-bottom:10px}#eu-lead label{display:flex;gap:8px;align-items:flex-start;font-size:12px;line-height:1.5;margin:8px 0 14px}#eu-lead label input{width:auto;margin:2px 0}#eu-lead-status{margin-top:12px}#eu-chat{display:flex;flex:1;flex-direction:column;min-height:0}
  @media(max-width:480px){#eu-panel{right:8px;bottom:75px;width:calc(100vw - 16px)}#eu-launch{right:12px;bottom:12px}}
  `;
  document.head.append(css);
  const launch = document.createElement('button');launch.id='eu-launch';launch.textContent='Chat with us';launch.type='button';launch.setAttribute('aria-label','Open chatbot');
  const panel = document.createElement('section');panel.id='eu-panel';panel.setAttribute('aria-label',title);
  panel.innerHTML=`<div id="eu-head"><span></span><button id="eu-close" aria-label="Close">×</button></div><div id="eu-tabs"><button type="button" data-tab="chat" aria-selected="true">AI Chat</button><button type="button" data-tab="lead" aria-selected="false">Contact team</button></div><div id="eu-chat"><div id="eu-messages" role="log" aria-live="polite"></div><form id="eu-chat-form"><input id="eu-input" maxlength="2000" placeholder="Ask about ERPNext..." aria-label="Message" required><button class="eu-primary" type="submit">Send</button></form></div><form id="eu-lead"><input name="name" placeholder="Your name" maxlength="140" required><input name="email" type="email" placeholder="Email address" maxlength="140" required><input name="phone" type="tel" placeholder="Phone (optional)" maxlength="40"><textarea name="message" rows="4" maxlength="2000" placeholder="How can we help?"></textarea><label><input name="consent" type="checkbox" required><span>I agree to share my details with ERPNextUSA so the team can contact me about my inquiry. See <a id="eu-privacy" target="_blank" rel="noopener noreferrer">privacy policy</a>.</span></label><button class="eu-primary" type="submit">Send inquiry</button><div id="eu-lead-status" role="status"></div></form>`;
  document.body.append(launch,panel);
  panel.querySelector('#eu-head span').textContent=title;
  panel.querySelector('#eu-privacy').href=privacy;
  const msgs=panel.querySelector('#eu-messages');
  const say=(s,who)=>{const d=document.createElement('div');d.className='eu-msg'+(who==='user'?' eu-user':'');d.textContent=s;msgs.append(d);msgs.scrollTop=msgs.scrollHeight;};
  say('Hello! Ask me about ERPNextUSA, or select Contact team to send an inquiry.');
  launch.onclick=()=>{panel.style.display='flex';launch.style.display='none';panel.querySelector('#eu-input').focus();};
  panel.querySelector('#eu-close').onclick=()=>{panel.style.display='none';launch.style.display='block';};
  panel.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{panel.querySelectorAll('[data-tab]').forEach(t=>t.setAttribute('aria-selected',String(t===b)));panel.querySelector('#eu-chat').style.display=b.dataset.tab==='chat'?'flex':'none';panel.querySelector('#eu-lead').style.display=b.dataset.tab==='lead'?'block':'none';});
  async function post(method,data){const r=await fetch(base+'/api/method/erpnextusa_ai_chatbot.api.'+method,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const j=await r.json();if(!r.ok||j.exc)throw Error('Request failed');return j.message;}
  const pageContent=()=>{const root=document.querySelector('main, article, [role="main"]');if(!root)return '';return [...root.querySelectorAll('h1, h2, h3, p, li')].map(node=>node.innerText.trim()).filter(Boolean).join('\n').slice(0,6000);};
  panel.querySelector('#eu-chat-form').onsubmit=async e=>{e.preventDefault();const form=e.currentTarget,input=form.querySelector('input'),button=form.querySelector('button'),message=input.value.trim();if(!message)return;say(message,'user');input.value='';button.disabled=true;try{const result=await post('chat',{message,session_id:sid,page:location.href,page_title:document.title,page_heading:document.querySelector('h1')?.innerText||'',page_description:document.querySelector('meta[name="description"]')?.content||'',page_content:pageContent()});say(result?.answer||'No response available.');}catch(_){say('Sorry, the assistant is unavailable. Please try again later.');}finally{button.disabled=false;input.focus();}};
  panel.querySelector('#eu-lead').onsubmit=async e=>{e.preventDefault();const f=e.currentTarget,button=f.querySelector('button[type=submit]'),status=f.querySelector('#eu-lead-status'),data=Object.fromEntries(new FormData(f).entries());if(!f.elements.consent.checked)return;data.consent=1;button.disabled=true;status.textContent='Sending...';try{await post('submit_lead',data);status.textContent='Thank you! Your inquiry has been submitted.';f.reset();}catch(_){status.textContent='Could not submit your inquiry. Please try again.';}finally{button.disabled=false;}};
})();
