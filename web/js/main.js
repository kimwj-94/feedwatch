// FeedWatch v2 — bootstrap: theme, backend detection, session, login, routing.
import { detectMode } from './config.js';
import { LocalAdapter } from './data/local.js';
import { el, mount, clear } from './util/dom.js';
import { icon, googleMark } from './util/icons.js';
import { toast, openModal, field, sourceCheckset } from './ui/components.js';
import { mountApp } from './ui/shell.js';

const root = document.getElementById('app');
const SESSION_KEY = 'feedwatch_session';
const THEME_KEY = 'feedwatch_theme';

/* ---------------- Theme ---------------- */
const mql = window.matchMedia('(prefers-color-scheme: dark)');
function themePref() { return localStorage.getItem(THEME_KEY) || 'system'; }
function resolvedTheme() { const p = themePref(); return p === 'system' ? (mql.matches ? 'dark' : 'light') : p; }
function applyTheme() { document.documentElement.setAttribute('data-theme', resolvedTheme()); }
function setTheme(p) { localStorage.setItem(THEME_KEY, p); applyTheme(); }
function cycleTheme() { const order = ['system', 'light', 'dark']; setTheme(order[(order.indexOf(themePref()) + 1) % 3]); }
mql.addEventListener('change', () => { if (themePref() === 'system') applyTheme(); });
applyTheme();

/* ---------------- Session ---------------- */
function loadSession() { try { return JSON.parse(localStorage.getItem(SESSION_KEY) || 'null'); } catch { return null; } }
function saveSession(s) { localStorage.setItem(SESSION_KEY, JSON.stringify(s)); }
function clearSession() { localStorage.removeItem(SESSION_KEY); }

/* ---------------- App state ---------------- */
let adapter, mode, currentUser, viewCleanup = null, seenBaseline = null;
function teardownView() { if (viewCleanup) { try { viewCleanup(); } catch (e) { console.error(e); } viewCleanup = null; } }

// 로그인 확정: '내 미확인' 기준선(직전 방문 시각)을 잡고 화면을 띄운 뒤, 이번 방문 시각을 기록한다.
function enterAs(user) {
  currentUser = user;
  seenBaseline = user.last_seen || null;
  renderApp();
  markSeen();
}
async function markSeen() {
  if (!currentUser || !adapter.updateProfile) return;
  const now = new Date().toISOString();
  try { await adapter.updateProfile({ ...currentUser, last_seen: now }); currentUser.last_seen = now; } catch (e) { void e; }
}

async function boot() {
  try {
    const detected = await detectMode();
    mode = detected.mode;
    if (mode === 'cloud') return bootCloud(detected.firebaseConfig);
    return bootDemo();
  } catch (err) {
    console.error(err);
    renderFatal(err);
  }
}

async function bootDemo() {
  adapter = await LocalAdapter.create();
  const config = await adapter.getConfig();
  if (adapter.archiveOld) await adapter.archiveOld(config.auto_archive_days);
  const session = loadSession();
  if (session && session.mode === 'demo') {
    const users = await adapter.listUsers();
    const u = users.find(x => x.id === session.userId);
    if (u) return enterAs(u);
  }
  renderLogin();
}

async function bootCloud(cfg) {
  // Cloud backend is imported lazily so demo mode stays dependency-free.
  const { CloudAdapter } = await import('./data/firestore.js');
  adapter = await CloudAdapter.create(cfg);
  // Firebase persists auth across reloads; rules require sign-in before any read.
  const fbUser = await adapter.waitForAuth();
  if (fbUser) {
    try {
      const u = await adapter.resolveAppUser(fbUser.email);
      if (u) { await adapter.startListeners(); return enterAs(u); }
      await adapter.createRequest({ email: fbUser.email, name: fbUser.displayName || (fbUser.email || '').split('@')[0], provider: 'firebase', uid: fbUser.uid }).catch(() => {});
      return renderPending(fbUser.email);
    } catch (e) { console.error(e); }
  }
  renderLogin();
}

/* ---------------- Login ---------------- */
async function renderLogin() {
  teardownView();
  root.removeAttribute('aria-busy');
  const users = await adapter.listUsers().catch(() => []);
  const card = el('div', { class: 'login__card' });

  card.append(
    el('div', { class: 'login__brand' }, [
      el('span', { class: 'logo' }, [icon('logo')]),
      el('h1', { class: 'login__title', text: 'FeedWatch' }),
    ]),
    el('p', { class: 'login__sub', text: '가족 통합 모니터링 대시보드' }),
  );

  const msg = el('div', { class: 'login__msg', role: 'alert' });

  if (mode === 'demo') {
    const select = el('select', { class: 'select', id: 'demo-user', 'aria-label': '사용자 선택' },
      users.map(u => el('option', { value: u.id }, [`${u.name} <${u.email}> · ${u.role === 'admin' ? '관리자' : '구성원'}`]))
    );
    const submit = () => {
      const id = select.value;
      const u = users.find(x => x.id === id);
      if (!u) { msg.textContent = '사용자를 선택하세요.'; msg.classList.add('is-error'); return; }
      saveSession({ mode: 'demo', userId: u.id, email: u.email });
      enterAs(u);
    };
    card.append(
      el('div', { class: 'field' }, [
        el('label', { class: 'field__label', for: 'demo-user' }, ['로그인 계정']),
        select,
      ]),
      msg,
      el('button', { class: 'btn btn--primary', style: { width: '100%' }, onclick: submit }, ['로그인']),
      el('div', { class: 'login__hint' }, [
        el('span', { class: 'modepill' }, [icon('eye'), '데모 모드']),
        ' Firebase 설정 없이 샘플 데이터로 모든 기능을 체험합니다. 변경사항은 이 브라우저에만 저장됩니다.',
      ]),
    );
  } else {
    // Cloud login (email / Google) — wired in auth.js
    renderCloudLogin(card, msg);
  }

  mount(root, el('div', { class: 'login' }, [card]));
  setTimeout(() => card.querySelector('select,input,button')?.focus(), 0);
}

async function renderCloudLogin(card, msg) {
  const { CloudAuth } = await import('./auth.js');
  const auth = new CloudAuth(adapter);
  let viewMode = 'login';
  const formArea = el('div', {});

  const finish = (result) => {
    if (result && result.pending) return renderPending(result.email);
    saveSession({ mode: 'cloud', userId: result.user.id, email: result.user.email });
    enterAs(result.user);
  };
  const ok = (text) => { msg.textContent = text; msg.className = 'login__msg is-ok'; };
  const fail = (e) => { msg.textContent = e.message || String(e); msg.className = 'login__msg is-error'; };
  const clearMsg = () => { msg.textContent = ''; msg.className = 'login__msg'; };
  const doReset = async (email) => { try { await auth.resetPassword(email); ok('비밀번호 재설정 메일을 보냈습니다. 메일함을 확인하세요.'); } catch (e) { fail(e); } };

  function renderForm() {
    clearMsg();
    clear(formArea);
    const googleBtn = el('button', { class: 'btn btn--google btn--block', type: 'button',
      onclick: async () => { try { finish(await auth.googleLogin()); } catch (e) { fail(e); } } },
      [googleMark(), 'Google로 ' + (viewMode === 'signup' ? '가입 신청' : '로그인')]);

    if (viewMode === 'login') {
      const email = el('input', { class: 'input', type: 'email', placeholder: '이메일', autocomplete: 'username' });
      const pw = el('input', { class: 'input', type: 'password', placeholder: '비밀번호', autocomplete: 'current-password' });
      const doLogin = async () => { try { finish(await auth.emailLogin(email.value.trim(), pw.value)); } catch (e) { fail(e); } };
      pw.addEventListener('keydown', e => { if (e.key === 'Enter') doLogin(); });
      formArea.append(
        googleBtn,
        el('div', { class: 'divider' }, ['또는 이메일로']),
        field('이메일', email), field('비밀번호', pw),
        el('button', { class: 'btn btn--primary btn--block', onclick: doLogin }, ['로그인']),
        el('div', { class: 'login__row' }, [
          el('button', { class: 'login__link', type: 'button', onclick: () => doReset(email.value.trim()) }, ['비밀번호 찾기']),
          el('button', { class: 'login__link', type: 'button', onclick: () => { viewMode = 'signup'; renderForm(); } }, ['가입 신청 →']),
        ]),
      );
    } else {
      const name = el('input', { class: 'input', placeholder: '이름', autocomplete: 'name' });
      const email = el('input', { class: 'input', type: 'email', placeholder: '이메일', autocomplete: 'email' });
      const pw = el('input', { class: 'input', type: 'password', placeholder: '비밀번호 (6자 이상)', autocomplete: 'new-password' });
      const doSignup = async () => { try { finish(await auth.signUp(name.value.trim(), email.value.trim(), pw.value)); } catch (e) { fail(e); } };
      pw.addEventListener('keydown', e => { if (e.key === 'Enter') doSignup(); });
      formArea.append(
        googleBtn,
        el('div', { class: 'divider' }, ['또는 이메일로']),
        field('이름', name), field('이메일', email), field('비밀번호', pw),
        el('button', { class: 'btn btn--primary btn--block', onclick: doSignup }, ['가입 신청']),
        el('div', { class: 'login__row' }, [
          el('span', { class: 'faint', text: '이미 계정이 있나요?' }),
          el('button', { class: 'login__link', type: 'button', onclick: () => { viewMode = 'login'; renderForm(); } }, ['로그인 →']),
        ]),
      );
    }
  }

  renderForm();
  card.append(formArea, msg, el('div', { class: 'login__hint' }, ['관리자가 승인한 가족만 입장할 수 있어요. 가입 신청 후 승인되면 로그인됩니다.']));
}

function renderPending(email) {
  teardownView();
  root.removeAttribute('aria-busy');
  mount(root, el('div', { class: 'login' }, [
    el('div', { class: 'login__card notice' }, [
      el('div', { class: 'notice__icon' }, [icon('clock')]),
      el('h1', { class: 'login__title', text: '승인 대기 중' }),
      el('p', { class: 'login__sub' }, [
        email ? el('b', { text: email }) : '', ' 계정의 가입 신청이 접수되었습니다. 관리자가 승인하면 로그인할 수 있어요.',
      ]),
      el('button', { class: 'btn btn--ghost btn--block', style: { marginTop: '20px' },
        onclick: async () => { try { if (adapter.signOut) await adapter.signOut(); } catch (e) { void e; } renderLogin(); } }, ['로그아웃']),
    ]),
  ]));
}

async function openProfileSettings() {
  const sources = await adapter.listSources().catch(() => []);
  const nameInput = el('input', { class: 'input', value: currentUser.name || '' });
  const notify = el('input', { type: 'checkbox', checked: currentUser.notify_email !== false });
  const picker = sourceCheckset(sources, currentUser.notify_sources || []);
  openModal({
    title: '내 설정',
    body: [
      field('표시 이름', nameInput),
      el('label', { class: 'checkbox' }, [notify, '새 글 이메일 알림 받기']),
      el('div', { class: 'field' }, [
        el('label', { class: 'field__label', text: '알림 받을 사이트' }),
        picker.node,
      ]),
    ],
    actions: [
      { label: '취소', variant: 'ghost' },
      { label: '저장', variant: 'primary', autofocus: true, onClick: async () => {
        const name = nameInput.value.trim() || currentUser.name;
        const notify_sources = picker.get();
        const updated = { ...currentUser, name, notify_email: notify.checked, notify_sources };
        try { await adapter.updateProfile(updated); } catch (e) { toast(e.message || '저장에 실패했습니다.', { variant: 'danger' }); return false; }
        currentUser = updated; renderApp(); toast('저장했습니다.', { variant: 'success' });
      } },
    ],
  });
}

/* ---------------- App routing ---------------- */
function buildCtx() {
  return {
    adapter, mode, user: currentUser, seenSince: seenBaseline,
    theme: { pref: themePref, resolved: resolvedTheme, cycle: () => cycleTheme() },
    profile: () => openProfileSettings(),
    logout: async () => { try { if (adapter.signOut) await adapter.signOut(); } catch (e) { console.error(e); } clearSession(); currentUser = null; seenBaseline = null; renderLogin(); toast('로그아웃되었습니다.'); },
    // 데모 전용: 다른 가족 계정 화면으로 즉시 전환
    switchUser: (u) => { saveSession({ mode: 'demo', userId: u.id, email: u.email }); enterAs(u); toast(`${u.name} 계정으로 전환했습니다.`); },
  };
}

function renderApp() {
  teardownView();
  clear(root);
  viewCleanup = mountApp(root, buildCtx());
  root.removeAttribute('aria-busy');
}

function renderFatal(err) {
  mount(root, el('div', { class: 'login' }, [
    el('div', { class: 'login__card' }, [
      el('h1', { class: 'login__title', text: '시작할 수 없습니다' }),
      el('p', { class: 'login__sub', text: String(err && err.message || err) }),
      el('button', { class: 'btn btn--primary', onclick: () => location.reload() }, ['다시 시도']),
    ]),
  ]));
}

boot();
