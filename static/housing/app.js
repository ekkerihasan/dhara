const form = document.querySelector('#review-form');
const results = document.querySelector('#results');
const submit = document.querySelector('#submit');
const file = document.querySelector('#file');
let currentReview = null;
let history = [];
function node(tag, text, cls) { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (cls) el.className = cls; return el; }
function readable(value) { return typeof value === 'object' && value !== null ? JSON.stringify(value, null, 2) : String(value); }
async function post(path, body) {
  const response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const data = await response.json(); if (!response.ok) throw new Error(data.error || 'Request failed'); return data;
}
function renderItem(value, container) {
  if (value === null || value === undefined) return;
  if (Array.isArray(value)) { value.forEach(item => renderItem(item, container)); return; }
  const card = node('article', undefined, 'card');
  if (typeof value === 'object') {
    const list = node('dl');
    Object.entries(value).forEach(([key, val]) => {
      if (val === null || val === undefined) return;
      list.append(node('dt', key.replaceAll('_', ' ')));
      const dd = node('dd');
      if (typeof val === 'string' && /^https?:\/\//i.test(val)) {
        const link = node('a', val); link.href = val; link.target = '_blank'; link.rel = 'noopener noreferrer'; dd.append(link);
      } else dd.textContent = readable(val);
      list.append(dd);
    });
    card.append(list);
  } else card.append(node('p', readable(value)));
  container.append(card);
}
function button(label, action) { const el = node('button', label); el.type = 'button'; el.addEventListener('click', action); return el; }
function addNegotiation(finding, container) {
  const box = node('div', undefined, 'negotiation');
  const label = node('label', 'Propose a revised clause');
  const area = node('textarea'); area.rows = 3; area.value = finding.proposed_revision || ''; label.append(area);
  const output = node('div', undefined, 'negotiation-result'); output.setAttribute('aria-live','polite');
  const send = button('Evaluate proposal', async () => {
    send.disabled = true; output.textContent = 'Evaluating proposal…';
    try {
      const result = await post('/api/negotiate', {review:currentReview, clause_id:finding.clause_id, offer:area.value, history});
      if (Array.isArray(result.history)) history = result.history;
      output.replaceChildren(); renderItem(Object.fromEntries(Object.entries(result).filter(([key]) => key !== 'messages')), output);
      if (result.messages) {
        const messageBox = document.querySelector('#draft-messages');
        if (messageBox) messageBox.remove();
        currentReview.messages = result.messages;
        renderMessages(result.messages);
      }
    } catch (error) { output.textContent = error.message; }
    finally { send.disabled = false; }
  });
  box.append(label, send, output); container.append(box);
}
function renderMessages(messages) {
  const target = node('section'); target.id = 'draft-messages';
  target.append(node('h2','Draft messages'));
  if (messages.translation_note) target.append(node('p',messages.translation_note,'muted'));
  if (messages.agreements_original?.length) {
    target.append(node('h3','Accepted clause wording · original language'));
    renderItem(messages.agreements_original,target);
  }
  for (const language of ['english','kannada','hindi']) {
    const message = messages[language]; if (!message) continue;
    const card = node('article', undefined, 'card'); card.append(node('h3',language[0].toUpperCase()+language.slice(1)));
    const text = typeof message === 'string' ? message : readable(message);
    card.append(node('p',text,'message'));
    if (messages[language+'_note']) card.append(node('p',readable(messages[language+'_note']),'muted'));
    const feedback = node('span',undefined,'muted');
    card.append(button('Copy message',async () => { try { await navigator.clipboard.writeText(text); feedback.textContent = 'Copied'; } catch { feedback.textContent = 'Select and copy the message text above.'; } }), feedback);
    target.append(card);
  }
  results.append(target);
}
function render(data) {
  currentReview = data; history = [];
  results.replaceChildren(node('span', (data.status || 'Review complete').replaceAll('_', ' '), 'status'));
  const actions = node('div',undefined,'actions');
  actions.append(button('Download review JSON', () => {
    const blob = new Blob([JSON.stringify({...currentReview, negotiation_history:history},null,2)],{type:'application/json'});
    const url = URL.createObjectURL(blob); const link = node('a'); link.href = url; link.download = 'dhara-review.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url),1000);
  })); results.append(actions);
  if (data.jurisdiction) {
    results.append(node('h2','Jurisdiction assessment'));
    renderItem({status:data.jurisdiction.status, reasons:data.jurisdiction.reasons, conditional_rules_enabled:data.jurisdiction.conditional_rules_enabled},results);
  }
  for (const [key,label] of [['limitations','Review limitations'],['questions','Questions to resolve']]) {
    if (data[key]?.length) { results.append(node('h2',label)); renderItem(data[key],results); }
  }
  results.append(node('h2','Review findings'));
  if (!data.findings?.length) results.append(node('p','No issues detected by the available rules. This does not establish that the agreement is legally compliant.','muted'));
  for (const finding of data.findings || []) {
    const card = node('article',undefined,'card');
    card.append(node('h3',`${finding.clause_id} · ${finding.category || 'review'}`));
    for (const [key,label] of [['original','Agreement clause'],['explanation','Why it needs attention'],['proposed_revision','Suggested revision']]) {
      if (finding[key]) card.append(node('strong',label),node('p',finding[key]));
    }
    if (finding.citations?.length) { card.append(node('strong','Supporting citations')); renderItem(finding.citations,card); }
    addNegotiation(finding,card); results.append(card);
  }
  if (data.messages) renderMessages(data.messages);
  if (data.sources?.length) { results.append(node('h2','Sources and applicability')); renderItem(data.sources,results); }
  for (const [key,label] of [['jurisdiction','Jurisdiction assessment'],['trace','Agent planning steps'],['clauses','Extracted clauses']]) {
    if (data[key]) { const detail = node('details'); detail.append(node('summary',label)); renderItem(data[key],detail); results.append(detail); }
  }
}
file.addEventListener('change', async () => {
  const selected = file.files[0]; if (!selected) return;
  if (!/\.(txt|pdf|png|jpe?g|webp)$/i.test(selected.name) || selected.size > 8 * 1024 * 1024) { results.replaceChildren(node('p','Choose a supported document smaller than 8 MB.','error')); file.value = ''; return; }
  submit.disabled = true; results.replaceChildren(node('p','Extracting text locally…'));
  try {
    const dataBase64 = await new Promise((resolve,reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(',')[1]); reader.onerror = reject; reader.readAsDataURL(selected); });
    const data = await post('/api/extract',{filename:selected.name,data_base64:dataBase64});
    document.querySelector('#document').value = data.text;
    results.replaceChildren(node('p','Text extracted. Check and correct the agreement text before selecting Review agreement.'));
  } catch (error) { results.replaceChildren(node('p',error.message || 'Document extraction failed.','error')); }
  finally { submit.disabled = false; }
});
form.addEventListener('submit', async event => {
  event.preventDefault(); submit.disabled = true; results.setAttribute('aria-busy','true'); results.replaceChildren(node('p','Reviewing your agreement…'));
  const preferences = {};
  for (const [id,key] of [['deposit','max_deposit_months'],['notice','max_notice_days'],['min-notice','min_notice_days'],['refund','max_refund_days'],['entry','min_entry_notice_hours'],['increase','max_rent_increase_percent']]) { const value = document.getElementById(id).value; if (value !== '') preferences[key] = Number(value); }
  const facts = {city:document.querySelector('#city').value, tenancy_date:document.querySelector('#tenancy-date').value, ownership_type:document.querySelector('#ownership').value, schedule_area:document.querySelector('#schedule-area').value};
  for (const [id,key] of [['rent','monthly_rent'],['age','building_age_years'],['standard-rent','standard_rent_monthly']]) { const value = document.getElementById(id).value; if (value !== '') facts[key] = Number(value); }
  const use = document.querySelector('#residential').value; if (use !== '') facts.residential = use === 'true';
  const exemptions = document.querySelector('#exemptions').value; if (exemptions !== '') facts.other_exemptions_checked = exemptions === 'true';
  try { render(await post('/api/review',{text:document.querySelector('#document').value,state:document.querySelector('#state').value,preferences,facts})); }
  catch (error) { results.replaceChildren(node('p',error.message,'error')); }
  finally { submit.disabled = false; results.setAttribute('aria-busy','false'); }
});
document.querySelector('#load-demo').addEventListener('click', () => {
  form.reset();
  document.querySelector('#document').value = '1. The security deposit is 6 months of rent.\n2. The tenant must give 90 days notice before terminating the tenancy.';
  document.querySelector('#state').value = 'Karnataka';
  results.replaceChildren(node('p','Demo agreement loaded. Review it against your preferences; jurisdiction facts remain unconfirmed.'));
  document.querySelector('#document').focus();
});
