// Reusable UI primitives: toast (with undo), modal, confirm dialog.
import { el, mount, trapFocus } from '../util/dom.js';
import { icon } from '../util/icons.js';

let toastHost;
function host() {
  if (!toastHost) {
    toastHost = el('div', { class: 'toasts', id: 'toasts', role: 'status', 'aria-live': 'polite', 'aria-atomic': 'false' });
    document.body.appendChild(toastHost);
  }
  return toastHost;
}

// toast(message, { variant, actionLabel, onAction, timeout })
export function toast(message, opts = {}) {
  const { variant, actionLabel, onAction, timeout = 5000 } = opts;
  const node = el('div', { class: 'toast' + (variant ? ` toast--${variant}` : '') }, [
    el('span', { class: 'toast__msg', text: message }),
  ]);
  let timer;
  const dismiss = () => { clearTimeout(timer); node.remove(); };
  if (actionLabel) {
    node.appendChild(el('button', {
      class: 'toast__action', type: 'button',
      onclick: () => { dismiss(); onAction && onAction(); },
    }, [actionLabel]));
  }
  node.appendChild(el('button', {
    class: 'toast__action', type: 'button', 'aria-label': '닫기',
    onclick: dismiss,
  }, [icon('x')]));
  host().appendChild(node);
  if (timeout) timer = setTimeout(dismiss, timeout);
  return { dismiss };
}

// openModal({ title, body:Node|Node[], actions:[{label, variant, onClick, autofocus, closeOnClick}] })
export function openModal({ title, body, actions = [], onClose } = {}) {
  const previous = document.activeElement;
  const panel = el('div', { class: 'modal__panel', role: 'dialog', 'aria-modal': 'true', 'aria-label': title || '대화상자' });
  const overlay = el('div', { class: 'modal' }, [
    el('div', { class: 'modal__backdrop', onclick: () => close() }),
    panel,
  ]);

  if (title) panel.appendChild(el('h2', { class: 'modal__title', text: title }));
  const bodyWrap = el('div', { class: 'modal__body' });
  if (body) (Array.isArray(body) ? body : [body]).forEach(b => bodyWrap.appendChild(b));
  panel.appendChild(bodyWrap);

  const foot = el('div', { class: 'modal__foot' });
  let autofocusNode;
  actions.forEach(a => {
    const btn = el('button', {
      class: 'btn' + (a.variant ? ` btn--${a.variant}` : ''), type: 'button',
      onclick: () => { if (a.onClick && a.onClick() === false) return; if (a.closeOnClick !== false) close(); },
    }, [a.label]);
    if (a.autofocus) autofocusNode = btn;
    foot.appendChild(btn);
  });
  if (actions.length) panel.appendChild(foot);

  const untrap = trapFocus(panel);
  function onKey(e) { if (e.key === 'Escape') close(); }
  document.addEventListener('keydown', onKey);

  function close() {
    untrap();
    document.removeEventListener('keydown', onKey);
    overlay.remove();
    onClose && onClose();
    if (previous && previous.focus) previous.focus();
  }

  document.body.appendChild(overlay);
  setTimeout(() => (autofocusNode || panel.querySelector('input,select,textarea,button'))?.focus(), 0);
  return { close, panel, bodyWrap };
}

export function confirmDialog({ title = '확인', message, confirmLabel = '확인', cancelLabel = '취소', danger = false } = {}) {
  return new Promise(resolve => {
    let decided = false;
    const m = openModal({
      title,
      body: el('p', { class: 'muted', text: message, style: { margin: 0 } }),
      actions: [
        { label: cancelLabel, variant: 'ghost', onClick: () => { decided = true; resolve(false); } },
        { label: confirmLabel, variant: danger ? 'danger' : 'primary', autofocus: true, onClick: () => { decided = true; resolve(true); } },
      ],
      onClose: () => { if (!decided) resolve(false); },
    });
    void m;
  });
}

// Replace a container's content with N skeleton cards.
export function renderSkeleton(container, n = 4) {
  mount(container, Array.from({ length: n }, () =>
    el('div', { class: 'skel' }, [
      el('div', { class: 'skel__av' }),
      el('div', { class: 'skel__lines' }, [
        el('div', { class: 'skel--line sm' }),
        el('div', { class: 'skel--line md' }),
      ]),
    ])
  ));
}

export function emptyState(title, hint, iconName = 'inbox2') {
  return el('div', { class: 'empty' }, [
    el('div', { class: 'empty__icon' }, [icon(iconName)]),
    el('div', { class: 'empty__title', text: title }),
    hint ? el('div', { class: 'empty__hint', text: hint }) : null,
  ]);
}

// 알림 받을 사이트 고르기 — '내 설정'과 '사용자 관리 → 편집'이 같은 UI를 쓴다.
// 아무것도 고르지 않으면 알림을 받지 않는다(빈 목록 = 전체가 아님).
export function sourceCheckset(sources, selected = []) {
  const chosen = new Set(selected);
  const boxes = sources.map(s => {
    const cb = el('input', { type: 'checkbox', value: s.id, checked: chosen.has(s.id) });
    return el('label', {}, [cb, s.name]);
  });
  const summary = el('small', { class: 'faint' });
  const sync = () => {
    const n = boxes.filter(l => l.firstChild.checked).length;
    summary.textContent = n ? `${n}개 사이트에서 알림을 받습니다.` : '고른 사이트가 없어 알림을 받지 않습니다.';
  };
  boxes.forEach(l => l.firstChild.addEventListener('change', sync));
  const setAll = (v) => { boxes.forEach(l => l.firstChild.checked = v); sync(); };
  sync();

  const node = sources.length
    ? el('div', {}, [
        el('div', { class: 'adv__row', style: { marginBottom: '10px', gap: '8px' } }, [
          summary,
          el('div', { style: { display: 'flex', gap: '6px', flex: 'none' } }, [
            el('button', { class: 'btn btn--subtle btn--sm', type: 'button', onclick: () => setAll(true) }, ['전체 선택']),
            el('button', { class: 'btn btn--subtle btn--sm', type: 'button', onclick: () => setAll(false) }, ['전체 해제']),
          ]),
        ]),
        el('div', { class: 'checkset' }, boxes),
      ])
    : el('small', { class: 'faint', text: '등록된 사이트가 없습니다. 먼저 URL 관리에서 사이트를 추가하세요.' });

  return { node, get: () => boxes.filter(l => l.firstChild.checked).map(l => l.firstChild.value) };
}

// Labeled form field (optional hint). Shared by dashboard/admin/login.
export function field(label, control, hint) {
  return el('div', { class: 'field' }, [
    el('label', { class: 'field__label', text: label }),
    control,
    hint ? el('small', { class: 'faint', text: hint }) : null,
  ]);
}
