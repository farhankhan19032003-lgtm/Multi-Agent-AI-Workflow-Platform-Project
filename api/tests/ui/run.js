const { JSDOM } = require('jsdom');
const fs = require('fs');
const BASE = 'http://127.0.0.1:8765';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const results = [];
const check = (name, ok, extra) => { results.push([ok, name, extra]); console.log((ok ? 'PASS ' : 'FAIL ') + name + (extra && !ok ? '  -> ' + extra : '')); };

async function waitFor(fn, ms = 8000) { const t = Date.now(); while (Date.now() - t < ms) { try { const v = fn(); if (v) return v; } catch (e) {} await sleep(50); } return null; }

(async () => {
  const html = await (await fetch(BASE + '/')).text();
  check('GET / serves the chat page', html.includes('Agent Factory') && html.includes('id="composer"'));
  check('template CSV served', (await fetch(BASE + '/templates/sales.csv')).status === 200);
  const css = await fetch(BASE + '/styles.css'); check('static css served', css.status === 200);
  check('health still routed before static mount', (await (await fetch(BASE + '/health')).json()).status === 'ok');

  const dom = new JSDOM(html, { url: BASE + '/', runScripts: 'outside-only', pretendToBeVisual: true });
  const w = dom.window;
  w.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
  w.fetch = async (u, o) => {
    o = o ? { ...o } : o;
    if (o && o.body && o.body.constructor && o.body.constructor.name === 'FormData') {
      const fd = new FormData();
      for (const [k, v] of o.body.entries()) { const buf = await new Promise((res) => { const fr = new w.FileReader(); fr.onload = () => res(fr.result); fr.readAsArrayBuffer(v); });
        fd.append(k, new Blob([buf], { type: v.type }), v.name); }
      o.body = fd;
    }
    return fetch(new URL(u, BASE), o);
  };
  w.AbortController = AbortController; w.TextDecoder = TextDecoder;
  w.HTMLElement.prototype.scrollIntoView = () => {};
  const charts = []; w.Chart = class { constructor(cv, cfg) { charts.push(cfg); } };
  w.eval(fs.readFileSync(require.resolve('marked/marked.min.js'), 'utf8'));
  w.eval(fs.readFileSync(require.resolve('dompurify/dist/purify.min.js'), 'utf8'));
  check('markdown libs load', !!w.marked && !!w.DOMPurify);
  const errors = []; w.addEventListener('error', (e) => errors.push(e.message));
  w.eval(fs.readFileSync(require('path').join(__dirname, '../../web/app.js'), 'utf8'));
  await sleep(50);
  w.document.dispatchEvent(new w.Event('DOMContentLoaded'));
  const $ = (s) => w.document.querySelector(s); const $$ = (s) => [...w.document.querySelectorAll(s)];

  const ready = await waitFor(() => !$('#app').classList.contains('hidden') && $('#dropzone'));
  check('app shown without login in local mode', !!ready);
  await waitFor(() => $('#dataset-badge').textContent && /messages today/.test($('#usage-text').textContent));
  check('empty workspace asks for data upload', /Upload your data/.test($('#empty-title').textContent) && $('#dataset-badge').textContent === 'No data yet', $('#dataset-badge').textContent);
  check('template links present', $$('.tpl a').length === 6);
  check('usage meter shown', /messages today/.test($('#usage-text').textContent), $('#usage-text').textContent);

  // upload through the attach input
  const csv = 'order_id,region,amount,order_date\n001,North,"₹1,200",05/01/2024\n002,South,"₹800",15/01/2024\n003,North,"₹2,000",20/02/2024\n';
  const file = new w.File([csv], 'sales.csv', { type: 'text/csv' });
  const inp = $('#file-input'); Object.defineProperty(inp, 'files', { value: [file], configurable: true });
  inp.dispatchEvent(new w.Event('change'));
  check('file chip appears in composer tray', !!(await waitFor(() => $$('#attach-tray .fchip').length === 1)));
  check('upload finished, library count = 1', !!(await waitFor(() => $('#lib-count').textContent === '1' && !$('#attach-tray .spin'))), $('#lib-count').textContent);
  check('badge shows 1 table', /1 table/.test($('#dataset-badge').textContent), $('#dataset-badge').textContent);
  check('send enabled with only an attachment', $('#send').disabled === false);

  // agent picker
  $('#agent-btn').click();
  const opts = $$('.agent-opt').length;
  check('picker lists 2 modes + 70+ agents', opts >= 72, opts);
  $('#agent-search').value = 'churn'; $('#agent-search').dispatchEvent(new w.Event('input'));
  check('picker search filters', $$('.agent-opt').length > 0 && $$('.agent-opt').length < 12, $$('.agent-opt').length);
  $('#agent-search').value = ''; $('#agent-search').dispatchEvent(new w.Event('input'));
  $('#agent-btn').click();

  // send a message with the attachment (auto mode)
  const input = $('#input'); input.value = 'total sales by region'; input.dispatchEvent(new w.Event('input'));
  $('#composer').dispatchEvent(new w.Event('submit', { cancelable: true }));
  const done = await waitFor(() => $('.msg.assistant .actions button'), 10000);
  check('assistant answer finished (actions shown)', !!done);
  check('user bubble + file chip shown', $('.msg.user .bubble').textContent === 'total sales by region' && /sales\.csv/.test($('.msg.user .ufiles').textContent));
  check('tray cleared after send', $$('#attach-tray .fchip').length === 0);
  check('answer text streamed + rendered', /North leads/.test($('.msg.assistant .md').textContent), $('.msg.assistant .md').textContent);
  check('tag says Quick answer', /Quick answer/.test($('.agent-tag').textContent), $('.agent-tag').textContent);
  check('2 tool rows (SQL + chart)', $$('.tool').length === 2, $$('.tool').length);
  check('SQL text visible in tool row', /FROM sales/.test($('.tool .sql').textContent));
  check('result table rendered (North/South)', $$('.tool .mini tbody tr').length === 2, $$('.tool .mini tbody tr').length);
  check('CSV + Excel download buttons', $$('.tool .dl button').length === 2);
  check('chart drawn with bar type', charts.length === 1 && charts[0].type === 'bar');
  check('title event renamed the chat', !!(await waitFor(() => /Sales Summary/.test($('.chat-item .title').textContent))), $('.chat-item .title').textContent);
  check('usage meter updated', !!(await waitFor(() => /^1 \/ /.test($('#usage-text').textContent))), $('#usage-text').textContent);

  // feedback
  const up = $$('.msg.assistant .actions button')[1]; up.click();
  check('thumbs up saved', !!(await waitFor(() => up.classList.contains('on'))));

  // edit the user message
  $('.msg.user .uacts button:nth-child(2)').click();
  const ta = $('.msg.user .editbox textarea'); ta.value = 'sales by month';
  $('.msg.user .editbox .btn-primary').click();
  const edited = await waitFor(() => $$('.msg.user').length === 1 && $('.msg.user .bubble').textContent === 'sales by month' && $('.msg.assistant .actions button'), 10000);
  check('edit & resend replaces the exchange', !!edited && $$('.msg.assistant').length === 1);

  // reopen from history
  $('#btn-new').click();
  check('new chat shows empty state with suggestions', $$('.msg').length === 0 && !$('#empty').classList.contains('hidden'));
  check('dynamic suggestions rendered', !!(await waitFor(() => $$('.starter').length >= 3)), $$('.starter').length);
  $('.chat-item .title').click();
  const reopened = await waitFor(() => $$('.msg.assistant').length === 1 && /North leads/.test($('.msg.assistant .md').textContent));
  check('history reload restores answer', !!reopened);
  check('history reload restores tools + chart', $$('.tool').length === 2 && charts.length >= 2);
  check('feedback state restored or neutral', $$('.msg.assistant .actions button').length >= 4);

  // team mode
  $('#agent-btn').click(); $$('.agent-opt').find((b) => /Team/.test(b.textContent)).click();
  check('agent button shows Team', $('#agent-label').textContent === 'Team');
  input.value = 'Full analysis of sales'; input.dispatchEvent(new w.Event('input'));
  $('#composer').dispatchEvent(new w.Event('submit', { cancelable: true }));
  const teamDone = await waitFor(() => $$('.msg.assistant').length === 2 && $$('.msg.assistant')[1].querySelector('.actions button'), 15000);
  check('team answer finished', !!teamDone);
  const last = $$('.msg.assistant')[1];
  check('team answer has combined text', last && /Combined answer/.test(last.querySelector('.md').textContent));
  check('team tag + finished-agent ticks', last && /Team/.test(last.querySelector('.agent-tag').textContent) && last.querySelectorAll('.tdone').length >= 2);

  // regenerate
  const before = $$('.msg.assistant').length;
  last.querySelectorAll('.actions button')[3].click();
  const regen = await waitFor(() => $$('.msg.assistant').length === before && $$('.msg.assistant')[before - 1].querySelector('.actions button'), 15000);
  check('regenerate replaces the last answer', !!regen && $$('.msg.user').length === 2, `${$$('.msg.user').length} user msgs`);

  // settings modal
  $('#btn-settings').click();
  check('settings modal opens', !$('#modal').classList.contains('hidden'));
  const about = await waitFor(() => $('#tab-body textarea'));
  about.value = 'I run a shop in Pune'; $('#tab-body .btn-primary').click();
  await sleep(300);
  check('instructions saved', (await (await fetch(BASE + '/v1/settings')).json()).about === 'I run a shop in Pune');
  $$('#tabs button').find((b) => b.dataset.tab === 'data').click();
  check('library tab lists the uploaded table', !!(await waitFor(() => /sales/.test($('#tab-body .frow').textContent))));
  $$('#tab-body .frow button')[0].click();
  check('preview shows rows', !!(await waitFor(() => $$('#tab-body .fprev tbody tr').length === 3)));
  $$('#tabs button').find((b) => b.dataset.tab === 'plan').click();
  check('plan tab shows usage', !!(await waitFor(() => /messages used today/.test($('#tab-body').textContent))));
  $$('#tabs button').find((b) => b.dataset.tab === 'workspace').click();
  check('workspace tab explains local mode', !!(await waitFor(() => /single-user local mode/.test($('#tab-body').textContent))));
  $('#modal-close').click();

  // sidebar rename/delete via prompt/confirm
  w.prompt = () => 'Renamed chat'; w.confirm = () => true; w.alert = (m) => errors.push('alert:' + m);
  $('.chat-item .acts button').click();
  check('rename updates sidebar', !!(await waitFor(() => /Renamed chat/.test($('.chat-item .title').textContent))));
  $$('.chat-item .acts button')[1].click();
  check('delete removes chat and resets view', !!(await waitFor(() => $$('.chat-item').length === 0 && $$('.msg').length === 0)), $$('.chat-item').length + ' items, ' + $$('.msg').length + ' msgs, ' + errors.join('|'));

  // theme
  const t0 = w.document.documentElement.dataset.theme; $('#btn-theme').click();
  check('theme toggles', w.document.documentElement.dataset.theme !== t0);
  check('no uncaught JS errors', errors.length === 0, errors.join(' | '));

  const failed = results.filter((r) => !r[0]).length;
  console.log(`\n${results.length - failed}/${results.length} UI checks passed`);
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.error('HARNESS ERROR', e); process.exit(2); });
