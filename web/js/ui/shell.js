// FeedWatch v2.2 — unified app shell (바빠요바빠 v4 디자인).
// Sidebar nav(받은 글 + 관리) + topbar + subbar + content. One place to find
// and change everything; management items live in the sidebar (발견성 개선).
import { el, mount, clear, debounce } from '../util/dom.js';
import { icon } from '../util/icons.js';
import { relativeTime, localDateTime, withinDateFilter, DATE_FILTERS, groupColorIndex, groupColorName, GROUP_COLORS, pluralCount } from '../util/format.js';
import { toast, openModal, confirmDialog, emptyState, renderSkeleton, field, sourceCheckset } from './components.js';
import { ITEM_STATUS, SOURCE_TYPES, SOURCE_TYPE_LABELS } from '../data/adapter.js';

const FEED_VIEWS = {
  new: { label: '신규', sub: '아직 확인하지 않은 새 글', statuses: [ITEM_STATUS.NEW] },
  archive: { label: '보관함', sub: '읽었거나 7일 지난 글', statuses: [ITEM_STATUS.READ, ITEM_STATUS.ARCHIVED] },
  trash: { label: '휴지통', sub: '삭제한 글', statuses: [ITEM_STATUS.DELETED] },
};
const MANAGE_VIEWS = {
  sources: { label: 'URL 관리', sub: '모니터링할 사이트', icon: 'link' },
  groups: { label: '구분값 관리', sub: '공통·아빠·엄마 등 분류', icon: 'tag' },
  logs: { label: '크롤링 로그', sub: '수집 실행 기록', icon: 'list' },
  users: { label: '사용자 관리', sub: '가족 구성원', icon: 'users', adminOnly: true },
  requests: { label: '가입 신청', sub: '승인 대기', icon: 'user', adminOnly: true },
  settings: { label: '설정', sub: '자동 보관·이메일', icon: 'settings', adminOnly: true },
};

// 사이트·항목의 구분값 목록. 옛 데이터(group_id 단일)도 그대로 읽는다.
function groupsOf(x) { return (x && x.group_ids) || (x && x.group_id ? [x.group_id] : []); }

export function mountApp(root, ctx) {
  const { adapter, user } = ctx;
  const isAdmin = user.role === 'admin';
  const state = { view: 'dashboard', groupId: null, dateFilter: 'all', sort: 'newest', query: '', editingSource: null };
  let data = { groups: [], sources: [], items: [], users: [], requests: [], logs: [], config: {} };
  let loaded = false, sidebarOpen = false, lastRefreshed = null;

  /* ---------- persistent chrome ---------- */
  const navEl = el('nav', { class: 'sidebar-nav', 'aria-label': '주 메뉴' });
  const sideFoot = el('div', { class: 'side-foot' });
  const sidebar = el('aside', { class: 'sidebar' }, [
    el('div', { class: 'brand' }, [
      el('span', { class: 'brand-logo' }, [icon('logo')]),
      el('div', {}, [el('div', { class: 'brand-name', text: 'FeedWatch' }), el('div', { class: 'brand-sub', text: '가족 통합 모니터링' })]),
    ]),
    navEl, sideFoot,
  ]);
  const scrimSide = el('div', { class: 'scrim-side', hidden: true, onclick: () => toggleSidebar(false) });

  const titleEl = el('h1');
  const subEl = el('div', { class: 'sub' });
  const searchInput = el('input', { type: 'search', placeholder: '제목·출처 검색', 'aria-label': '검색' });
  searchInput.addEventListener('input', debounce(() => { state.query = searchInput.value.trim().toLowerCase(); if (isFeed()) renderView(); }, 180));
  const searchWrap = el('label', { class: 'search' }, [icon('search'), searchInput]);
  const refreshBtn = iconBtn('refresh', '새로고침', () => refresh(true));
  const themeBtn = iconBtn(themeIcon(), '테마', cycleTheme);

  const topbar = el('header', { class: 'topbar' }, [
    el('button', { class: 'icon-btn sidebar-toggle', 'aria-label': '메뉴', onclick: () => toggleSidebar() }, [icon('menu')]),
    el('div', { class: 'topbar-title' }, [titleEl, subEl]),
    el('div', { class: 'topbar-spacer' }),
    searchWrap, refreshBtn, themeBtn,
  ]);
  const subbar = el('div', { class: 'subbar' });
  const viewEl = el('main', { class: 'view', id: 'main', tabindex: '-1' });

  mount(root, el('div', { class: 'app' }, [
    sidebar, scrimSide,
    el('div', { class: 'main' }, [topbar, subbar, viewEl]),
  ]));

  /* ---------- helpers ---------- */
  function isFeed() { return state.view in FEED_VIEWS; }
  function toggleSidebar(force) { sidebarOpen = force == null ? !sidebarOpen : force; root.querySelector('.app').classList.toggle('sidebar-open', sidebarOpen); scrimSide.hidden = !sidebarOpen; }
  function themeIcon() { const p = ctx.theme.pref(); return p === 'light' ? 'sun' : p === 'dark' ? 'moon' : 'monitor'; }
  function cycleTheme() { ctx.theme.cycle(); themeBtn.replaceChildren(icon(themeIcon())); themeBtn.setAttribute('aria-label', '테마'); }
  function groupMap() { const m = {}; data.groups.forEach(g => m[g.id] = g); return m; }
  // 이미 등록된 사람의 신청(승인 절차를 거치지 않고 등록된 첫 관리자 등)은 '대기'가 아니다.
  function isRegistered(r) {
    const email = (r.email || '').toLowerCase();
    return data.users.some(u => u.id === r.uid || (u.email || '').toLowerCase() === email);
  }
  function openRequests() { return data.requests.filter(r => (r.status || 'pending') === 'pending' && !isRegistered(r)); }
  function staleRequests() { return data.requests.filter(r => (r.status || 'pending') === 'pending' && isRegistered(r)); }
  function count(statuses) { return data.items.filter(it => statuses.includes(it.status)).length; }

  /* ---------- sidebar nav ---------- */
  function renderNav() {
    const navNew = count([ITEM_STATUS.NEW]);
    const section = (label, items) => el('div', { class: 'side-section' }, [el('div', { class: 'side-label', text: label }), ...items]);
    const navItem = (id, label, ic, badge, hot) => el('button', {
      class: 'nav-item' + (state.view === id ? ' active' : ''), 'aria-current': state.view === id ? 'page' : null,
      onclick: () => go(id),
    }, [icon(ic), el('span', { style: { flex: '1' }, text: label }), badge != null ? el('span', { class: 'count' + (hot ? ' is-hot' : ''), text: String(badge) }) : null]);

    const manageItems = Object.entries(MANAGE_VIEWS)
      .filter(([, v]) => !v.adminOnly || isAdmin)
      .map(([id, v]) => {
        const badge = id === 'requests' ? openRequests().length : null;
        return navItem(id, v.label, v.icon, badge || null, id === 'requests' && badge > 0);
      });

    mount(navEl, [
      el('div', { class: 'side-section' }, [navItem('dashboard', '대시보드', 'grid', null)]),
      section('받은 글', [
        navItem('new', '신규', 'inbox2', navNew, navNew > 0),
        navItem('archive', '보관함', 'check', null),
        navItem('trash', '휴지통', 'trash', null),
      ]),
      section('관리', manageItems),
    ]);
  }

  function renderFoot() {
    const initial = (user.name || '?').trim().charAt(0) || '?';
    const btn = el('button', { class: 'profile__btn', 'aria-haspopup': 'true', 'aria-expanded': 'false' }, [
      el('span', { class: 'avatar avatar--sm chip--g0', 'aria-hidden': 'true', text: initial }),
      el('span', { class: 'profile__name', text: user.name }),
      icon('up'),
    ]);
    const items = [
      el('div', { class: 'menu__head' }, [
        el('span', { class: 'avatar avatar--sm chip--g0', 'aria-hidden': 'true', text: initial }),
        el('div', { style: { minWidth: '0' } }, [el('b', { text: user.name }), el('small', { text: user.email || (isAdmin ? '관리자' : '구성원') })]),
      ]),
      el('button', { class: 'menu__item', onclick: () => { closeMenu(); ctx.profile(); } }, [icon('user'), '내 설정']),
    ];
    if (ctx.mode === 'demo' && ctx.switchUser) {
      items.push(el('div', { class: 'menu__sep' }), el('div', { class: 'menu__label', text: '데모: 계정 전환' }));
      data.users.forEach(u => items.push(el('button', { class: 'menu__item', onclick: () => { closeMenu(); ctx.switchUser(u); } }, [
        icon(u.role === 'admin' ? 'settings' : 'user'), `${u.name} · ${u.role === 'admin' ? '관리자' : '구성원'}`,
      ])));
      items.push(el('div', { class: 'menu__sep' }));
    }
    items.push(el('button', { class: 'menu__item is-danger', onclick: () => { closeMenu(); ctx.logout(); } }, [icon('logout'), '로그아웃']));
    const menu = el('div', { class: 'menu menu--up', role: 'menu', hidden: true }, items);
    const wrap = el('div', { class: 'profile' }, [menu, btn]);
    let open = false;
    function onDoc(e) { if (!wrap.contains(e.target)) closeMenu(); }
    function closeMenu() { open = false; menu.hidden = true; btn.setAttribute('aria-expanded', 'false'); document.removeEventListener('click', onDoc); }
    btn.addEventListener('click', e => { e.stopPropagation(); open = !open; menu.hidden = !open; btn.setAttribute('aria-expanded', String(open)); if (open) document.addEventListener('click', onDoc); });
    mount(sideFoot, [wrap]);
  }

  function go(view) { state.view = view; toggleSidebar(false); renderNav(); renderTopbar(); renderSubbar(); renderView(); viewEl.scrollTop = 0; }

  /* ---------- topbar / subbar ---------- */
  function renderTopbar() {
    const v = FEED_VIEWS[state.view] || MANAGE_VIEWS[state.view]
      || (state.view === 'dashboard' ? { label: '대시보드', sub: `안녕하세요, ${user.name}님` } : null);
    titleEl.textContent = v ? v.label : 'FeedWatch';
    subEl.textContent = v ? v.sub : '';
    searchWrap.hidden = !isFeed();
  }
  function renderSubbar() {
    if (!isFeed()) { clear(subbar); subbar.hidden = true; return; }
    subbar.hidden = false;
    const gm = groupMap();
    const groupChip = (id, label, colorIdx) => el('button', {
      class: 'chip' + (state.groupId === id ? ' active' : ''), 'aria-pressed': String(state.groupId === id),
      onclick: () => { state.groupId = id; renderSubbar(); renderView(); },
    }, [id != null ? el('span', { class: 'swatch-dot', style: { background: `var(--chip-${colorIdx}-fg)` } }) : null, label]);
    const dateSeg = el('div', { class: 'seg', role: 'group', 'aria-label': '기간' },
      DATE_FILTERS.map(f => el('button', { class: 'seg__opt', 'aria-pressed': String(state.dateFilter === f.value), onclick: () => { state.dateFilter = f.value; renderSubbar(); renderView(); } }, [f.label])));
    const sortSel = el('select', { class: 'select', style: { width: 'auto', height: '32px' }, 'aria-label': '정렬', onchange: () => { state.sort = sortSel.value; renderView(); } },
      [['newest', '최신순'], ['oldest', '오래된순'], ['source', '사이트별']].map(([v, l]) => el('option', { value: v, selected: state.sort === v ? '' : null }, [l])));
    mount(subbar, [
      groupChip(null, '전체', 0),
      ...data.groups.map(g => groupChip(g.id, g.name, groupColorIndex(g, data.groups))),
      el('span', { class: 'spacer' }),
      dateSeg, sortSel,
    ]);
  }

  /* ---------- view router ---------- */
  function renderView() {
    if (!loaded) { renderSkeleton(viewEl, 6); return; }
    if (state.view === 'dashboard') return renderDashboard();
    if (isFeed()) return renderFeed();
    const panel = el('div', { class: 'view__inner' });
    mount(viewEl, panel);
    ({ sources: renderSources, groups: renderGroups, users: renderUsers, requests: renderRequests, logs: renderLogs, settings: renderSettings }[state.view] || renderFeed)(panel);
  }

  /* ---------- FEED ---------- */
  function visibleItems() {
    const v = FEED_VIEWS[state.view];
    let list = data.items.filter(it => v.statuses.includes(it.status));
    if (state.groupId) list = list.filter(it => groupsOf(it).includes(state.groupId));
    if (state.dateFilter !== 'all') list = list.filter(it => withinDateFilter(it.fetched_at, state.dateFilter));
    if (state.query) list = list.filter(it => (it.title + ' ' + it.source_name).toLowerCase().includes(state.query));
    list = [...list].sort((a, b) => (b.fetched_at || '').localeCompare(a.fetched_at || ''));
    if (state.sort === 'oldest') list.reverse();
    else if (state.sort === 'source') list.sort((a, b) => a.source_name.localeCompare(b.source_name, 'ko') || (b.fetched_at || '').localeCompare(a.fetched_at || ''));
    return list;
  }
  function statusInfo(s) {
    if (s === ITEM_STATUS.NEW) return { dot: 'new', label: '신규' };
    if (s === ITEM_STATUS.READ) return { dot: 'read', label: '읽음' };
    if (s === ITEM_STATUS.ARCHIVED) return { dot: 'pending', label: '미처리' };
    return { dot: 'deleted', label: '삭제됨' };
  }
  function itemCard(item) {
    const gm = groupMap();
    const itemGroups = groupsOf(item).map(id => gm[id]).filter(Boolean);
    const colorIdx = itemGroups.length ? groupColorIndex(itemGroups[0], data.groups) : 7;
    const st = statusInfo(item.status);
    const actions = el('div', { class: 'item__actions' });
    if (item.status === ITEM_STATUS.NEW) {
      actions.append(textBtn('check', '읽음', () => setStatus(item, ITEM_STATUS.READ, '읽음 처리했습니다.')), iconBtn('trash', '삭제', () => del(item), 'btn--icon btn--subtle btn--sm'));
    } else if (item.status === ITEM_STATUS.DELETED) {
      actions.append(textBtn('restore', '복원', () => setStatus(item, ITEM_STATUS.ARCHIVED, '보관함으로 복원했습니다.')), iconBtn('x', '완전삭제', () => purge(item), 'btn--icon btn--subtle btn--sm'));
    } else {
      actions.append(iconBtn('trash', '삭제', () => del(item), 'btn--icon btn--subtle btn--sm'));
    }
    return el('article', { class: 'item' + (item.status === ITEM_STATUS.READ ? ' is-read' : '') }, [
      el('div', { class: 'item__lead' }, [
        el('span', { class: `avatar chip--g${colorIdx}`, 'aria-hidden': 'true', text: (item.source_name || '?').trim().charAt(0) }),
        el('span', { class: `dot dot--${st.dot}`, role: 'img', 'aria-label': st.label }),
      ]),
      el('div', { class: 'item__main' }, [
        el('a', { class: 'item__title', href: item.url, target: '_blank', rel: 'noopener noreferrer' }, [item.title, ' ', icon('external', 'ic')]),
        el('div', { class: 'item__meta' }, [
          el('span', { class: 'item__src', text: item.source_name }),
          el('span', { class: 'sep', text: '·' }),
          el('span', { class: 'item__time', title: localDateTime(item.fetched_at), text: relativeTime(item.fetched_at) }),
          ...itemGroups.map(g => el('span', { class: `chip chip--g${groupColorIndex(g, data.groups)}`, text: g.name })),
          el('span', { class: 'item__url', text: prettyUrl(item.url) }),
        ]),
      ]),
      actions,
    ]);
  }
  function renderFeed(container) {
    const list = visibleItems();
    const hints = { new: '등록된 사이트에 새 글이 올라오면 여기에 표시됩니다.', archive: '읽음 처리하거나 7일이 지난 글이 모입니다.', trash: '삭제한 글이 이리로 이동합니다.' };
    const body = list.length ? el('div', { class: 'itemlist' }, list.map(itemCard)) : emptyState('표시할 항목이 없어요', hints[state.view]);
    if (container) mount(container, body); else mount(viewEl, el('div', { class: 'view__inner' }, [body]));
  }
  async function setStatus(item, status, msg) { await adapter.setItemStatus(item.id, status); if (msg) toast(msg); }
  async function del(item) { const prev = item.status; await adapter.setItemStatus(item.id, ITEM_STATUS.DELETED); toast('휴지통으로 옮겼습니다.', { actionLabel: '실행취소', onAction: () => adapter.setItemStatus(item.id, prev) }); }
  async function purge(item) { if (!(await confirmDialog({ title: '완전 삭제', message: '이 항목을 완전히 삭제할까요? 되돌릴 수 없습니다.', confirmLabel: '완전삭제', danger: true }))) return; await adapter.purgeItem(item.id); toast('완전히 삭제했습니다.', { variant: 'danger' }); }

  /* ---------- DASHBOARD (home) ---------- */
  function dashLine(it, showTime, unseen) {
    const gm = groupMap(); const gs = groupsOf(it).map(id => gm[id]).filter(Boolean);
    const g = gs[0]; const ci = g ? groupColorIndex(g, data.groups) : 7;
    return el('a', { class: 'dline' + (unseen ? ' is-unseen' : ''), href: it.url, target: '_blank', rel: 'noopener noreferrer' }, [
      el('span', { class: `avatar avatar--sm chip--g${ci}`, 'aria-hidden': 'true', text: (it.source_name || '?').trim().charAt(0) }),
      el('span', { class: 'dline__name', text: it.title }),
      unseen ? el('span', { class: 'dline__new', title: '직전 방문 이후 도착', text: 'NEW' }) : null,
      el('span', { class: 'dline__sub', text: showTime ? relativeTime(it.fetched_at) : gs.map(x => x.name).join(' · ') }),
    ]);
  }
  function renderDashboard() {
    const gm = groupMap();
    const newItems = data.items.filter(it => it.status === ITEM_STATUS.NEW);
    const pending = data.items.filter(it => it.status === ITEM_STATUS.ARCHIVED);
    const todayNew = newItems.filter(it => withinDateFilter(it.fetched_at, 'today'));
    // 고른 사이트의 글만 '내 알림'. 아무것도 고르지 않았으면 비어 있는 게 맞다(알림도 오지 않는다).
    const mySrc = user.notify_sources || [];
    const myNew = newItems.filter(it => mySrc.includes(it.source_id));
    // '내 미확인' = 내 구독 사이트의 새 글 중 직전 방문(last_seen) 이후 도착한 것
    const since = ctx.seenSince ? Date.parse(ctx.seenSince) : 0;
    const isUnseen = (it) => (Date.parse(it.fetched_at) || 0) > since;
    const myUnseen = myNew.filter(isUnseen);
    const recent = [...newItems].sort((a, b) => (b.fetched_at || '').localeCompare(a.fetched_at || '')).slice(0, 6);
    const goNew = (patch) => { Object.assign(state, { groupId: null, dateFilter: 'all', query: '' }, patch || {}); go('new'); };

    const statCard = (num, lbl, ic, klass, onClick) => el('button', { class: 'stat', onclick: onClick }, [
      el('span', { class: `stat__ico ${klass}` }, [icon(ic)]),
      el('div', { class: 'stat__num', text: String(num) }),
      el('div', { class: 'stat__lbl', text: lbl }),
    ]);
    const stats = el('div', { class: 'stat-grid' }, [
      statCard(newItems.length, '신규', 'inbox2', 'st-accent', () => goNew()),
      statCard(myUnseen.length, '내 미확인', 'bell', 'st-rose', () => goNew()),
      statCard(todayNew.length, '오늘 도착', 'clock', 'st-amber', () => goNew({ dateFilter: 'today' })),
      statCard(pending.length, '미처리 보관', 'check', 'st-blue', () => go('archive')),
    ]);

    const byGroup = el('div', { class: 'card' }, [
      el('h2', { class: 'card__title', text: '구분값별 새 글' }),
      el('div', { class: 'dlist' }, data.groups.length ? data.groups.map(g => {
        const n = newItems.filter(it => groupsOf(it).includes(g.id)).length;
        return el('button', { class: 'dline', onclick: () => goNew({ groupId: g.id }) }, [
          el('span', { class: `avatar avatar--sm chip--g${groupColorIndex(g, data.groups)}`, 'aria-hidden': 'true', text: g.name.charAt(0) }),
          el('span', { class: 'dline__name', text: g.name }),
          el('span', { class: 'count' + (n ? ' is-hot' : ''), text: String(n) }),
        ]);
      }) : [el('div', { class: 'empty__hint', text: '구분값이 없습니다.' })]),
    ]);

    const siteCounts = data.sources.map(s => ({ s, n: newItems.filter(it => it.source_id === s.id).length })).filter(x => x.n > 0).sort((a, b) => b.n - a.n).slice(0, 6);
    const bySite = el('div', { class: 'card' }, [
      el('h2', { class: 'card__title', text: '사이트별 새 글' }),
      el('div', { class: 'dlist' }, siteCounts.length ? siteCounts.map(({ s, n }) => {
        const g = gm[groupsOf(s)[0]]; const ci = g ? groupColorIndex(g, data.groups) : 7;
        return el('button', { class: 'dline', onclick: () => goNew({ query: (s.name || '').toLowerCase() }) }, [
          el('span', { class: `avatar avatar--sm chip--g${ci}`, 'aria-hidden': 'true', text: (s.name || '?').charAt(0) }),
          el('span', { class: 'dline__name', text: s.name }),
          el('span', { class: 'count is-hot', text: String(n) }),
        ]);
      }) : [el('div', { class: 'empty__hint', text: '새 글이 있는 사이트가 없습니다.' })]),
    ]);

    // 미확인 글을 위로 정렬해 '내 미확인'을 한눈에
    const myList = [...myNew].sort((a, b) => (isUnseen(b) - isUnseen(a)) || (b.fetched_at || '').localeCompare(a.fetched_at || '')).slice(0, 5);
    const myCard = el('div', { class: 'card' }, [
      el('h2', { class: 'card__title' }, ['내 알림 ', el('span', { class: 'count' + (myNew.length ? ' is-hot' : ''), text: String(myNew.length) }), myUnseen.length ? el('span', { class: 'card__badge', text: `미확인 ${myUnseen.length}` }) : null]),
      mySrc.length ? null : el('button', { class: 'banner banner--warn', style: { width: '100%', textAlign: 'left', marginBottom: '10px' }, onclick: () => ctx.profile() },
        [icon('bell'), '알림 받을 사이트를 아직 고르지 않았습니다. 눌러서 선택하세요.']),
      el('div', { class: 'dlist' }, myList.length ? myList.map(it => dashLine(it, true, isUnseen(it))) : [el('div', { class: 'empty__hint', text: '새 글이 없습니다.' })]),
    ]);

    const lastLog = data.logs[0];
    const statusCard = el('div', { class: 'card' }, [
      el('h2', { class: 'card__title', text: '수집 상태' }),
      lastLog ? el('div', {}, [
        el('div', { class: 'dstat-line' }, [icon('clock'), `마지막 수집 ${relativeTime(lastLog.run_at)}`]),
        el('div', { class: 'dstat-line' }, [icon('check'), el('span', { class: 'tag tag--on', text: `성공 ${lastLog.success_count}/${lastLog.total_sources}` }), lastLog.fail_count ? el('span', { class: 'tag tag--off', text: `실패 ${lastLog.fail_count}` }) : null, el('span', { class: 'muted', text: `· 신규 ${lastLog.new_items_count}` })]),
        el('button', { class: 'btn btn--subtle btn--sm', style: { marginTop: '8px' }, onclick: () => go('logs') }, [icon('list'), '로그 보기']),
      ]) : el('div', { class: 'empty__hint', text: '아직 수집 기록이 없습니다.' }),
    ]);

    const recentCard = el('div', { class: 'card' }, [
      el('h2', { class: 'card__title', text: '최근 새 글' }),
      el('div', { class: 'dlist' }, recent.length ? recent.map(it => dashLine(it, true, isUnseen(it))) : [el('div', { class: 'empty__hint', text: '새 글이 없습니다.' })]),
    ]);

    mount(viewEl, el('div', { class: 'dash' }, [
      el('div', { class: 'dash-hero' }, [
        el('div', { class: 'dash-hello', text: `안녕하세요, ${user.name}님 👋` }),
        el('div', { class: 'dash-date', text: `${longToday()}${lastRefreshed ? ' · 마지막 갱신 ' + lastRefreshed.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }) : ''}` }),
      ]),
      stats,
      el('div', { class: 'dash-grid' }, [
        el('div', { style: { display: 'flex', flexDirection: 'column', gap: '16px' } }, [byGroup, recentCard]),
        el('div', { style: { display: 'flex', flexDirection: 'column', gap: '16px' } }, [myCard, bySite, statusCard]),
      ]),
    ]));
  }

  /* ---------- credential passphrase ---------- */
  function ensurePassphrase() {
    const cached = sessionStorage.getItem('feedwatch_cred_pass');
    if (cached) return Promise.resolve(cached);
    return new Promise(resolve => {
      let done = false;
      const input = el('input', { class: 'input', type: 'password', placeholder: '수집 비밀번호', autocomplete: 'off' });
      openModal({
        title: '수집 비밀번호',
        body: [
          el('p', { class: 'muted', style: { margin: 0 }, text: '로그인 사이트 자격증명을 암호화할 비밀번호입니다. 크롤러 환경(FEEDWATCH_CRED_PASSPHRASE)과 같은 값이어야 하며, 저장되지 않고 이 세션에서만 기억됩니다.' }),
          field('수집 비밀번호', input),
        ],
        actions: [
          { label: '취소', variant: 'ghost', onClick: () => { done = true; resolve(null); } },
          { label: '확인', variant: 'primary', autofocus: true, onClick: () => { const v = input.value; if (!v) return false; sessionStorage.setItem('feedwatch_cred_pass', v); done = true; resolve(v); } },
        ],
        onClose: () => { if (!done) resolve(null); },
      });
    });
  }

  /* ---------- MANAGE: sources ---------- */
  function renderSources(panel) {
    const editing = state.editingSource;
    const f = {};
    f.name = el('input', { class: 'input', placeholder: '예: 연세의료원 공지' });
    f.url = el('input', { class: 'input', type: 'url', placeholder: 'https://…' });
    f.type = el('select', { class: 'select' }, SOURCE_TYPES.map(t => el('option', { value: t }, [SOURCE_TYPE_LABELS[t]])));
    f.active = el('input', { type: 'checkbox', checked: true });
    f.credUser = el('input', { class: 'input', placeholder: '로그인 아이디', autocomplete: 'off' });
    f.credPass = el('input', { class: 'input', type: 'password', placeholder: '로그인 비밀번호', autocomplete: 'new-password' });

    // 구분값: 여러 개 선택 가능(하나의 사이트를 아빠·엄마 양쪽에 넣는 식)
    const selectedGroups = new Set(groupsOf(editing || {}));
    const groupChecks = data.groups.map(g => {
      const cb = el('input', { type: 'checkbox', value: g.id, checked: selectedGroups.has(g.id) });
      return el('label', {}, [cb, g.name]);
    });
    const groupBox = data.groups.length
      ? el('div', { class: 'checkset' }, groupChecks)
      : el('small', { class: 'faint', text: '구분값이 없습니다. ‘구분값 관리’에서 먼저 추가하세요.' });

    const credStatus = el('div', { class: 'dline__sub' });
    const credBlock = el('div', { class: 'field', hidden: true }, [
      el('div', { class: 'banner banner--warn' }, [icon('key'), '이 사이트에 로그인할 때 쓰는 아이디/비밀번호입니다. 입력하면 브라우저가 ‘수집 비밀번호’로 암호화해 저장하고, 수집 프로그램만 풀어 볼 수 있습니다.']),
      isAdmin ? field('로그인 아이디', f.credUser) : el('div', { class: 'dline__sub', text: '아이디·비밀번호 입력은 관리자만 가능합니다.' }),
      isAdmin ? field('로그인 비밀번호', f.credPass) : null,
      credStatus,
    ]);

    const TYPE_HINTS = {
      general: '주소만 넣으면 새 글을 자동으로 찾아옵니다. 대부분 이걸로 끝입니다.',
      youtube: '유튜브 채널 주소(@핸들 또는 /channel/…)만 붙여넣으세요. 별도 설정 없이 최신 영상을 가져옵니다.',
      naver: '네이버 블로그는 주소만으로 됩니다. 카페는 아래 ‘자세한 설정’이 필요할 수 있습니다.',
      login_required: '로그인해야 볼 수 있는 사이트입니다. 아이디·비밀번호와 아래 ‘자세한 설정’이 필요합니다.',
    };
    const typeHint = el('small', { class: 'faint form__hint' });

    // 고급 설정 — 개발자 용어 대신 '무엇을 넣는 칸인지'로 설명한다.
    const POS_HINT = '페이지에서 그 부분이 어디인지 알려주는 주소 같은 값입니다. 아래 ‘이건 어떻게 찾나요?’를 펼쳐 보세요.';
    const ADV = {
      general: [
        { key: '@selector', label: '글 목록 위치', hint: '비워두세요. 새 글을 자동으로 못 찾을 때만 채웁니다. ' + POS_HINT, ph: '예: .board-list .title a' },
      ],
      youtube: [
        { key: 'channel_id', label: '채널 ID', hint: '비워두세요. 채널 주소로 자동 인식합니다. 자동 인식이 안 될 때만 UC로 시작하는 값을 넣습니다.', ph: 'UC…' },
        { key: 'max_items', label: '한 번에 가져올 영상 수', hint: '비우면 15개', ph: '15' },
      ],
      naver: [
        { key: 'rss_url', label: 'RSS 주소', hint: '블로그는 보통 자동으로 찾습니다. 못 찾을 때만 직접 넣으세요.', ph: 'https://rss.blog.naver.com/아이디.xml' },
        { key: 'iframe_selector', label: '카페 본문 틀', hint: '네이버 카페는 글 목록이 페이지 안의 별도 틀에 들어 있습니다. 그대로 두세요.', ph: 'iframe#cafe_main' },
        { key: '@selector', label: '글 목록 위치', hint: 'RSS가 없는 카페에서 글 제목 링크가 있는 위치. ' + POS_HINT, ph: '예: .article-board a.article' },
        { key: 'cookie', label: '로그인 쿠키', hint: '비공개 카페만 필요합니다. 없으면 비워두세요.', ph: '' },
        { key: 'max_items', label: '한 번에 가져올 글 수', hint: '비우면 30개', ph: '30' },
      ],
      login_required: [
        { key: 'username_selector', label: '아이디 입력칸 위치', hint: POS_HINT, ph: '예: #userId' },
        { key: 'password_selector', label: '비밀번호 입력칸 위치', hint: POS_HINT, ph: '예: #userPw' },
        { key: 'submit_selector', label: '로그인 버튼 위치', hint: POS_HINT, ph: '예: button[type=submit]' },
        { key: 'post_login_wait_selector', label: '로그인 성공 확인 요소', hint: '로그인 후에만 보이는 부분(예: 내 이름). 비워둬도 됩니다.', ph: '' },
        { key: '@selector', label: '글 목록 위치', hint: '로그인 후 게시판에서 글 제목 링크가 있는 위치. ' + POS_HINT, ph: '예: .board td.title a' },
      ],
    };
    const advInputs = {};                       // key -> input
    const advWrap = el('div', {});
    const meta0 = (editing && editing.metadata) || {};
    function buildAdvanced(type) {
      clear(advWrap); Object.keys(advInputs).forEach(k => delete advInputs[k]);
      (ADV[type] || []).forEach(spec => {
        const cur = spec.key === '@selector' ? (editing ? editing.selector || '' : '') : (meta0[spec.key] ?? '');
        const input = el('input', { class: 'input', placeholder: spec.ph || '', value: String(cur ?? '') });
        advInputs[spec.key] = input;
        advWrap.appendChild(field(spec.label, input, spec.hint));
      });
    }
    const helpDetails = el('details', { class: 'adv' }, [
      el('summary', {}, ['이건 어떻게 찾나요? (‘위치’ 값 찾는 법)']),
      el('div', { class: 'dline__sub', style: { lineHeight: '1.7', padding: '4px 0 10px' } }, [
        '1. 크롬에서 그 페이지를 열고 글 제목에 마우스 우클릭 → ', el('b', { text: '검사' }), ' 를 누릅니다.', el('br'),
        '2. 오른쪽에 파란색으로 표시된 줄에 다시 우클릭 → ', el('b', { text: 'Copy → Copy selector' }), ' 를 누릅니다.', el('br'),
        '3. 복사된 값을 위 칸에 붙여넣습니다.', el('br'),
        el('span', { class: 'faint', text: '어렵다면 비워두고 저장해도 됩니다. 자동으로 못 찾으면 ‘크롤링 로그’에 안내가 남습니다.' }),
      ]),
    ]);
    f.meta = el('textarea', { class: 'textarea', spellcheck: 'false' });
    f.meta.value = JSON.stringify(meta0, null, 2);
    let metaTouched = false;
    f.meta.addEventListener('input', () => { metaTouched = true; });
    const jsonDetails = el('details', { class: 'adv' }, [
      el('summary', {}, ['전문가용: 설정을 직접 편집']),
      el('div', { class: 'dline__sub', style: { padding: '0 0 8px' }, text: '여기를 고치면 위 칸 대신 이 내용이 저장됩니다. 평소에는 열지 않아도 됩니다.' }),
      f.meta,
    ]);
    const advDetails = el('details', { class: 'adv' }, [
      el('summary', {}, ['자세한 설정 (대부분 그냥 두셔도 됩니다)']),
      advWrap, helpDetails, jsonDetails,
    ]);

    const syncType = () => {
      credBlock.hidden = f.type.value !== 'login_required';
      typeHint.textContent = TYPE_HINTS[f.type.value] || '';
      buildAdvanced(f.type.value);
      advDetails.open = f.type.value === 'naver' || f.type.value === 'login_required';
    };
    f.type.addEventListener('change', syncType);

    const submitBtn = el('button', { class: 'btn btn--primary', onclick: submit }, [editing ? '수정 저장' : 'URL 등록']);
    const form = el('div', { class: 'card' }, [
      el('h2', { class: 'card__title', text: editing ? 'URL 수정' : '새 URL 등록' }),
      el('div', { class: 'form' }, [
        field('사이트명', f.name), field('URL', f.url), field('사이트 유형', f.type), typeHint,
        el('div', { class: 'field' }, [
          el('label', { class: 'field__label', text: '구분값 (여러 개 선택 가능)' }),
          groupBox,
          el('small', { class: 'faint', text: '고른 구분값 모두에서 이 사이트의 글이 보입니다.' }),
        ]),
        credBlock, advDetails,
        el('label', { class: 'checkbox' }, [f.active, '활성화 (꺼두면 수집하지 않음)']),
        el('div', { class: 'form__actions' }, [editing ? el('button', { class: 'btn btn--ghost', onclick: () => { state.editingSource = null; renderView(); } }, ['취소']) : null, submitBtn]),
      ]),
    ]);
    if (editing) {
      f.name.value = editing.name; f.url.value = editing.url;
      f.type.value = editing.type; f.active.checked = editing.active !== false;
      if (editing.type === 'login_required' && editing.credential_id) credStatus.textContent = '✓ 로그인 정보가 등록되어 있습니다. 새로 입력하면 교체됩니다.';
    }
    syncType();

    async function submit() {
      const name = f.name.value.trim(), url = f.url.value.trim();
      if (!name || !url) { toast('사이트명과 URL을 입력하세요.', { variant: 'danger' }); return; }
      const group_ids = groupChecks.filter(l => l.firstChild.checked).map(l => l.firstChild.value);
      if (!group_ids.length) { toast('구분값을 하나 이상 선택하세요.', { variant: 'danger' }); return; }
      // 자세한 설정 → metadata. 전문가용 JSON을 직접 고쳤다면 그쪽을 그대로 쓴다.
      let metadata, selector = editing ? editing.selector || '' : '';
      if (metaTouched) {
        try { metadata = JSON.parse(f.meta.value.trim() || '{}'); }
        catch { toast('직접 편집한 설정의 형식이 올바르지 않습니다.', { variant: 'danger' }); return; }
        if (advInputs['@selector']) selector = advInputs['@selector'].value.trim();
      } else {
        metadata = { ...meta0 };
        for (const [key, input] of Object.entries(advInputs)) {
          const v = input.value.trim();
          if (key === '@selector') { selector = v; continue; }
          if (v === '') delete metadata[key];
          else metadata[key] = /^(max_items)$/.test(key) ? (parseInt(v, 10) || 0) : v;
        }
      }
      const base = editing || { id: '', consecutive_failures: 0, last_error: null };
      const payload = { ...base, name, url, selector, type: f.type.value, group_ids, active: f.active.checked, metadata };
      delete payload.group_id;   // 단일 구분값 시절의 잔재 제거
      let s = await adapter.saveSource(payload);
      if (s.type === 'login_required' && isAdmin && (f.credUser.value.trim() || f.credPass.value)) {
        try {
          const pass = await ensurePassphrase();
          if (pass) {
            const { encryptSecret } = await import('../util/crypto.js');
            const cred = await adapter.saveCredential({
              id: s.credential_id || '', source_id: s.id,
              username_encrypted: await encryptSecret(pass, f.credUser.value.trim()),
              password_encrypted: await encryptSecret(pass, f.credPass.value),
            });
            s = await adapter.saveSource({ ...s, credential_id: cred.id });
          }
        } catch (e) { toast('자격증명 저장 실패: ' + (e.message || e), { variant: 'danger' }); }
      }
      toast(editing ? '수정했습니다.' : 'URL을 등록했습니다.', { variant: 'success' });
      state.editingSource = null;
    }

    const gm = groupMap();
    const rows = data.sources.length ? data.sources.map(s => {
      const srcGroups = groupsOf(s).map(id => gm[id]).filter(Boolean);
      const colorIdx = srcGroups.length ? groupColorIndex(srcGroups[0], data.groups) : 7;
      const health = (s.consecutive_failures || 0) >= 3 ? el('span', { class: 'tag tag--off', title: s.last_error || '', text: `연속실패 ${s.consecutive_failures}` }) : null;
      return el('div', { class: 'row' }, [
        el('span', { class: `avatar avatar--sm chip--g${colorIdx}`, 'aria-hidden': 'true', text: (s.name || '?').trim().charAt(0) }),
        el('div', { class: 'row__main' }, [
          el('div', { class: 'row__title' }, [s.name, el('span', { class: 'tag', text: SOURCE_TYPE_LABELS[s.type] || s.type }), el('span', { class: s.active !== false ? 'tag tag--on' : 'tag tag--off', text: s.active !== false ? 'ON' : 'OFF' }), ...srcGroups.map(g => el('span', { class: `chip chip--g${groupColorIndex(g, data.groups)}`, text: g.name })), s.type === 'login_required' ? el('span', { class: s.credential_id ? 'tag tag--on' : 'tag tag--warn', text: s.credential_id ? '로그인정보 등록됨' : '로그인정보 미등록' }) : null, health]),
          el('div', { class: 'row__sub', text: s.url }),
        ]),
        el('div', { class: 'row__actions' }, [
          iconBtn('edit', '편집', () => { state.editingSource = s; renderView(); viewEl.scrollTo({ top: 0, behavior: 'smooth' }); }),
          iconBtn(s.active !== false ? 'x' : 'check', s.active !== false ? '비활성화' : '활성화', async () => { await adapter.saveSource({ ...s, active: !(s.active !== false) }); }),
          iconBtn('trash', '삭제', async () => { if (await confirmDialog({ title: 'URL 삭제', message: `"${s.name}"을(를) 삭제할까요?`, confirmLabel: '삭제', danger: true })) { await adapter.deleteSource(s.id); toast('삭제했습니다.'); } }),
        ]),
      ]);
    }) : [emptyState('등록된 URL이 없어요', '왼쪽 양식에서 첫 모니터링 대상을 추가하세요.', 'link')];

    mount(panel, el('div', { class: 'admingrid' }, [form, el('div', { class: 'card' }, [el('h2', { class: 'card__title', text: `등록된 URL (${data.sources.length})` }), el('div', { class: 'rows' }, rows)])]));
  }

  /* ---------- MANAGE: groups ---------- */
  // 색 고르기 — 빨주노초파남보+회색. 고르지 않으면 보기 좋은 순서로 자동 배정된다.
  function colorPicker(initial) {
    let picked = Number.isInteger(initial) ? initial : null;
    const btns = GROUP_COLORS.map(c => el('button', {
      type: 'button', class: `chip chip--g${c.index}` + (picked === c.index ? ' is-picked' : ''),
      'aria-pressed': String(picked === c.index), title: c.name,
      onclick: () => { picked = c.index; btns.forEach((b, i) => { b.classList.toggle('is-picked', i === c.index); b.setAttribute('aria-pressed', String(i === c.index)); }); },
    }, [c.name]));
    return { node: el('div', { class: 'checkset' }, btns), get: () => picked };
  }

  function renderGroups(panel) {
    const name = el('input', { class: 'input', placeholder: '새 구분값 이름 (예: 아빠)' });
    const picker = colorPicker(null);
    const add = async () => {
      const v = name.value.trim(); if (!v) return;
      const payload = { id: '', name: v, order: data.groups.length + 1 };
      if (picker.get() != null) payload.color_index = picker.get();
      await adapter.saveGroup(payload);
      name.value = '';
      toast('구분값을 추가했습니다.', { variant: 'success' });
    };
    name.addEventListener('keydown', e => { if (e.key === 'Enter') add(); });
    const rows = data.groups.map((g, i) => el('div', { class: 'row' }, [
      el('span', { class: `avatar avatar--sm chip--g${groupColorIndex(g, data.groups)}`, 'aria-hidden': 'true', text: g.name.charAt(0) }),
      el('div', { class: 'row__main' }, [
        el('div', { class: 'row__title' }, [`${g.order}. ${g.name}`, el('span', { class: `chip chip--g${groupColorIndex(g, data.groups)}`, text: groupColorName(groupColorIndex(g, data.groups)) })]),
      ]),
      el('div', { class: 'row__actions' }, [
        iconBtn('up', '위로', () => move(i, -1), 'btn--icon btn--subtle btn--sm'),
        iconBtn('down', '아래로', () => move(i, 1), 'btn--icon btn--subtle btn--sm'),
        iconBtn('edit', '이름·색', () => editGroup(g)),
        iconBtn('trash', '삭제', () => removeGroup(g), 'btn--icon btn--subtle btn--sm'),
      ]),
    ]));
    mount(panel, el('div', { class: 'card', style: { maxWidth: '640px' } }, [
      el('h2', { class: 'card__title', text: '구분값 관리' }),
      el('div', { class: 'form', style: { marginBottom: '18px' } }, [
        field('새 구분값 이름', name),
        el('div', { class: 'field' }, [
          el('label', { class: 'field__label', text: '색 (고르지 않으면 자동)' }),
          picker.node,
        ]),
        el('div', { class: 'form__actions' }, [el('button', { class: 'btn btn--primary', onclick: add }, [icon('plus'), '추가'])]),
      ]),
      el('div', { class: 'rows' }, rows),
    ]));
    async function move(i, dir) { const j = i + dir; if (j < 0 || j >= data.groups.length) return; const ids = data.groups.map(g => g.id); [ids[i], ids[j]] = [ids[j], ids[i]]; await adapter.reorderGroups(ids); }
    function editGroup(g) {
      const input = el('input', { class: 'input', value: g.name });
      const picker = colorPicker(groupColorIndex(g, data.groups));
      openModal({
        title: '구분값 수정',
        body: [field('이름', input), el('div', { class: 'field' }, [el('label', { class: 'field__label', text: '색' }), picker.node])],
        actions: [
          { label: '취소', variant: 'ghost' },
          { label: '저장', variant: 'primary', autofocus: true, onClick: async () => {
            const v = input.value.trim(); if (!v) return false;
            const patch = { ...g, name: v, color_index: picker.get() ?? groupColorIndex(g, data.groups) };
            delete patch.colorIndex;
            await adapter.saveGroup(patch);
            toast('수정했습니다.', { variant: 'success' });
          } },
        ],
      });
    }
    async function removeGroup(g) {
      if (data.sources.some(s => groupsOf(s).includes(g.id))) { toast('이 구분값에 연결된 URL이 있어 삭제할 수 없습니다.', { variant: 'danger' }); return; }
      if (!(await confirmDialog({ title: '구분값 삭제', message: `"${g.name}"을(를) 삭제할까요?`, confirmLabel: '삭제', danger: true }))) return;
      try { await adapter.deleteGroup(g.id); toast('삭제했습니다.'); } catch (e) { toast(e.message, { variant: 'danger' }); }
    }
  }

  /* ---------- MANAGE: users ---------- */
  function renderUsers(panel) {
    const email = el('input', { class: 'input', type: 'email', placeholder: '가족 이메일' });
    const name = el('input', { class: 'input', placeholder: '이름' });
    const role = el('select', { class: 'select' }, [el('option', { value: 'member' }, ['구성원']), el('option', { value: 'admin' }, ['관리자'])]);
    const add = async () => {
      const e = email.value.trim(); if (!e) { toast('이메일을 입력하세요.', { variant: 'danger' }); return; }
      if (data.users.some(u => u.email.toLowerCase() === e.toLowerCase())) { toast('이미 등록된 이메일입니다.', { variant: 'danger' }); return; }
      await adapter.saveUser({ id: '', email: e, name: name.value.trim() || e.split('@')[0], role: role.value, notify_email: true, notify_sources: [] });
      toast('사용자를 추가했습니다.', { variant: 'success' });
    };
    const rows = data.users.map(u => {
      const sites = u.notify_sources || []; const notifyText = !u.notify_email ? '알림 꺼짐' : (sites.length ? `${sites.length}개 사이트 알림` : '알림 받을 사이트 미선택');
      return el('div', { class: 'row' }, [
        el('span', { class: 'avatar avatar--sm chip--g0', 'aria-hidden': 'true', text: (u.name || '?').trim().charAt(0) }),
        el('div', { class: 'row__main' }, [
          el('div', { class: 'row__title' }, [u.name, el('span', { class: 'tag', text: u.role === 'admin' ? '관리자' : '구성원' }), el('span', { class: u.notify_email ? 'tag tag--on' : 'tag tag--off', text: u.notify_email ? '알림 ON' : '알림 OFF' })]),
          el('div', { class: 'row__sub', text: `${u.email} · ${notifyText}` }),
        ]),
        el('div', { class: 'row__actions' }, [iconBtn('edit', '편집', () => editUser(u)), iconBtn('trash', '삭제', () => removeUser(u), 'btn--icon btn--subtle btn--sm')]),
      ]);
    });
    mount(panel, el('div', { class: 'admingrid' }, [
      el('div', { class: 'card' }, [el('h2', { class: 'card__title', text: '사용자 추가' }), el('div', { class: 'form' }, [field('이메일', email), field('이름', name), field('권한', role), el('div', { class: 'form__actions' }, [el('button', { class: 'btn btn--primary', onclick: add }, [icon('plus'), '추가'])])])]),
      el('div', { class: 'card' }, [el('h2', { class: 'card__title', text: `가족 구성원 (${data.users.length})` }), el('div', { class: 'rows' }, rows)]),
    ]));
    function editUser(u) {
      const nm = el('input', { class: 'input', value: u.name });
      const rl = el('select', { class: 'select' }, [el('option', { value: 'member' }, ['구성원']), el('option', { value: 'admin' }, ['관리자'])]);
      rl.value = u.role === 'admin' ? 'admin' : 'member';   // 예상 밖 값이면 select가 조용히 첫 항목(구성원)으로 떨어지는 것 방지
      const notify = el('input', { type: 'checkbox', checked: !!u.notify_email });
      const picker = sourceCheckset(data.sources, u.notify_sources || []);
      openModal({ title: `${u.name} 설정`, body: [field('이름', nm), field('권한', rl), el('label', { class: 'checkbox' }, [notify, '이메일 알림 받기']), el('div', { class: 'field' }, [el('label', { class: 'field__label', text: '알림 받을 사이트' }), picker.node])],
        actions: [{ label: '취소', variant: 'ghost' }, { label: '저장', variant: 'primary', autofocus: true, onClick: async () => {
          if (u.role === 'admin' && rl.value !== 'admin' && data.users.filter(x => x.role === 'admin').length <= 1) { toast('마지막 관리자는 권한을 바꿀 수 없습니다.', { variant: 'danger' }); return false; }
          const notify_sources = picker.get();
          await adapter.saveUser({ ...u, name: nm.value.trim() || u.name, role: rl.value, notify_email: notify.checked, notify_sources }); toast('저장했습니다.', { variant: 'success' });
        } }] });
    }
    async function removeUser(u) {
      if (u.id === user.id) { toast('현재 로그인한 본인은 삭제할 수 없습니다.', { variant: 'danger' }); return; }
      if (u.role === 'admin' && data.users.filter(x => x.role === 'admin').length <= 1) { toast('마지막 관리자는 삭제할 수 없습니다.', { variant: 'danger' }); return; }
      if (!(await confirmDialog({ title: '사용자 삭제', message: `"${u.name}"을(를) 삭제할까요?`, confirmLabel: '삭제', danger: true }))) return;
      await adapter.deleteUser(u.id); toast('삭제했습니다.');
    }
  }

  /* ---------- MANAGE: requests ---------- */
  function renderRequests(panel) {
    const pending = openRequests();
    const stale = staleRequests();
    const pl = p => p === 'google' ? 'Google' : (p === 'password' ? '이메일' : (p || '기타'));
    const rows = pending.length ? pending.map(r => el('div', { class: 'row' }, [
      el('span', { class: 'avatar avatar--sm chip--g3', 'aria-hidden': 'true', text: (r.name || r.email || '?').trim().charAt(0) }),
      el('div', { class: 'row__main' }, [el('div', { class: 'row__title' }, [r.name || r.email, el('span', { class: 'tag', text: pl(r.provider) })]), el('div', { class: 'row__sub', text: `${r.email} · ${relativeTime(r.requested_at)} 신청` })]),
      el('div', { class: 'row__actions' }, [el('button', { class: 'btn btn--primary btn--sm', onclick: async () => { await adapter.approveRequest(r.id, { role: 'member' }); toast(`${r.name || r.email} 님을 승인했습니다.`, { variant: 'success' }); } }, [icon('check'), '승인']), iconBtn('x', '거절', async () => { if (await confirmDialog({ title: '가입 신청 거절', message: `${r.name || r.email} 님의 신청을 거절할까요?`, confirmLabel: '거절', danger: true })) { await adapter.deleteRequest(r.id); toast('거절했습니다.'); } }, 'btn--icon btn--subtle btn--sm')]),
    ])) : [emptyState('대기 중인 가입 신청이 없어요', '미등록 계정이 로그인하면 신청이 여기에 표시됩니다.', 'user')];
    const staleBar = stale.length ? el('div', { class: 'banner banner--warn', style: { marginTop: '12px' } }, [
      icon('alert'),
      el('span', { style: { flex: '1' }, text: `이미 가입된 계정의 오래된 신청 ${stale.length}건이 남아 있습니다(${stale.map(r => r.email).join(', ')}). 승인·거절할 필요 없이 정리하면 됩니다.` }),
      el('button', { class: 'btn btn--subtle btn--sm', onclick: async () => {
        for (const r of stale) { try { await adapter.deleteRequest(r.id); } catch (e) { toast(e.message || '정리에 실패했습니다.', { variant: 'danger' }); return; } }
        toast(`${stale.length}건을 정리했습니다.`, { variant: 'success' });
      } }, ['정리']),
    ]) : null;
    mount(panel, el('div', { class: 'card', style: { maxWidth: '680px' } }, [el('h2', { class: 'card__title', text: `가입 신청 (${pending.length})` }), el('div', { class: 'banner' }, [icon('user'), '승인하면 구성원으로 추가됩니다. 관리자 권한은 사용자 관리에서 바꿀 수 있어요.']), staleBar, el('div', { class: 'rows', style: { marginTop: '14px' } }, rows)]));
  }

  /* ---------- MANAGE: logs ---------- */
  function renderLogs(panel) {
    const bar = ctx.mode === 'cloud'
      ? el('div', { class: 'banner' }, [icon('play'), '수동 크롤링은 GitHub Actions의 FeedWatch Crawl 워크플로 "Run workflow"로 실행합니다. 인트라넷 대상은 로컬에서 python -m crawler.main_crawler.'])
      : el('div', { class: 'banner banner--warn' }, [icon('alert'), '데모 모드에는 실제 크롤러가 없습니다. 아래는 샘플 실행 기록입니다.']);
    const rows = data.logs.length ? data.logs.map(log => el('div', { class: 'row' }, [
      el('div', { class: 'logline' }, [el('b', { text: localDateTime(log.run_at) }), el('span', { class: 'muted', text: relativeTime(log.run_at) }), el('span', { class: 'tag', text: `신규 ${log.new_items_count}` }), el('span', { class: 'tag tag--on', text: `성공 ${log.success_count}/${log.total_sources}` }), log.fail_count ? el('span', { class: 'tag tag--off', text: `실패 ${log.fail_count}` }) : null, el('span', { class: 'muted', text: `${(log.duration_seconds || 0).toFixed(1)}s` })]),
      (log.failed_sources || []).length ? el('div', {}, Object.entries(log.error_messages || {}).map(([sid, m]) => { const s = data.sources.find(x => x.id === sid); return el('div', { class: 'logfail' }, [el('b', { text: (s ? s.name : sid) + ': ' }), m]); })) : null,
    ])) : [emptyState('아직 크롤링 로그가 없어요', null, 'list')];
    mount(panel, el('div', { class: 'card' }, [el('h2', { class: 'card__title', text: '크롤링 로그' }), bar, el('div', { class: 'rows loglist', style: { marginTop: '14px' } }, rows)]));
  }

  /* ---------- MANAGE: settings ---------- */
  function renderSettings(panel) {
    const c = data.config;
    const days = el('input', { class: 'input', type: 'number', min: '1', max: '365', value: String(c.auto_archive_days ?? 7) });
    const trash = el('input', { class: 'input', type: 'number', min: '0', max: '365', value: String(c.trash_retention_days ?? 30) });
    const emailEnabled = el('input', { type: 'checkbox', checked: c.email_enabled !== false });
    const provider = el('select', { class: 'select' }, [['', '자동 (크롤러 환경설정 사용) · 권장'], ['preview', '미리보기 (HTML 파일)'], ['smtp', 'SMTP'], ['gmail', 'Gmail API']].map(([v, l]) => el('option', { value: v }, [l]))); provider.value = c.email_provider || '';
    const save = async () => { await adapter.saveConfig({ auto_archive_days: Math.max(1, Number(days.value) || 7), trash_retention_days: Math.max(0, parseInt(trash.value, 10) || 0), email_enabled: emailEnabled.checked, email_provider: provider.value }); toast('설정을 저장했습니다.', { variant: 'success' }); };
    const diag = el('pre', { class: 'diag' });
    const ln = (l, v, cls) => el('span', {}, [`${l}: `, el('span', { class: cls, text: v }), '\n']);
    diag.append(ln('모드', ctx.mode === 'cloud' ? 'CLOUD (Firestore)' : 'DEMO (로컬 샘플)', 'ok'), ln('자동 보관 기간', `${c.auto_archive_days ?? 7}일`, 'ok'), ln('휴지통 보관', `${c.trash_retention_days ?? 30}일`, 'ok'), ln('이메일 알림', c.email_enabled === false ? '꺼짐' : `켜짐 · ${c.email_provider || '크롤러 환경설정'}`, c.email_enabled === false ? 'warn' : 'ok'),ln('등록 URL', `${data.sources.length}개 (활성 ${data.sources.filter(s => s.active !== false).length})`, 'ok'), ln('구성원', `${data.users.length}명`, 'ok'), ln('알림 수신', `${data.users.filter(u => u.notify_email).length}명`, 'ok'));
    mount(panel, el('div', { class: 'admingrid' }, [
      el('div', { class: 'card' }, [el('h2', { class: 'card__title', text: '동작 설정' }), el('div', { class: 'form' }, [field('자동 보관 기간 (일)', days, '신규가 이 기간 미처리되면 보관함(미처리)으로 자동 이동합니다.'), field('휴지통 보관 기간 (일)', trash, '삭제한 글을 이 기간 후 영구 삭제합니다(클라우드 크롤러 실행 시). 0이면 자동 삭제 안 함.'), el('label', { class: 'checkbox' }, [emailEnabled, '새 글 이메일 알림 발송']), field('이메일 발송 방식', provider, '‘자동’이면 크롤러 환경(.env / GitHub Secrets)의 EMAIL_PROVIDER를 그대로 씁니다. 발송 계정·비밀번호도 그곳에서 설정합니다.'), el('div', { class: 'form__actions' }, [el('button', { class: 'btn btn--primary', onclick: save }, ['설정 저장'])])])]),
      el('div', { class: 'card' }, [el('h2', { class: 'card__title', text: '환경 진단' }), diag, ctx.mode === 'demo' ? el('button', { class: 'btn btn--ghost', style: { marginTop: '12px' }, onclick: async () => { if (await confirmDialog({ title: '데모 초기화', message: '데모 데이터를 처음 상태로 되돌릴까요?', confirmLabel: '초기화', danger: true })) { adapter.resetDemo && adapter.resetDemo(); location.reload(); } } }, [icon('refresh'), '데모 데이터 초기화']) : null]),
    ]));
  }

  /* ---------- data / boot ---------- */
  async function refresh(manual) {
    [data.groups, data.sources, data.items, data.users, data.logs, data.config] = await Promise.all([
      adapter.listGroups(), adapter.listSources(), adapter.listItems(), adapter.listUsers(), adapter.listLogs(), adapter.getConfig(),
    ]);
    data.requests = adapter.listRequests ? await adapter.listRequests() : [];
    loaded = true; lastRefreshed = new Date();
    renderNav(); renderFoot(); renderTopbar(); renderSubbar(); renderView();
    if (manual) toast('새로고침했습니다.');
  }

  renderNav(); renderFoot(); renderTopbar(); renderSubbar(); renderSkeleton(viewEl, 6);
  refresh();
  const unsub = adapter.subscribe(debounce(() => refresh(false), 60));
  return () => unsub();
}

/* ---------- shared small helpers ---------- */
function iconBtn(name, label, onclick, extra = 'icon-btn') {
  if (extra.includes('icon-btn')) return el('button', { class: extra, type: 'button', 'aria-label': label, title: label, onclick }, [icon(name)]);
  return el('button', { class: `btn ${extra}`, type: 'button', 'aria-label': label, title: label, onclick }, [icon(name)]);
}
function textBtn(name, label, onclick) { return el('button', { class: 'btn btn--sm btn--subtle', type: 'button', onclick }, [icon(name), label]); }
function prettyUrl(url) { try { const u = new URL(url); return u.hostname.replace(/^www\./, '') + (u.pathname !== '/' ? u.pathname : ''); } catch { return url; } }
function longToday() { try { return new Date().toLocaleDateString('ko-KR', { month: 'long', day: 'numeric', weekday: 'long' }); } catch { return ''; } }
