/* Agent Factory chat UI v3: plain JS, no build step. */
(function () {
  'use strict';

  // ------------------------------------------------------------------ icons
  var svg = function (p, s) {
    return '<svg width="' + (s || 20) + '" height="' + (s || 20) + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + p + '</svg>';
  };
  var ICON = {
    edit: svg('<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z"/>'),
    sidebar: svg('<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/>'),
    send: svg('<path d="M12 19V5"/><path d="M5 12l7-7 7 7"/>', 18),
    stop: '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="5" y="5" width="14" height="14" rx="3"/></svg>',
    copy: svg('<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 012-2h9"/>', 17),
    check: svg('<path d="M5 12l5 5 9-10"/>', 17),
    refresh: svg('<path d="M20 11a8 8 0 00-14.9-3M4 5v4h4"/><path d="M4 13a8 8 0 0014.9 3M20 19v-4h-4"/>', 17),
    chev: svg('<path d="M6 9l6 6 6-6"/>', 16),
    sun: svg('<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'),
    moon: svg('<path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z"/>'),
    trash: svg('<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>', 16),
    pencil: svg('<path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z"/>', 16),
    out: svg('<path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>', 18),
    check2: svg('<path d="M5 12l5 5 9-10"/>', 16),
    clip: svg('<path d="M21 11.5l-8.6 8.6a5 5 0 01-7-7l9-9a3.3 3.3 0 014.7 4.7l-9 9a1.7 1.7 0 01-2.4-2.4l8.3-8.3"/>'),
    mic: svg('<rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0014 0M12 18v3"/>'),
    lib: svg('<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>'),
    gear: svg('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1.1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3H9a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8V9a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z"/>'),
    upload: svg('<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v3a2 2 0 002 2h12a2 2 0 002-2v-3"/>', 26),
    down: svg('<path d="M12 4v12M7 11l5 5 5-5"/><path d="M4 20h16"/>', 16),
    up: svg('<path d="M7 11v9H4v-9zM7 11l4-8a2 2 0 012 2v4h6a2 2 0 012 2.3l-1 6A2 2 0 0118 20H7"/>', 16),
    dn: svg('<path d="M17 13V4h3v9zM17 13l-4 8a2 2 0 01-2-2v-4H5a2 2 0 01-2-2.3l1-6A2 2 0 016 4h11"/>', 16),
    file: svg('<path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8z"/><path d="M14 3v5h5"/>', 16),
    x: svg('<path d="M6 6l12 12M18 6L6 18"/>', 14)
  };
  var LOGO = '<svg viewBox="0 0 24 24" width="100%" height="100%" aria-hidden="true"><path d="M12 2l8.66 5v10L12 22l-8.66-5V7z" fill="#6366f1"/><circle cx="12" cy="12" r="3.2" fill="#fff"/></svg>';

  var TOOL_LABEL = {
    run_sql: 'Ran SQL query', make_chart: 'Built a chart', list_tables: 'Listed your tables', describe_table: 'Inspected a table',
    profile_table: 'Profiled the data', forecast_series: 'Forecast', detect_anomalies: 'Looked for anomalies',
    correlations: 'Checked correlations', search_documents: 'Searched your documents', web_search: 'Searched the web'
  };
  var PALETTE = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#a855f7', '#84cc16', '#f97316'];

  // ------------------------------------------------------------------ state
  var S = {
    token: null, email: null, sb: null, config: {}, me: null,
    agents: [], categories: [], files: [], conversations: [],
    currentId: null, agentChoice: 'auto', streaming: false, abort: null,
    lastUserEl: null, attachments: [], suggestions: [], lastUserId: null
  };

  var $ = function (id) { return document.getElementById(id); };
  var h = function (tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]; }); };
  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } }
  };
  var fmtBytes = function (n) { n = Number(n) || 0; return n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1024)) + ' KB'; };

  // -------------------------------------------------------------------- api
  function headers(json) {
    var o = {};
    if (json !== false) o['Content-Type'] = 'application/json';
    if (S.token) o.Authorization = 'Bearer ' + S.token;
    return o;
  }
  function errText(txt) {
    try { var j = JSON.parse(txt); var d = j.detail; if (typeof d === 'string') return d; if (d && d.message) return d.message; if (Array.isArray(d)) return d.map(function (x) { return x.msg; }).join('; '); } catch (e) { /* plain text */ }
    return String(txt).slice(0, 300);
  }
  async function api(path, opts) {
    opts = opts || {};
    var r = await fetch(path, { method: opts.method || 'GET', headers: headers(), body: opts.body ? JSON.stringify(opts.body) : undefined });
    if (r.status === 401) { showLogin('Please sign in again.'); throw new Error('unauthorized'); }
    if (!r.ok) throw new Error(errText(await r.text()));
    return r.json();
  }
  var toastTimer;
  function toast(msg, bad) {
    var t = $('toast'); t.textContent = msg; t.classList.toggle('bad', !!bad); t.classList.remove('hidden');
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { t.classList.add('hidden'); }, 4500);
  }

  // --------------------------------------------------------------- bootstrap
  async function init() {
    $('login-logo').innerHTML = LOGO; $('empty-logo').innerHTML = LOGO; $('sb-logo').innerHTML = LOGO;
    $('ico-edit').innerHTML = ICON.edit; $('btn-collapse').innerHTML = ICON.sidebar; $('btn-menu').innerHTML = ICON.sidebar;
    $('ico-chev').innerHTML = ICON.chev; $('btn-signout').innerHTML = ICON.out; $('send').innerHTML = ICON.send;
    $('ico-lib').innerHTML = ICON.lib; $('ico-set').innerHTML = ICON.gear; $('ico-upload').innerHTML = ICON.upload;
    $('btn-attach').innerHTML = ICON.clip; $('btn-mic').innerHTML = ICON.mic; $('btn-export').innerHTML = ICON.down;
    applyTheme(document.documentElement.dataset.theme);
    wireUi();

    try { S.config = await (await fetch('/v1/config')).json(); }
    catch (e) { showLogin('Cannot reach the server.', true); return; }

    if (S.config.dev_no_auth) return start();

    if (!window.supabase || !S.config.supabase_url || !S.config.supabase_anon_key) {
      return showLogin('Login is not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY on the server.', true);
    }
    var hash = location.hash || '', recovery = /type=recovery/.test(hash);
    var linkErr = /error_code=|error=/.test(hash) ? 'That link is invalid or has expired. Request a new one.' : '';
    // The default navigator.locks lock can hang getSession() when another tab/page holds it, which left the page blank.
    S.sb = window.supabase.createClient(S.config.supabase_url, S.config.supabase_anon_key, {
      auth: { lock: function (_name, _timeout, fn) { return fn(); } },
    });
    S.sb.auth.onAuthStateChange(function (ev, session) {
      S.token = session ? session.access_token : null;
      if (ev === 'PASSWORD_RECOVERY') { recovery = true; A.view = 'newpw'; setTimeout(function () { showLogin(); }, 0); }
    });
    var res = await Promise.race([S.sb.auth.getSession(), new Promise(function (r) { setTimeout(function () { r(null); }, 5000); })]);
    if (!res) return showLogin('The sign-in service is slow to respond. Check your connection, then reload.', true);
    var session = res.data && res.data.session;
    if (linkErr) { history.replaceState(null, '', location.pathname + location.search); A.view = 'reset'; return showLogin(linkErr, true); }
    if (session && recovery) { A.view = 'newpw'; return showLogin(); }
    if (session) {
      S.token = session.access_token; S.email = session.user.email;
      if (location.hash) history.replaceState(null, '', location.pathname + location.search);
      start();
    } else showLogin();
  }

  // -------------------------------------------------------------------- auth
  // ChatGPT-style flow: email -> password. Views: login, signup, reset, sent, newpw.
  var A = { view: 'login', step: 1, email: '', sentKind: 'confirm', timer: null };
  var EYE = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>';
  var EYE_OFF = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17.9 17.9A10.1 10.1 0 0 1 12 19c-6.4 0-10-7-10-7a17.8 17.8 0 0 1 4.1-5M9.9 5.2A9.5 9.5 0 0 1 12 5c6.4 0 10 7 10 7a17.7 17.7 0 0 1-2.2 3.2M1 1l22 22M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>';
  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  function bootDone() { var b = document.getElementById('boot'); if (b) b.remove(); }
  function showLogin(msg, bad) {
    bootDone();
    $('app').classList.add('hidden'); $('login').classList.remove('hidden');
    authRender(); setLoginMsg(msg || '', bad);
  }
  function setLoginMsg(msg, bad) { var m = $('login-msg'); m.textContent = msg || ''; m.classList.toggle('bad', !!bad); }
  function show(id, on) { $(id).classList.toggle('hidden', !on); }

  function authRender() {
    var v = A.view, st = A.step, flow = v === 'login' || v === 'signup', pwStep = flow && st === 2;
    var title = { login: 'Welcome back', signup: 'Create an account', reset: 'Reset your password', sent: 'Check your inbox', newpw: 'Choose a new password' }[v];
    var sub = '';
    if (v === 'reset') sub = 'Enter your email address and we will send you a link to reset your password.';
    if (v === 'sent') sub = A.sentKind === 'reset'
      ? 'We sent a password reset link to ' + A.email + '. Open it to choose a new password.'
      : 'We sent a verification link to ' + A.email + '. Open it to finish creating your account, then log in.';
    if (v === 'newpw') sub = 'Use at least 8 characters.';
    $('auth-title').textContent = title; $('auth-sub').textContent = sub; show('auth-sub', !!sub);

    show('login-email', (flow && st === 1) || v === 'reset');
    show('auth-email-chip', pwStep); $('auth-email-text').textContent = A.email;
    show('pw-wrap', pwStep || v === 'newpw');
    show('pw-wrap2', v === 'newpw');
    show('pw-rules', (v === 'signup' && st === 2) || v === 'newpw');
    show('auth-forgot', v === 'login' && st === 2);
    show('btn-signin', v !== 'sent'); show('btn-resend', v === 'sent');
    show('auth-switch', flow); show('auth-back', v === 'reset' || v === 'sent');
    show('auth-social', flow && st === 1);
    $('auth-switch').firstChild.textContent = v === 'login' ? "Don't have an account? " : 'Already have an account? ';
    $('auth-switch-link').textContent = v === 'login' ? 'Sign up' : 'Log in';
    $('btn-signin').textContent = { login: st === 1 ? 'Continue' : 'Log in', signup: st === 1 ? 'Continue' : 'Create account', reset: 'Send reset link', newpw: 'Update password' }[v] || 'Continue';
    $('login-password').autocomplete = v === 'login' ? 'current-password' : 'new-password';
    $('login-password2').value = ''; setLoginMsg('');
    if (v === 'reset' || (flow && st === 1)) $('login-email').value = A.email;
    if (!pwStep && v !== 'newpw') $('login-password').value = '';
    $('login-password').type = 'password'; $('login-password2').type = 'password'; $('pw-toggle').innerHTML = EYE;
    rulesUpdate();
    var f = pwStep || v === 'newpw' ? 'login-password' : (v === 'sent' ? 'btn-resend' : 'login-email');
    setTimeout(function () { var el = $(f); if (el && el.offsetParent !== null) el.focus(); }, 0);
  }
  function rulesUpdate() { $('rule-len').classList.toggle('ok', $('login-password').value.length >= 8); }
  function authBusy(on) { $('btn-signin').disabled = on; }
  function authError(e) {
    var m = (e && e.message) || '', c = (e && e.code) || '';
    if (c === 'invalid_credentials' || /invalid login credentials/i.test(m)) return 'Incorrect email or password.';
    if (c === 'email_not_confirmed' || /not confirmed/i.test(m)) return 'Your email is not verified yet. Check your inbox for the verification link.';
    if (c === 'over_email_send_rate_limit' || c === 'over_request_rate_limit' || (e && e.status === 429) || /rate limit/i.test(m)) return 'Too many attempts. Please wait a few minutes and try again.';
    if (c === 'user_already_exists' || /already registered/i.test(m)) return 'An account with this email already exists. Log in instead.';
    if (c === 'weak_password') return m || 'That password is too weak. Try a longer one.';
    if (/failed to fetch|network/i.test(m)) return 'Cannot reach the server. Check your connection and try again.';
    if (c === 'signup_disabled' || /signups not allowed/i.test(m)) return 'Sign-ups are currently disabled.';
    return m || 'Something went wrong. Please try again.';
  }
  function finishLogin(session) {
    S.token = session.access_token; S.email = session.user.email;
    if (location.hash) history.replaceState(null, '', location.pathname + location.search);
    start();
  }
  function cooldown(secs) {
    var b = $('btn-resend'), left = secs; clearInterval(A.timer);
    b.disabled = true; b.textContent = 'Resend email (' + left + 's)';
    A.timer = setInterval(function () {
      left--;
      if (left <= 0) { clearInterval(A.timer); b.disabled = false; b.textContent = 'Resend email'; }
      else b.textContent = 'Resend email (' + left + 's)';
    }, 1000);
  }

  async function authSubmit() {
    var v = A.view;
    if (!S.sb) return setLoginMsg('Login is not configured on the server.', true);
    if (v === 'login' || v === 'signup') {
      if (A.step === 1) {
        var email = $('login-email').value.trim();
        if (!EMAIL_RE.test(email)) return setLoginMsg('Email is not valid.', true);
        A.email = email; A.step = 2; return authRender();
      }
      var pw = $('login-password').value;
      if (!pw) return setLoginMsg('Enter your password.', true);
      if (v === 'signup' && pw.length < 8) return setLoginMsg('Password must be at least 8 characters.', true);
      authBusy(true); setLoginMsg('');
      try {
        if (v === 'login') {
          var r = await S.sb.auth.signInWithPassword({ email: A.email, password: pw });
          if (r.error) throw r.error;
          finishLogin(r.data.session);
        } else {
          var s = await S.sb.auth.signUp({ email: A.email, password: pw, options: { emailRedirectTo: location.origin } });
          if (s.error) throw s.error;
          if (s.data.session) return finishLogin(s.data.session);
          if (s.data.user && s.data.user.identities && s.data.user.identities.length === 0) {
            A.view = 'login'; A.step = 2; authRender();
            return setLoginMsg('You already have an account with this email. Enter your password to log in.');
          }
          A.view = 'sent'; A.sentKind = 'confirm'; authRender(); cooldown(30);
        }
      } catch (e) {
        if (e && (e.code === 'email_not_confirmed' || /not confirmed/i.test(e.message || ''))) {
          A.view = 'sent'; A.sentKind = 'confirm'; authRender(); setLoginMsg(authError(e), true); cooldown(5);
        } else setLoginMsg(authError(e), true);
      } finally { authBusy(false); }
      return;
    }
    if (v === 'reset') {
      var em = $('login-email').value.trim();
      if (!EMAIL_RE.test(em)) return setLoginMsg('Email is not valid.', true);
      A.email = em; authBusy(true);
      try {
        var rr = await S.sb.auth.resetPasswordForEmail(em, { redirectTo: location.origin });
        if (rr.error) throw rr.error;
        A.view = 'sent'; A.sentKind = 'reset'; authRender(); cooldown(30);
      } catch (e2) { setLoginMsg(authError(e2), true); }
      finally { authBusy(false); }
      return;
    }
    if (v === 'newpw') {
      var p1 = $('login-password').value, p2 = $('login-password2').value;
      if (p1.length < 8) return setLoginMsg('Password must be at least 8 characters.', true);
      if (p1 !== p2) return setLoginMsg('Passwords do not match.', true);
      authBusy(true);
      try {
        var u = await S.sb.auth.updateUser({ password: p1 });
        if (u.error) throw u.error;
        var cur = await S.sb.auth.getSession();
        if (cur.data.session) finishLogin(cur.data.session);
        else { A.view = 'login'; A.step = 1; authRender(); setLoginMsg('Password updated. Log in with your new password.'); }
      } catch (e3) { setLoginMsg(authError(e3), true); }
      finally { authBusy(false); }
    }
  }

  async function authResend() {
    $('btn-resend').disabled = true;
    try {
      var r = A.sentKind === 'reset'
        ? await S.sb.auth.resetPasswordForEmail(A.email, { redirectTo: location.origin })
        : await S.sb.auth.resend({ type: 'signup', email: A.email, options: { emailRedirectTo: location.origin } });
      if (r.error) throw r.error;
      setLoginMsg('Email sent again. Check your inbox (and spam folder).'); cooldown(30);
    } catch (e) { setLoginMsg(authError(e), true); $('btn-resend').disabled = false; }
  }

  // Social sign-in. `provider` is the Supabase provider id.
  var SOCIAL = { google: ['btn-google', 'Google'], github: ['btn-github', 'GitHub'] };
  function unlockSocial() { Object.keys(SOCIAL).forEach(function (k) { $(SOCIAL[k][0]).disabled = false; }); }
  async function authSocial(provider) {
    var label = SOCIAL[provider][1];
    if (!S.sb) return setLoginMsg('Login is not configured on the server.', true);
    var btns = Object.keys(SOCIAL).map(function (k) { return $(SOCIAL[k][0]); });
    function lock(on) { btns.forEach(function (b) { b.disabled = on; }); }
    lock(true); setLoginMsg('');
    try {
      // Ask Supabase first, so a disabled provider gives a clear message instead of a raw JSON error page.
      var cfg = await (await fetch(S.config.supabase_url + '/auth/v1/settings', { headers: { apikey: S.config.supabase_anon_key } })).json();
      if (!cfg.external || !cfg.external[provider]) { lock(false); return setLoginMsg(label + ' sign-in is not enabled yet. Use another option for now.', true); }
      var r = await S.sb.auth.signInWithOAuth({ provider: provider, options: { redirectTo: location.origin } });
      if (r.error) throw r.error;
    } catch (e) { lock(false); setLoginMsg(authError(e), true); }
  }

  function wireAuth() {
    window.addEventListener('pageshow', function (e) { if (e.persisted) unlockSocial(); });
    Object.keys(SOCIAL).forEach(function (k) { $(SOCIAL[k][0]).onclick = function () { authSocial(k); }; });
    $('login-form').onsubmit = function (e) { e.preventDefault(); authSubmit(); };
    $('btn-resend').onclick = authResend;
    $('pw-toggle').onclick = function () {
      var i = $('login-password'), reveal = i.type === 'password';
      i.type = reveal ? 'text' : 'password'; $('login-password2').type = i.type;
      this.innerHTML = reveal ? EYE_OFF : EYE; this.setAttribute('aria-label', reveal ? 'Hide password' : 'Show password');
    };
    $('login-password').oninput = rulesUpdate;
    $('auth-edit').onclick = function () { A.step = 1; authRender(); };
    $('auth-forgot').onclick = function (e) { e.preventDefault(); A.view = 'reset'; authRender(); };
    $('auth-switch-link').onclick = function (e) {
      e.preventDefault(); var typed = $('login-email').value.trim(); if (typed) A.email = typed;
      A.view = A.view === 'login' ? 'signup' : 'login'; A.step = 1; authRender();
    };
    $('auth-back-link').onclick = function (e) { e.preventDefault(); clearInterval(A.timer); A.view = 'login'; A.step = 1; authRender(); };
  }

  async function start() {
    bootDone();
    $('login').classList.add('hidden'); $('app').classList.remove('hidden');
    var saved = store.get('af-agent'); if (saved) S.agentChoice = saved;
    try {
      var join = new URLSearchParams(location.search).get('join');
      if (join) {
        try { var j = await api('/v1/workspace/join', { method: 'POST', body: { token: join } }); toast('Joined workspace ' + ((j.tenant && j.tenant.name) || '')); }
        catch (e) { toast(e.message, true); }
        history.replaceState(null, '', '/');
      }
      var a = await api('/v1/agents'); S.agents = a.agents; S.categories = a.categories;
    } catch (e) { return; }
    if (!S.agents.some(function (x) { return x.id === S.agentChoice; }) && S.agentChoice !== 'auto' && S.agentChoice !== 'team') S.agentChoice = 'auto';
    renderAgentButton(); renderAgentList('');
    await Promise.all([refreshMe(), refreshFiles(), refreshConversations()]);
    await renderEmpty();
    $('btn-signout').classList.toggle('hidden', !S.sb);
    $('btn-mic').classList.toggle('hidden', !(window.SpeechRecognition || window.webkitSpeechRecognition));
    $('input').focus();
  }

  async function refreshMe() {
    try {
      S.me = await api('/v1/me');
      var email = S.me.email || (S.me.mode === 'local' ? 'Local workspace' : 'You');
      $('user-email').textContent = email; $('user-avatar').textContent = (email[0] || 'U').toUpperCase();
      var u = S.me.usage; $('usage-mini').classList.remove('hidden');
      $('usage-text').textContent = u.used + ' / ' + u.limit + ' messages today · ' + (u.pro ? 'Pro' : 'Free');
      $('usage-bar').style.width = Math.min(100, Math.round(100 * u.used / Math.max(1, u.limit))) + '%';
    } catch (e) { /* ignore */ }
  }
  async function refreshFiles() {
    try { S.files = await api('/v1/files'); } catch (e) { S.files = []; }
    var tables = S.files.filter(function (f) { return f.kind === 'table'; }).length;
    $('lib-count').textContent = S.files.length ? String(S.files.length) : '';
    var b = $('dataset-badge');
    if (S.files.length) { b.textContent = tables + (tables === 1 ? ' table' : ' tables') + ' · ' + (S.files.length - tables) + ' docs'; b.classList.remove('warn'); }
    else { b.textContent = 'No data yet'; b.classList.add('warn'); }
  }

  // ------------------------------------------------------------------- theme
  function applyTheme(t) {
    document.documentElement.dataset.theme = t; store.set('af-theme', t);
    $('ico-theme').innerHTML = t === 'dark' ? ICON.sun : ICON.moon;
    $('theme-label').textContent = t === 'dark' ? 'Light mode' : 'Dark mode';
  }

  // -------------------------------------------------------- UI event wiring
  function wireUi() {
    $('btn-theme').onclick = function () { applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'); };
    $('btn-new').onclick = newChat;
    $('btn-collapse').onclick = function () { $('app').classList.add('collapsed'); };
    $('btn-menu').onclick = function () {
      var app = $('app');
      if (window.matchMedia('(max-width: 820px)').matches) app.classList.add('sb-open'); else app.classList.remove('collapsed');
    };
    $('scrim').onclick = function () { $('app').classList.remove('sb-open'); };
    $('chat-search').oninput = renderChatList;
    $('btn-signout').onclick = async function () { if (S.sb) await S.sb.auth.signOut(); S.token = null; location.reload(); };
    wireAuth();

    var input = $('input');
    input.addEventListener('input', function () {
      input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 200) + 'px'; updateSend();
    });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); if (!S.streaming) submit(); }
    });
    input.addEventListener('paste', function (e) {
      var items = (e.clipboardData && e.clipboardData.files) || [];
      if (items.length) { e.preventDefault(); handleFiles(items); }
    });
    $('composer').onsubmit = function (e) { e.preventDefault(); if (S.streaming) stop(); else submit(); };

    $('btn-attach').onclick = function () { $('file-input').click(); };
    $('file-input').onchange = function () { handleFiles(this.files); this.value = ''; };
    $('dropzone').onclick = function () { $('file-input').click(); };
    $('dropzone').onkeydown = function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); $('file-input').click(); } };
    $('btn-samples').onclick = installSamples;
    $('btn-library').onclick = function () { openModal('data'); };
    $('btn-settings').onclick = function () { openModal('general'); };
    $('btn-export').onclick = exportChat;
    $('btn-mic').onclick = toggleMic;
    $('modal-close').onclick = closeModal;
    $('modal').onclick = function (e) { if (e.target === $('modal')) closeModal(); };
    Array.prototype.forEach.call($('tabs').children, function (b) { b.onclick = function () { openModal(b.dataset.tab); }; });

    var dragDepth = 0;
    document.addEventListener('dragenter', function (e) { if (hasFiles(e)) { dragDepth++; $('drop-overlay').classList.remove('hidden'); } });
    document.addEventListener('dragleave', function (e) { if (hasFiles(e) && --dragDepth <= 0) { dragDepth = 0; $('drop-overlay').classList.add('hidden'); } });
    document.addEventListener('dragover', function (e) { if (hasFiles(e)) e.preventDefault(); });
    document.addEventListener('drop', function (e) {
      if (!hasFiles(e)) return; e.preventDefault(); dragDepth = 0; $('drop-overlay').classList.add('hidden'); handleFiles(e.dataTransfer.files);
    });

    $('agent-btn').onclick = function (e) { e.stopPropagation(); togglePopover(); };
    $('agent-search').oninput = function () { renderAgentList(this.value); };
    $('agent-pop').onclick = function (e) { e.stopPropagation(); };
    document.addEventListener('click', function () { togglePopover(false); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { togglePopover(false); closeModal(); $('app').classList.remove('sb-open'); }
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'o' || e.key === 'O')) { e.preventDefault(); newChat(); }
    });
  }
  function hasFiles(e) { var t = e.dataTransfer && e.dataTransfer.types; return !!t && Array.prototype.indexOf.call(t, 'Files') >= 0; }

  // ------------------------------------------------------------ agent picker
  function agentInfo(id) {
    if (id === 'auto') return { icon: '🪄', name: 'Auto', desc: 'Quick single agent for simple questions, a team for complex ones' };
    if (id === 'team') return { icon: '🧑‍🤝‍🧑', name: 'Team', desc: 'Up to 4 agents work in parallel, then one answer' };
    var a = S.agents.find(function (x) { return x.id === id; });
    return a ? { icon: a.icon, name: a.name, desc: a.description } : { icon: '🪄', name: 'Auto', desc: '' };
  }
  function renderAgentButton() { var i = agentInfo(S.agentChoice); $('agent-icon').textContent = i.icon; $('agent-label').textContent = i.name; }
  function togglePopover(force) {
    var pop = $('agent-pop'), open = force === undefined ? pop.classList.contains('hidden') : force;
    pop.classList.toggle('hidden', !open); $('agent-btn').setAttribute('aria-expanded', String(open));
    if (open) { $('agent-search').value = ''; renderAgentList(''); setTimeout(function () { $('agent-search').focus(); }, 0); }
  }
  function agentOption(id, icon, name, desc) {
    var b = h('button', 'agent-opt' + (S.agentChoice === id ? ' sel' : ''));
    b.type = 'button'; b.setAttribute('role', 'option');
    b.innerHTML = '<span class="ai">' + icon + '</span><span><div class="an">' + esc(name) + '</div><div class="ad">' + esc(desc) + '</div></span>' + (S.agentChoice === id ? '<span class="ck">' + ICON.check2 + '</span>' : '');
    b.onclick = function () { S.agentChoice = id; store.set('af-agent', id); renderAgentButton(); togglePopover(false); renderEmpty(); };
    return b;
  }
  function renderAgentList(q) {
    var box = $('agent-list'); box.innerHTML = ''; q = (q || '').toLowerCase().trim();
    var match = function (t) { return !q || t.toLowerCase().indexOf(q) >= 0; };
    var special = [['auto', '🪄', 'Auto', agentInfo('auto').desc], ['team', '🧑‍🤝‍🧑', 'Team', agentInfo('team').desc]];
    var shown = special.filter(function (s) { return match(s[2] + ' ' + s[3]); });
    if (shown.length) { box.appendChild(h('div', 'cat-title', 'MODES')); shown.forEach(function (s) { box.appendChild(agentOption(s[0], s[1], s[2], s[3])); }); }
    S.categories.forEach(function (cat) {
      var list = S.agents.filter(function (a) { return a.category === cat && match(a.name + ' ' + a.description + ' ' + a.category); });
      if (!list.length) return;
      box.appendChild(h('div', 'cat-title', esc(cat.toUpperCase())));
      list.forEach(function (a) { box.appendChild(agentOption(a.id, a.icon, a.name, a.description)); });
    });
    if (!box.children.length) box.appendChild(h('div', 'cat-title', 'No agents found'));
  }

  // -------------------------------------------------------------- empty state
  async function renderEmpty() {
    var box = $('starters'); box.innerHTML = '';
    var hasData = S.files.length > 0;
    $('dropzone').classList.toggle('compact', hasData);
    $('empty-title').textContent = hasData ? 'What do you want to know about your data?' : 'Upload your data to get started';
    var pool = [];
    if (S.agentChoice !== 'auto' && S.agentChoice !== 'team') {
      var a = S.agents.find(function (x) { return x.id === S.agentChoice; });
      if (a) a.starters.forEach(function (s) { pool.push(s); });
    }
    if (pool.length < 4) {
      try { var s = await api('/v1/suggestions'); S.suggestions = s.questions || []; } catch (e) { S.suggestions = []; }
      S.suggestions.forEach(function (q) { if (pool.length < 4 && pool.indexOf(q) < 0) pool.push(q); });
    }
    pool.slice(0, 4).forEach(function (t) {
      var b = h('button', 'starter', esc(t)); b.type = 'button';
      b.onclick = function () { send(t); }; box.appendChild(b);
    });
    var chips = $('dataset-chips'); chips.innerHTML = '';
    S.files.slice(0, 8).forEach(function (f) {
      chips.appendChild(h('span', 'chip', esc(f.name) + (f.kind === 'table' ? ' · ' + Number(f.rows).toLocaleString() + ' rows' : ' · doc')));
    });
    $('btn-samples').classList.toggle('hidden', hasData);
  }

  // --------------------------------------------------------- conversation list
  async function refreshConversations() {
    try { S.conversations = await api('/v1/conversations'); } catch (e) { return; }
    renderChatList();
  }
  function groupName(iso) {
    var d = new Date(iso), now = new Date(), day = 864e5;
    var a = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime(), b = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    var diff = Math.round((b - a) / day);
    return diff <= 0 ? 'Today' : diff === 1 ? 'Yesterday' : diff <= 7 ? 'Previous 7 days' : 'Older';
  }
  function renderChatList() {
    var list = $('chat-list'); list.innerHTML = '';
    var q = $('chat-search').value.toLowerCase().trim(), last = null;
    S.conversations.filter(function (c) { return !q || c.title.toLowerCase().indexOf(q) >= 0; }).forEach(function (c) {
      var g = groupName(c.updated_at);
      if (g !== last) { list.appendChild(h('div', 'group-title', g)); last = g; }
      var row = h('div', 'chat-item' + (c.id === S.currentId ? ' active' : ''));
      var t = h('button', 'title'); t.textContent = c.title; t.type = 'button'; t.onclick = function () { openConversation(c.id); };
      var acts = h('div', 'acts');
      var ren = h('button', '', ICON.pencil); ren.title = 'Rename'; ren.onclick = function (e) { e.stopPropagation(); renameConversation(c); };
      var del = h('button', '', ICON.trash); del.title = 'Delete'; del.onclick = function (e) { e.stopPropagation(); deleteConversation(c); };
      acts.appendChild(ren); acts.appendChild(del); row.appendChild(t); row.appendChild(acts); list.appendChild(row);
    });
  }
  async function renameConversation(c) {
    var t = prompt('Rename chat', c.title); if (!t || !t.trim()) return;
    try { await api('/v1/conversations/' + c.id, { method: 'PATCH', body: { title: t.trim() } }); await refreshConversations(); } catch (e) { toast('Rename failed: ' + e.message, true); }
  }
  async function deleteConversation(c) {
    if (!confirm('Delete this chat?')) return;
    try { await api('/v1/conversations/' + c.id, { method: 'DELETE' }); if (S.currentId === c.id) newChat(); await refreshConversations(); } catch (e) { toast('Delete failed: ' + e.message, true); }
  }
  function newChat() {
    if (S.streaming) stop();
    S.currentId = null; S.lastUserEl = null; S.attachments = []; renderTray();
    $('thread').innerHTML = ''; $('empty').classList.remove('hidden'); renderEmpty(); renderChatList();
    $('app').classList.remove('sb-open'); $('input').focus();
  }
  async function openConversation(id) {
    if (S.streaming) stop();
    $('app').classList.remove('sb-open');
    try {
      var data = await api('/v1/conversations/' + id);
      S.currentId = id; $('thread').innerHTML = ''; $('empty').classList.add('hidden'); S.lastUserEl = null;
      data.messages.forEach(function (m) {
        if (m.role === 'user') addUser(m.content, m.id, m.meta); else renderStoredAssistant(m);
      });
      renderChatList(); scrollBottom(true);
    } catch (e) { toast('Could not open chat: ' + e.message, true); }
  }
  function exportChat() {
    var parts = [];
    Array.prototype.forEach.call($('thread').children, function (m) {
      if (m.classList.contains('user')) parts.push('## You\n\n' + m.querySelector('.bubble').textContent);
      else { var md = m.querySelector('.md'); parts.push('## Assistant\n\n' + (md ? md.__raw || md.textContent : '')); }
    });
    if (!parts.length) return toast('Nothing to download yet.');
    var blob = new Blob([parts.join('\n\n---\n\n')], { type: 'text/markdown' });
    var a = h('a'); a.href = URL.createObjectURL(blob); a.download = 'chat.md'; document.body.appendChild(a); a.click(); a.remove();
  }

  // ------------------------------------------------------------------ markdown
  function renderMarkdown(el, text) {
    el.__raw = text || '';
    var html = window.marked ? window.marked.parse(text || '', { gfm: true, breaks: true }) : esc(text).replace(/\n/g, '<br>');
    el.innerHTML = window.DOMPurify ? window.DOMPurify.sanitize(html, { ADD_ATTR: ['target'] }) : html;
    el.querySelectorAll('a').forEach(function (a) { a.target = '_blank'; a.rel = 'noopener noreferrer'; });
    el.querySelectorAll('table').forEach(function (t) { var w = h('div', 'table-wrap'); t.parentNode.insertBefore(w, t); w.appendChild(t); });
    el.querySelectorAll('pre').forEach(function (pre) {
      var code = pre.querySelector('code'), raw = (code || pre).textContent;
      var lang = ((code && /language-(\w+)/.exec(code.className)) || [])[1] || 'code';
      if (code && window.hljs) { try { window.hljs.highlightElement(code); } catch (e) { /* ignore */ } }
      var box = h('div', 'codeblock'), head = h('div', 'ch', '<span>' + esc(lang) + '</span>');
      var btn = h('button', '', ICON.copy + '<span>Copy</span>'); btn.type = 'button';
      btn.onclick = function () { copyText(raw); btn.lastChild.textContent = 'Copied'; setTimeout(function () { btn.lastChild.textContent = 'Copy'; }, 1500); };
      head.appendChild(btn); pre.parentNode.insertBefore(box, pre); box.appendChild(head); box.appendChild(pre);
    });
  }
  function copyText(t) {
    if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(t).catch(function () { });
    var ta = h('textarea'); ta.value = t; document.body.appendChild(ta); ta.select(); try { document.execCommand('copy'); } catch (e) { /* ignore */ } ta.remove();
  }

  // ------------------------------------------------------------ message views
  function scrollBottom(force) {
    var s = $('scroll'); if (force || s.scrollHeight - s.scrollTop - s.clientHeight < 140) s.scrollTop = s.scrollHeight;
  }
  function addUser(text, id, meta) {
    var m = h('div', 'msg user'); if (id) m.dataset.id = id;
    var wrap = h('div', 'ubody');
    var files = (meta && meta.files) || [];
    if (files.length || (meta && meta.images)) {
      var fl = h('div', 'ufiles');
      files.forEach(function (f) { fl.appendChild(h('span', 'fchip', ICON.file + '<span>' + esc(f.name) + '</span>')); });
      if (meta.images) fl.appendChild(h('span', 'fchip', '🖼 ' + meta.images + (meta.images > 1 ? ' images' : ' image')));
      wrap.appendChild(fl);
    }
    var b = h('div', 'bubble'); b.textContent = text; wrap.appendChild(b);
    var acts = h('div', 'uacts');
    var ed = h('button', '', ICON.pencil); ed.type = 'button'; ed.title = 'Edit message';
    ed.onclick = function () { startEdit(m, text); };
    var cp = h('button', '', ICON.copy); cp.type = 'button'; cp.title = 'Copy';
    cp.onclick = function () { copyText(text); };
    acts.appendChild(cp); acts.appendChild(ed); wrap.appendChild(acts);
    m.appendChild(wrap); $('thread').appendChild(m); S.lastUserEl = m; return m;
  }
  function startEdit(m, text) {
    if (S.streaming) return;
    var wrap = m.querySelector('.ubody'); wrap.style.display = 'none';
    var box = h('div', 'editbox'), ta = h('textarea'); ta.value = text; ta.rows = Math.min(8, Math.max(2, text.split('\n').length));
    var row = h('div', 'erow'), c = h('button', 'btn-secondary', 'Cancel'), s = h('button', 'btn-primary', 'Send');
    c.type = s.type = 'button';
    c.onclick = function () { box.remove(); wrap.style.display = ''; };
    s.onclick = function () {
      var v = ta.value.trim(); if (!v || !m.dataset.id) return;
      var next = m.nextSibling; while (next) { var n = next.nextSibling; next.remove(); next = n; }
      m.remove(); send(v, { edit: m.dataset.id });
    };
    row.appendChild(c); row.appendChild(s); box.appendChild(ta); box.appendChild(row); m.appendChild(box); ta.focus();
  }
  function newAssistant(agent) {
    var m = h('div', 'msg assistant');
    var av = h('div', 'avatar'); av.textContent = (agent && agent.icon) || '🪄';
    var body = h('div', 'body');
    var tag = h('div', 'agent-tag'), status = h('div', 'status'), team = h('div', 'team'), tools = h('div', 'tools'), content = h('div', 'md'), charts = h('div', 'charts'), actions = h('div', 'actions');
    [tag, team, tools, status, content, charts, actions].forEach(function (x) { body.appendChild(x); });
    m.appendChild(av); m.appendChild(body); $('thread').appendChild(m);
    var ui = { root: m, av: av, tag: tag, team: team, status: status, tools: tools, content: content, charts: charts, actions: actions, raw: '', toolEls: {}, msgId: null, feedback: null };
    setStatus(ui, 'Thinking'); return ui;
  }
  function setStatus(ui, text) {
    ui.status.innerHTML = text ? '<span class="dots"><i></i><i></i><i></i></span><span>' + esc(text) + '</span>' : '';
  }
  function setAgentTag(ui, agent, routed, reason, team, mode) {
    if (!agent) return;
    ui.av.textContent = agent.icon;
    var html = '<strong>' + esc(agent.name) + '</strong>';
    if (mode === 'complex') html += '<span class="pill team">Team</span>';
    else if (mode === 'simple' || mode === 'chat') html += '<span class="pill">' + (mode === 'chat' ? 'Chat' : 'Quick answer') + '</span>';
    else if (routed) html += '<span class="pill">auto-selected</span>';
    if (team && team.length) html += '<span>' + team.map(function (a) { return esc(a.icon + ' ' + a.name); }).join(' · ') + '</span>';
    else if (reason) html += '<span>· ' + esc(reason) + '</span>';
    ui.tag.innerHTML = html;
  }
  function toolRow(ui, t) {
    var d = h('details', 'tool'), s = h('summary');
    s.innerHTML = '<span class="spin"></span><span class="tname">' + esc(TOOL_LABEL[t.name] || t.name) + '</span><span class="tmeta">running…</span>';
    var body = h('div', 'tb'); d.appendChild(s); d.appendChild(body);
    var sql = null;
    if (t.name === 'run_sql' && t.args && t.args.query) { sql = t.args.query; body.appendChild(sqlBlock(sql)); }
    else if (t.args && Object.keys(t.args).length && t.name !== 'make_chart') { var p = h('div', 'note'); p.textContent = JSON.stringify(t.args); body.appendChild(p); }
    ui.tools.appendChild(d); ui.toolEls[t.id] = { d: d, s: s, body: body, sql: sql }; return ui.toolEls[t.id];
  }
  function sqlBlock(q) { var s = h('div', 'sql'); s.textContent = q; return s; }
  async function download(sql, format) {
    try {
      var r = await fetch('/v1/export', { method: 'POST', headers: headers(), body: JSON.stringify({ sql: sql, format: format }) });
      if (!r.ok) throw new Error(errText(await r.text()));
      var blob = await r.blob(), a = h('a'); a.href = URL.createObjectURL(blob); a.download = 'result.' + format; document.body.appendChild(a); a.click(); a.remove();
    } catch (e) { toast('Download failed: ' + e.message, true); }
  }
  function finishTool(el, ok, preview) {
    var meta = '';
    el.body.querySelectorAll('.mini, .note.res, .dl').forEach(function (n) { n.remove(); });
    if (preview && preview.columns) {
      meta = preview.row_count + ' row' + (preview.row_count === 1 ? '' : 's') + (preview.truncated ? '+' : '');
      var wrap = h('div', 'mini'), tb = h('table'), thead = h('thead'), trh = h('tr');
      preview.columns.forEach(function (c) { var th = h('th'); th.textContent = c; trh.appendChild(th); }); thead.appendChild(trh); tb.appendChild(thead);
      var tbody = h('tbody'); preview.rows.forEach(function (r) { var tr = h('tr'); r.forEach(function (v) { var td = h('td'); td.textContent = v == null ? '' : v; tr.appendChild(td); }); tbody.appendChild(tr); });
      tb.appendChild(tbody); wrap.appendChild(tb); el.body.appendChild(wrap);
      if (preview.row_count > preview.rows.length) { var n = h('div', 'note res'); n.textContent = 'Showing first ' + preview.rows.length + ' of ' + preview.row_count + ' rows'; el.body.appendChild(n); }
      if (el.sql) {
        var dl = h('div', 'dl'), c1 = h('button', '', ICON.down + '<span>CSV</span>'), c2 = h('button', '', ICON.down + '<span>Excel</span>');
        c1.type = c2.type = 'button'; c1.onclick = function () { download(el.sql, 'csv'); }; c2.onclick = function () { download(el.sql, 'xlsx'); };
        dl.appendChild(c1); dl.appendChild(c2); el.body.appendChild(dl);
      }
    } else if (preview && preview.text && !ok) { var e = h('div', 'note res'); e.textContent = preview.text; el.body.appendChild(e); meta = 'error'; }
    var spin = el.s.querySelector('.spin'); if (spin) { var dot = h('span', 'tok' + (ok ? '' : ' bad')); spin.replaceWith(dot); }
    el.s.querySelector('.tmeta').textContent = meta || (ok ? 'done' : 'error');
  }
  function addChart(ui, spec) {
    var card = h('div', 'chart-card'); if (spec.title) { var t = h('h4'); t.textContent = spec.title; card.appendChild(t); }
    var box = h('div', 'chart-box'), cv = h('canvas'); box.appendChild(cv); card.appendChild(box); ui.charts.appendChild(card);
    if (!window.Chart) { box.textContent = 'Chart library unavailable.'; return; }
    var css = getComputedStyle(document.documentElement), grid = css.getPropertyValue('--border').trim(), txt = css.getPropertyValue('--text-2').trim();
    var pie = spec.type === 'pie' || spec.type === 'doughnut';
    var datasets = (spec.series || []).map(function (s, i) {
      var c = PALETTE[i % PALETTE.length];
      return {
        label: s.name, data: s.data,
        backgroundColor: pie ? (s.data || []).map(function (_, j) { return PALETTE[j % PALETTE.length]; }) : (spec.type === 'line' ? c + '33' : c),
        borderColor: pie ? 'transparent' : c, borderWidth: spec.type === 'line' ? 2 : 0, tension: .3, pointRadius: spec.type === 'line' ? 2 : 4, borderRadius: spec.type === 'bar' ? 6 : 0
      };
    });
    try {
      new window.Chart(cv, {
        type: spec.type, data: { labels: spec.labels, datasets: datasets },
        options: {
          responsive: true, maintainAspectRatio: false, animation: { duration: 400 },
          plugins: { legend: { display: pie || datasets.length > 1, labels: { color: txt } } },
          scales: pie ? {} : { x: { ticks: { color: txt }, grid: { color: grid } }, y: { ticks: { color: txt }, grid: { color: grid }, beginAtZero: true } }
        }
      });
    } catch (e) { box.textContent = 'Could not draw chart.'; }
  }
  var rafPending = false;
  function scheduleRender(ui) {
    if (rafPending) return; rafPending = true;
    requestAnimationFrame(function () { rafPending = false; renderMarkdown(ui.content, ui.raw); scrollBottom(false); });
  }
  async function sendFeedback(ui, value, up, dn) {
    if (!ui.msgId) return;
    var v = ui.feedback === value ? null : value;
    try {
      await api('/v1/messages/' + ui.msgId + '/feedback', { method: 'POST', body: { value: v } });
      ui.feedback = v; up.classList.toggle('on', v === 'up'); dn.classList.toggle('on', v === 'down');
    } catch (e) { toast('Could not save feedback', true); }
  }
  function addActions(ui) {
    ui.actions.innerHTML = '';
    var c = h('button', '', ICON.copy); c.title = 'Copy'; c.type = 'button';
    c.onclick = function () { copyText(ui.raw); c.innerHTML = ICON.check; setTimeout(function () { c.innerHTML = ICON.copy; }, 1500); };
    ui.actions.appendChild(c);
    var up = h('button', ui.feedback === 'up' ? 'on' : '', ICON.up), dn = h('button', ui.feedback === 'down' ? 'on' : '', ICON.dn);
    up.type = dn.type = 'button'; up.title = 'Good answer'; dn.title = 'Bad answer';
    up.onclick = function () { sendFeedback(ui, 'up', up, dn); }; dn.onclick = function () { sendFeedback(ui, 'down', up, dn); };
    ui.actions.appendChild(up); ui.actions.appendChild(dn);
    var r = h('button', '', ICON.refresh); r.title = 'Regenerate'; r.type = 'button';
    r.onclick = function () { if (S.streaming || !S.currentId) return; ui.root.remove(); send('', { regenerate: true }); };
    ui.actions.appendChild(r);
  }
  function renderStoredAssistant(m) {
    var meta = m.meta || {}, ui = newAssistant(meta.agent); setStatus(ui, '');
    ui.msgId = m.id; ui.feedback = meta.feedback || null;
    setAgentTag(ui, meta.agent, false, meta.mode === 'complex' ? '' : '', meta.team, meta.mode);
    (meta.tools || []).forEach(function (t) { var el = toolRow(ui, t); finishTool(el, t.ok !== false, t.preview); });
    ui.raw = m.content || ''; renderMarkdown(ui.content, ui.raw);
    (meta.charts || []).forEach(function (c) { addChart(ui, c); });
    addActions(ui);
  }

  // ----------------------------------------------------------- attachments
  function updateSend() {
    var busy = S.attachments.some(function (a) { return a.uploading; });
    $('send').disabled = S.streaming ? false : (busy || (!$('input').value.trim() && !S.attachments.length));
  }
  function renderTray() {
    var t = $('attach-tray'); t.innerHTML = ''; t.classList.toggle('hidden', !S.attachments.length);
    S.attachments.forEach(function (a, i) {
      var chip = h('span', 'fchip' + (a.error ? ' bad' : ''), (a.image ? '🖼 ' : ICON.file) + '<span>' + esc(a.name) + '</span>' + (a.uploading ? '<span class="spin"></span>' : ''));
      if (a.error) chip.title = a.error;
      var x = h('button', 'x', ICON.x); x.type = 'button'; x.title = 'Remove'; x.onclick = function () { S.attachments.splice(i, 1); renderTray(); updateSend(); };
      chip.appendChild(x); t.appendChild(chip);
    });
    updateSend();
  }
  function readDataUrl(file) {
    return new Promise(function (res, rej) { var r = new FileReader(); r.onload = function () { res(r.result); }; r.onerror = rej; r.readAsDataURL(file); });
  }
  async function uploadFiles(files) {
    var fd = new FormData(); files.forEach(function (f) { fd.append('files', f, f.name); });
    var r = await fetch('/v1/files', { method: 'POST', headers: headers(false), body: fd });
    if (r.status === 401) { showLogin('Please sign in again.'); throw new Error('unauthorized'); }
    if (!r.ok) throw new Error(errText(await r.text()));
    return (await r.json()).results;
  }
  async function handleFiles(list) {
    var files = Array.prototype.slice.call(list || []); if (!files.length) return;
    $('empty').classList.contains('hidden') || null;
    var images = files.filter(function (f) { return /^image\//.test(f.type); });
    var data = files.filter(function (f) { return !/^image\//.test(f.type); });
    for (var i = 0; i < images.slice(0, 4).length; i++) {
      var img = images[i];
      if (img.size > 5 * 1024 * 1024) { toast(img.name + ' is larger than 5 MB.', true); continue; }
      try { S.attachments.push({ image: true, name: img.name || 'image', dataUrl: await readDataUrl(img) }); } catch (e) { toast('Could not read the image', true); }
    }
    if (data.length) {
      var pend = data.map(function (f) { var a = { name: f.name, uploading: true, ids: [] }; S.attachments.push(a); return a; });
      renderTray();
      try {
        var results = await uploadFiles(data);
        await refreshFiles();
        results.forEach(function (r, i) {
          var a = pend[i]; a.uploading = false;
          if (r.status !== 'ok') { a.error = r.error || 'Upload failed'; toast(r.filename + ': ' + a.error, true); return; }
          var names = r.kind === 'table' ? r.tables.map(function (t) { return t.name; }) : [r.filename];
          a.ids = S.files.filter(function (f) { return names.indexOf(f.name) >= 0; }).map(function (f) { return f.id; });
          if (r.kind === 'table') toast(r.tables.map(function (t) { return t.name + ': ' + Number(t.rows).toLocaleString() + ' rows'; }).join(' · ') + ' ready');
        });
      } catch (e) { pend.forEach(function (a) { a.uploading = false; a.error = e.message; }); toast(e.message, true); }
      S.attachments = S.attachments.filter(function (a) { return !a.error; });
    }
    renderTray(); renderEmpty(); $('input').focus();
  }
  async function installSamples() {
    try { var r = await api('/v1/samples/install', { method: 'POST' }); toast('Installed ' + r.installed.length + ' sample tables'); await refreshFiles(); await renderEmpty(); }
    catch (e) { toast(e.message, true); }
  }

  // ----------------------------------------------------------------- voice
  var rec = null;
  function toggleMic() {
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition; if (!SR) return;
    if (rec) { rec.stop(); return; }
    rec = new SR(); rec.interimResults = true; rec.lang = navigator.language || 'en-IN';
    var base = $('input').value;
    $('btn-mic').classList.add('on');
    rec.onresult = function (e) {
      var t = ''; for (var i = 0; i < e.results.length; i++) t += e.results[i][0].transcript;
      $('input').value = (base ? base + ' ' : '') + t; $('input').dispatchEvent(new Event('input'));
    };
    rec.onend = function () { rec = null; $('btn-mic').classList.remove('on'); };
    rec.onerror = function () { rec = null; $('btn-mic').classList.remove('on'); };
    try { rec.start(); } catch (e) { rec = null; }
  }

  // --------------------------------------------------------------------- send
  function submit() {
    var t = $('input').value.trim();
    if (!t && !S.attachments.length) return;
    if (S.attachments.some(function (a) { return a.uploading; })) return;
    $('input').value = ''; $('input').style.height = 'auto';
    send(t, {});
  }
  function setStreaming(on) {
    S.streaming = on; var b = $('send');
    b.innerHTML = on ? ICON.stop : ICON.send; b.title = on ? 'Stop generating' : 'Send'; updateSend();
  }
  function stop() { if (S.abort) S.abort.abort(); }

  async function send(text, opt) {
    if (S.streaming) return;
    if (typeof opt !== 'object' || !opt) opt = {};
    $('empty').classList.add('hidden');
    var atts = opt.regenerate || opt.edit ? [] : S.attachments;
    var fileIds = [], images = [], fileMeta = [];
    atts.forEach(function (a) {
      if (a.image) images.push(a.dataUrl); else { a.ids.forEach(function (id) { fileIds.push(id); }); fileMeta.push({ name: a.name }); }
    });
    if (!opt.regenerate) {
      S.lastUserEl = addUser(text || 'Please analyze the attached file(s).', null, { files: fileMeta, images: images.length });
      if (!opt.edit) { S.attachments = []; renderTray(); }
    }
    var ui = newAssistant(agentInfo(S.agentChoice)); scrollBottom(true);
    setStreaming(true); S.abort = new AbortController();
    var userEl = S.lastUserEl;
    try {
      var resp = await fetch('/v1/chat', {
        method: 'POST', headers: headers(), signal: S.abort.signal,
        body: JSON.stringify({
          message: text, conversation_id: S.currentId, agent_id: S.agentChoice, regenerate: !!opt.regenerate,
          edit_message_id: opt.edit || null, file_ids: fileIds, images: images
        })
      });
      if (resp.status === 401) { showLogin('Please sign in again.'); throw new Error('unauthorized'); }
      if (!resp.ok) throw new Error(errText(await resp.text()));
      var reader = resp.body.getReader(), dec = new TextDecoder(), buf = '';
      for (; ;) {
        var r = await reader.read(); if (r.done) break;
        buf += dec.decode(r.value, { stream: true });
        var i;
        while ((i = buf.indexOf('\n\n')) >= 0) {
          var chunk = buf.slice(0, i); buf = buf.slice(i + 2);
          if (chunk.indexOf('data: ') === 0) { try { handleEvent(JSON.parse(chunk.slice(6)), ui, userEl); } catch (e) { console.error(e); } }
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        ui.status.innerHTML = ''; ui.content.parentNode.appendChild(h('div', 'err', esc(e.message)));
        if (/messages for today|too fast/.test(e.message)) toast(e.message, true);
      }
    } finally {
      setStatus(ui, ''); setStreaming(false); S.abort = null;
      renderMarkdown(ui.content, ui.raw); if (ui.raw || ui.tools.children.length) addActions(ui);
      refreshConversations(); refreshMe(); $('input').focus();
    }
  }

  function handleEvent(ev, ui, userEl) {
    switch (ev.type) {
      case 'start':
        S.currentId = ev.conversation_id;
        if (userEl && ev.user_message_id) userEl.dataset.id = ev.user_message_id;
        if (ev.is_new) { S.conversations.unshift({ id: ev.conversation_id, title: ev.title, updated_at: new Date().toISOString() }); renderChatList(); }
        break;
      case 'meta': setAgentTag(ui, ev.agent, ev.routed, ev.reason, ev.team, ev.mode); break;
      case 'team_agent': setStatus(ui, 'Team working: ' + ev.agent.icon + ' ' + ev.agent.name); break;
      case 'team_agent_done': ui.team.appendChild(h('span', 'tdone', '✓ ' + esc(ev.agent.name))); break;
      case 'team_synthesis': setStatus(ui, 'Combining the findings'); break;
      case 'tool_start': setStatus(ui, TOOL_LABEL[ev.name] || ev.name); toolRow(ui, ev); scrollBottom(false); break;
      case 'tool_result': var el = ui.toolEls[ev.id]; if (el) finishTool(el, ev.ok, ev.preview); setStatus(ui, 'Thinking'); break;
      case 'chart': addChart(ui, ev.spec); scrollBottom(false); break;
      case 'delta': if (ui.status.innerHTML) setStatus(ui, ''); ui.raw += ev.text; scheduleRender(ui); break;
      case 'error': ui.content.parentNode.appendChild(h('div', 'err', esc(ev.message))); break;
      case 'done': ui.msgId = ev.message_id; break;
      case 'title':
        S.conversations.forEach(function (c) { if (c.id === S.currentId) c.title = ev.title; }); renderChatList(); break;
    }
  }

  // ------------------------------------------------------------------- modal
  var tabState = 'general';
  function openModal(tab) {
    tabState = tab; $('modal').classList.remove('hidden'); $('app').classList.remove('sb-open');
    Array.prototype.forEach.call($('tabs').children, function (b) { b.classList.toggle('on', b.dataset.tab === tab); });
    var body = $('tab-body'); body.innerHTML = '<p class="muted">Loading…</p>';
    ({ general: tabGeneral, data: tabData, workspace: tabWorkspace, plan: tabPlan })[tab](body);
  }
  function closeModal() { $('modal').classList.add('hidden'); }
  function field(label, el, hint) {
    var w = h('label', 'field'); w.appendChild(h('span', 'fl', esc(label))); w.appendChild(el); if (hint) w.appendChild(h('span', 'muted small', esc(hint))); return w;
  }

  async function tabGeneral(body) {
    var s = { about: '', style: '' }; try { s = await api('/v1/settings'); } catch (e) { /* ignore */ }
    body.innerHTML = '';
    var about = h('textarea'); about.rows = 4; about.maxLength = 1500; about.value = s.about; about.placeholder = 'e.g. I run a 40-person garment factory in Surat. Amounts are in INR. Financial year is April to March.';
    var style = h('textarea'); style.rows = 3; style.maxLength = 1500; style.value = s.style; style.placeholder = 'e.g. Answer in Hinglish, keep it short, always show a chart for trends.';
    body.appendChild(field('What should the agents know about you and your company?', about));
    body.appendChild(field('How should they respond?', style));
    var save = h('button', 'btn-primary', 'Save'); save.type = 'button';
    save.onclick = async function () {
      try { await api('/v1/settings', { method: 'PUT', body: { about: about.value, style: style.value } }); toast('Saved. Applies to new messages.'); } catch (e) { toast(e.message, true); }
    };
    body.appendChild(save);
  }

  async function tabData(body) {
    await refreshFiles(); body.innerHTML = '';
    var up = h('button', 'btn-primary', 'Upload files'); up.type = 'button'; up.onclick = function () { $('file-input').click(); };
    body.appendChild(up);
    body.appendChild(h('p', 'muted small', 'CSV, Excel (all sheets), JSON, PDF, Word, TXT. Re-uploading a file with the same name replaces it. Max ' + ((S.me && S.me.limits.max_upload_mb) || 50) + ' MB per file.'));
    if (!S.files.length) { body.appendChild(h('p', 'muted', 'Nothing uploaded yet.')); return; }
    var list = h('div', 'flist');
    S.files.forEach(function (f) {
      var row = h('div', 'frow');
      row.appendChild(h('div', 'finfo', '<strong>' + esc(f.name) + '</strong><span class="muted small">' +
        (f.kind === 'table' ? Number(f.rows).toLocaleString() + ' rows · ' + f.column_count + ' columns' : 'document') + ' · ' + esc(f.filename || '') + (f.is_sample ? ' · sample' : '') + '</span>'));
      var pv = h('button', 'btn-secondary', 'Preview'), del = h('button', 'btn-secondary danger', 'Delete'); pv.type = del.type = 'button';
      var pane = h('div', 'fprev hidden');
      pv.onclick = async function () {
        if (!pane.classList.contains('hidden')) { pane.classList.add('hidden'); return; }
        pane.classList.remove('hidden'); pane.textContent = 'Loading…';
        try {
          var d = await api('/v1/files/' + f.id); pane.innerHTML = '';
          if (d.preview_text != null) { pane.textContent = d.preview_text; return; }
          var cols = h('div', 'cols small muted', d.columns.map(function (c) { return esc(c.name) + ' <em>' + esc(String(c.type).toLowerCase()) + '</em>'; }).join(' · ')); pane.appendChild(cols);
          var wrap = h('div', 'mini'), tb = h('table'), tr = h('tr');
          d.preview.columns.forEach(function (c) { var th = h('th'); th.textContent = c; tr.appendChild(th); }); var th = h('thead'); th.appendChild(tr); tb.appendChild(th);
          var tbd = h('tbody'); d.preview.rows.slice(0, 8).forEach(function (r) { var t = h('tr'); r.forEach(function (v) { var td = h('td'); td.textContent = v == null ? '' : v; t.appendChild(td); }); tbd.appendChild(t); });
          tb.appendChild(tbd); wrap.appendChild(tb); pane.appendChild(wrap);
        } catch (e) { pane.textContent = e.message; }
      };
      del.onclick = async function () {
        if (!confirm('Delete "' + f.name + '"? Agents will no longer see it.')) return;
        try { await api('/v1/files/' + f.id, { method: 'DELETE' }); await refreshFiles(); renderEmpty(); tabData(body); } catch (e) { toast(e.message, true); }
      };
      var acts = h('div', 'facts'); acts.appendChild(pv); acts.appendChild(del); row.appendChild(acts); list.appendChild(row); list.appendChild(pane);
    });
    body.appendChild(list);
  }

  async function tabWorkspace(body) {
    body.innerHTML = '';
    if (!S.config.workspace_enabled && !(S.me && S.me.workspace_enabled)) {
      body.appendChild(h('p', 'muted', 'You are running in single-user local mode. Team workspaces, invites and sign-in are available when the server runs with Supabase (STORAGE=supabase).'));
      return;
    }
    var name = h('input'); name.value = (S.me && S.me.tenant && S.me.tenant.name) || '';
    var sv = h('button', 'btn-secondary', 'Rename'); sv.type = 'button';
    sv.onclick = async function () { try { await api('/v1/workspace', { method: 'PUT', body: { name: name.value } }); toast('Workspace renamed'); await refreshMe(); } catch (e) { toast(e.message, true); } };
    var row = h('div', 'inline'); row.appendChild(name); row.appendChild(sv);
    body.appendChild(field('Workspace name', row));
    var inv = h('button', 'btn-primary', 'Create invite link'); inv.type = 'button';
    var out = h('div', 'invite muted small');
    inv.onclick = async function () {
      try { var r = await api('/v1/workspace/invites', { method: 'POST' }); var url = location.origin + r.path; out.textContent = url + '  (valid 7 days)'; copyText(url); toast('Invite link copied'); }
      catch (e) { toast(e.message, true); }
    };
    body.appendChild(inv); body.appendChild(out);
    body.appendChild(h('h3', '', 'Members'));
    try {
      var ms = await api('/v1/workspace/members'), list = h('div', 'flist');
      ms.forEach(function (m) {
        var r = h('div', 'frow'); r.appendChild(h('div', 'finfo', '<strong>' + esc(m.email || m.user_id) + '</strong><span class="muted small">' + esc(m.role) + '</span>'));
        if (m.role !== 'owner') {
          var rm = h('button', 'btn-secondary danger', 'Remove'); rm.type = 'button';
          rm.onclick = async function () { if (!confirm('Remove this member?')) return; try { await api('/v1/workspace/members/' + m.user_id, { method: 'DELETE' }); tabWorkspace(body); } catch (e) { toast(e.message, true); } };
          var a = h('div', 'facts'); a.appendChild(rm); r.appendChild(a);
        }
        list.appendChild(r);
      });
      body.appendChild(list);
    } catch (e) { body.appendChild(h('p', 'muted', esc(e.message))); }
  }

  async function tabPlan(body) {
    await refreshMe(); body.innerHTML = '';
    var u = S.me && S.me.usage; if (!u) { body.textContent = 'Usage unavailable.'; return; }
    body.appendChild(h('div', 'plan', '<div class="plan-name">' + (u.pro ? 'Pro' : 'Free') + ' plan</div>' +
      '<div class="bar big"><i style="width:' + Math.min(100, Math.round(100 * u.used / Math.max(1, u.limit))) + '%"></i></div>' +
      '<div class="muted">' + u.used + ' of ' + u.limit + ' messages used today · resets at midnight UTC</div>' +
      '<div class="muted small">Tokens today: ' + Number(u.tokens_in).toLocaleString() + ' in / ' + Number(u.tokens_out).toLocaleString() + ' out</div>'));
    if (!u.pro) body.appendChild(h('p', 'muted', 'Need more? Ask your workspace admin to upgrade to Pro for ' + '3,000 messages a day.'));
  }

  document.addEventListener('DOMContentLoaded', function () {
    init().catch(function (e) { showLogin('Could not start the app: ' + ((e && e.message) || e), true); });
  });
})();
