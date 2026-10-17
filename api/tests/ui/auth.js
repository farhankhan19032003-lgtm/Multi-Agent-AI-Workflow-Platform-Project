// Login / signup flow checks against a fake Supabase client (no network).
// Run: node auth.js
const { JSDOM } = require('jsdom');
const fs = require('fs');
const path = require('path');
const WEB = path.join(__dirname, '../../web');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let failed = 0;
const check = (name, ok, extra) => { if (!ok) failed++; console.log((ok ? 'PASS ' : 'FAIL ') + name + (extra && !ok ? '  -> ' + extra : '')); };
async function waitFor(fn, ms = 3000) { const t = Date.now(); while (Date.now() - t < ms) { try { const v = fn(); if (v) return v; } catch (e) {} await sleep(20); } return null; }

async function boot({ hash = '', session = null } = {}) {
  const html = fs.readFileSync(path.join(WEB, 'index.html'), 'utf8').replace(/<script src="https:[^>]*><\/script>/g, '');
  const dom = new JSDOM(html, { url: 'http://127.0.0.1:8000/' + hash, runScripts: 'outside-only', pretendToBeVisual: true });
  const w = dom.window;
  w.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
  w.HTMLElement.prototype.scrollIntoView = () => {};
  const calls = []; const listeners = []; const reqs = [];
  const next = {}; // per-method scripted result
  const sb = {
    auth: {
      onAuthStateChange: (cb) => { listeners.push(cb); },
      getSession: async () => ({ data: { session } }),
      signInWithPassword: async (a) => { calls.push(['signIn', a]); return next.signIn || { data: { session: { access_token: 't', user: { email: a.email } } }, error: null }; },
      signUp: async (a) => { calls.push(['signUp', a]); return next.signUp || { data: { session: null, user: { identities: [{}] } }, error: null }; },
      resend: async (a) => { calls.push(['resend', a]); return { error: null }; },
      resetPasswordForEmail: async (e, o) => { calls.push(['reset', e, o]); return { error: null }; },
      updateUser: async (a) => { calls.push(['update', a]); return { error: null }; },
      signInWithOAuth: async (a) => { calls.push(['oauth', a]); return { data: {}, error: null }; },
      signOut: async () => {},
    },
  };
  w.supabase = { createClient: () => sb };
  w.fetch = async (u) => {
    u = String(u); reqs.push(u);
    if (u.includes('/auth/v1/settings')) return { ok: true, status: 200, json: async () => ({ external: { email: true, google: !!w.__googleOn, github: !!w.__ghOn } }) };
    if (u.includes('/v1/config')) return { ok: true, status: 200, json: async () => ({ dev_no_auth: false, supabase_url: 'https://x.supabase.co', supabase_anon_key: 'k', workspace_enabled: true }) };
    return { ok: false, status: 401, json: async () => ({ detail: 'x' }), text: async () => '' };
  };
  w.AbortController = AbortController; w.TextDecoder = TextDecoder;
  w.marked = { parse: (s) => s, setOptions() {}, use() {} }; w.DOMPurify = { sanitize: (s) => s };
  w.eval(fs.readFileSync(path.join(WEB, 'app.js'), 'utf8'));
  await sleep(30); // jsdom fires DOMContentLoaded itself
  const $ = (id) => w.document.getElementById(id);
  const vis = (id) => !$(id).classList.contains('hidden');
  const type = (id, v) => { $(id).value = v; $(id).dispatchEvent(new w.Event('input', { bubbles: true })); };
  const submit = async () => { $('login-form').dispatchEvent(new w.Event('submit', { cancelable: true, bubbles: true })); await sleep(40); };
  await waitFor(() => vis('login') || !$('app').classList.contains('hidden'));
  return { w, $, vis, type, submit, calls, next, listeners, reqs };
}

(async () => {
  // 1. login page layout
  let t = await boot();
  check('login page shown when signed out', t.vis('login') && !t.vis('app'));
  check('step 1 shows only email + continue', t.$('auth-title').textContent === 'Welcome back' && t.vis('login-email') && !t.vis('pw-wrap') && t.$('btn-signin').textContent === 'Continue');
  check('sign-up link visible', t.vis('auth-switch') && /Sign up/.test(t.$('auth-switch').textContent));

  // 2. email validation
  t.type('login-email', 'not-an-email'); await t.submit();
  check('invalid email rejected', /not valid/i.test(t.$('login-msg').textContent) && !t.vis('pw-wrap'));

  // 3. login: email -> password step
  t.type('login-email', 'a@b.com'); await t.submit();
  check('step 2 shows email chip + password + forgot', t.vis('auth-email-chip') && t.$('auth-email-text').textContent === 'a@b.com' && t.vis('pw-wrap') && t.vis('auth-forgot') && !t.vis('login-email'));
  check('password button says Log in', t.$('btn-signin').textContent === 'Log in');
  t.$('pw-toggle').click();
  check('show password toggles type', t.$('login-password').type === 'text');
  t.$('pw-toggle').click();
  check('hide password toggles back', t.$('login-password').type === 'password');
  t.$('auth-edit').click();
  check('Edit returns to email step with email kept', t.vis('login-email') && t.$('login-email').value === 'a@b.com');
  t.type('login-email', 'a@b.com'); await t.submit();

  // 4. wrong password
  t.next.signIn = { data: {}, error: { code: 'invalid_credentials', message: 'Invalid login credentials' } };
  t.type('login-password', 'wrongpass'); await t.submit();
  check('wrong password shows friendly error', t.$('login-msg').textContent === 'Incorrect email or password.' && t.$('login-msg').classList.contains('bad'));
  check('button re-enabled after error', !t.$('btn-signin').disabled);

  // 5. unverified email on login
  t.next.signIn = { data: {}, error: { code: 'email_not_confirmed', message: 'Email not confirmed' } };
  await t.submit();
  check('unverified email moves to check-inbox view with resend', t.$('auth-title').textContent === 'Check your inbox' && t.vis('btn-resend') && !t.vis('btn-signin'));
  t.$('auth-back-link').click();
  check('back to log in works', t.$('auth-title').textContent === 'Welcome back' && t.vis('login-email'));
  t.w.close();

  // 6. successful login reaches the app
  t = await boot();
  t.type('login-email', 'a@b.com'); await t.submit();
  t.type('login-password', 'goodpass1'); await t.submit();
  check('successful login starts the app (loads agents)', !!(await waitFor(() => t.reqs.some((u) => u.includes('/v1/agents')))));
  check('signIn called with email+password', t.calls.some((c) => c[0] === 'signIn' && c[1].email === 'a@b.com' && c[1].password === 'goodpass1'));
  t.w.close();

  // 7. signup flow
  t = await boot();
  t.$('auth-switch-link').click();
  check('switch to signup', t.$('auth-title').textContent === 'Create an account' && /Log in/.test(t.$('auth-switch').textContent));
  t.type('login-email', 'new@user.com'); await t.submit();
  check('signup step 2 shows password rules + Create account', t.vis('pw-rules') && t.$('btn-signin').textContent === 'Create account');
  t.type('login-password', 'short'); await t.submit();
  check('short password blocked', /at least 8/.test(t.$('login-msg').textContent) && !t.calls.some((c) => c[0] === 'signUp'));
  t.type('login-password', 'longenough1');
  check('rule turns green at 8 chars', t.$('rule-len').classList.contains('ok'));
  await t.submit();
  check('signUp called once with redirect to origin', t.calls.filter((c) => c[0] === 'signUp').length === 1 && t.calls.find((c) => c[0] === 'signUp')[1].options.emailRedirectTo === 'http://127.0.0.1:8000');
  check('signup w/o session shows verify-email screen', t.$('auth-title').textContent === 'Check your inbox' && /new@user\.com/.test(t.$('auth-sub').textContent));
  check('resend is on cooldown', t.$('btn-resend').disabled && /\(30s\)/.test(t.$('btn-resend').textContent));
  t.w.close();

  // 8. signup auto-login (email confirmation off)
  t = await boot(); t.next.signUp = { data: { session: { access_token: 't', user: { email: 'n@u.com' } }, user: {} }, error: null };
  t.$('auth-switch-link').click(); t.type('login-email', 'n@u.com'); await t.submit(); t.type('login-password', 'longenough1'); await t.submit();
  check('signup with instant session starts the app', !!(await waitFor(() => t.reqs.some((u) => u.includes('/v1/agents')))));
  t.w.close();

  // 9. existing email on signup
  t = await boot(); t.next.signUp = { data: { session: null, user: { identities: [] } }, error: null };
  t.$('auth-switch-link').click(); t.type('login-email', 'dup@u.com'); await t.submit(); t.type('login-password', 'longenough1'); await t.submit();
  check('duplicate email sends user to log in', t.$('auth-title').textContent === 'Welcome back' && /already have an account/i.test(t.$('login-msg').textContent) && t.vis('pw-wrap'));
  t.w.close();

  // 10. forgot password
  t = await boot();
  t.type('login-email', 'a@b.com'); await t.submit(); t.$('auth-forgot').click();
  check('forgot opens reset view with email prefilled', t.$('auth-title').textContent === 'Reset your password' && t.$('login-email').value === 'a@b.com');
  await t.submit();
  check('reset email requested with redirect', t.calls.some((c) => c[0] === 'reset' && c[1] === 'a@b.com' && c[2].redirectTo === 'http://127.0.0.1:8000'));
  check('reset shows check-inbox screen', t.$('auth-title').textContent === 'Check your inbox' && /reset link/.test(t.$('auth-sub').textContent));
  t.w.close();

  // 11. recovery link -> choose new password
  t = await boot({ hash: '#access_token=a&type=recovery', session: { access_token: 't', user: { email: 'a@b.com' } } });
  check('recovery link opens new-password form (not the app)', t.$('auth-title').textContent === 'Choose a new password' && t.vis('login') && t.vis('pw-wrap2'));
  t.type('login-password', 'newpass123'); t.type('login-password2', 'different1'); await t.submit();
  check('mismatched passwords rejected', /do not match/i.test(t.$('login-msg').textContent) && !t.calls.some((c) => c[0] === 'update'));
  t.type('login-password2', 'newpass123'); await t.submit();
  check('password updated then app opens', t.calls.some((c) => c[0] === 'update' && c[1].password === 'newpass123') && !!(await waitFor(() => t.reqs.some((u) => u.includes('/v1/agents')))));
  t.w.close();

  // 12. expired link
  t = await boot({ hash: '#error=access_denied&error_code=otp_expired' });
  check('expired link shows error on reset view', t.$('auth-title').textContent === 'Reset your password' && /expired/i.test(t.$('login-msg').textContent));
  t.w.close();

  // 12b. Google button
  t = await boot();
  check('Google button visible on email step', t.vis('auth-social') && /Continue with Google/.test(t.$('btn-google').textContent));
  t.$('btn-google').click(); await sleep(80);
  check('Google disabled in Supabase -> friendly message, no redirect', /not enabled yet/.test(t.$('login-msg').textContent) && !t.calls.some((c) => c[0] === 'oauth') && !t.$('btn-google').disabled);
  t.w.__googleOn = true; t.$('btn-google').click(); await sleep(80);
  check('Google enabled -> OAuth started with redirect to origin', t.calls.some((c) => c[0] === 'oauth' && c[1].provider === 'google' && c[1].options.redirectTo === 'http://127.0.0.1:8000'));
  t.w.close();

  // 12c. GitHub button (fresh page: buttons stay locked after a successful redirect)
  t = await boot();
  check('GitHub button visible, no LinkedIn button', /Continue with GitHub/.test(t.$('btn-github').textContent) && !t.$('btn-linkedin'));
  t.$('btn-github').click(); await sleep(80);
  check('GitHub disabled -> friendly message', /GitHub sign-in is not enabled/.test(t.$('login-msg').textContent) && !t.calls.some((c) => c[0] === 'oauth' && c[1].provider === 'github'));
  t.w.__ghOn = true; t.$('btn-github').click(); await sleep(80);
  check('GitHub enabled -> OAuth with provider github', t.calls.some((c) => c[0] === 'oauth' && c[1].provider === 'github' && c[1].options.redirectTo === 'http://127.0.0.1:8000'));
  t.type('login-email', 'a@b.com'); await t.submit();
  check('social buttons hidden on password step', !t.vis('auth-social'));
  t.w.close();

  // 13. already signed in
  t = await boot({ session: { access_token: 't', user: { email: 'a@b.com' } } });
  check('existing session skips login and starts the app', !!(await waitFor(() => t.reqs.some((u) => u.includes('/v1/agents')))));
  t.w.close();

  console.log(failed ? `\n${failed} auth check(s) FAILED` : '\nall auth checks passed');
  process.exit(failed ? 1 : 0);
})();
