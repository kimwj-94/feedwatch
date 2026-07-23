// Time / date / text formatting helpers (Korean-first, local timezone).

export function parseDate(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  return isNaN(d.getTime()) ? null : d;
}

// "방금 전", "3분 전", "5시간 전", "2일 전", then absolute date.
export function relativeTime(iso, now = new Date()) {
  const d = parseDate(iso);
  if (!d) return '-';
  const sec = Math.round((now - d) / 1000);
  if (sec < 0) return '곧';
  if (sec < 45) return '방금 전';
  const min = Math.round(sec / 60);
  if (min < 60) return `${min}분 전`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}시간 전`;
  const day = Math.round(hr / 24);
  if (day < 7) return `${day}일 전`;
  if (day < 31) return `${Math.round(day / 7)}주 전`;
  return localDate(iso);
}

// Local absolute timestamp, e.g. "2026-06-17 14:30"
export function localDateTime(iso) {
  const d = parseDate(iso);
  if (!d) return '-';
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

export function localDate(iso) {
  const d = parseDate(iso);
  if (!d) return '-';
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

// Date filter used in the dashboard toolbar.
// values: 'all' | 'today' | 'd1' | 'd2' | 'd3' | 'week'
const DAY = 86400000;
export function withinDateFilter(iso, filter, now = new Date()) {
  if (!filter || filter === 'all') return true;
  const d = parseDate(iso);
  if (!d) return false;
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const ageFromToday = startOfToday - new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  switch (filter) {
    case 'today': return ageFromToday <= 0;          // today or future
    case 'd1': return ageFromToday <= 1 * DAY;
    case 'd2': return ageFromToday <= 2 * DAY;
    case 'd3': return ageFromToday <= 3 * DAY;
    case 'week': return (now - d) <= 7 * DAY;
    default: return true;
  }
}

export const DATE_FILTERS = [
  { value: 'all', label: '전체' },
  { value: 'today', label: '오늘' },
  { value: 'd1', label: 'D+1' },
  { value: 'd2', label: 'D+2' },
  { value: 'd3', label: 'D+3' },
  { value: 'week', label: '일주일' },
];

// 구분값 색 팔레트 — tokens.css의 --chip-N-* 과 순서가 같아야 한다(저장값이 인덱스라 순서 고정).
export const GROUP_COLORS = [
  { index: 0, name: '빨강' },
  { index: 1, name: '주황' },
  { index: 2, name: '노랑' },
  { index: 3, name: '초록' },
  { index: 4, name: '파랑' },
  { index: 5, name: '남색' },
  { index: 6, name: '보라' },
  { index: 7, name: '회색' },
];

// 색을 직접 고르지 않았을 때 자동으로 배정되는 순서.
// 빨강·주황은 이 앱에서 오류·경고 표시색과 겹쳐 오해를 부르므로 뒤로 미룬다.
const AUTO_ORDER = [4, 3, 6, 5, 2, 7, 1, 0];   // 파랑 → 초록 → 보라 → 남색 → 노랑 → 회색 → 주황 → 빨강

export function groupColorName(i) { return (GROUP_COLORS[((i % 8) + 8) % 8] || {}).name || ''; }

// Stable color index (0..7) for a group, by id.
// 저장 필드는 다른 모델과 같은 snake_case(color_index). colorIndex는 옛 데이터 호환.
export function groupColorIndex(group, allGroups = []) {
  const picked = group && (Number.isInteger(group.color_index) ? group.color_index : group.colorIndex);
  if (Number.isInteger(picked)) return ((picked % 8) + 8) % 8;
  const idx = allGroups.findIndex(g => g.id === (group && group.id));
  if (idx >= 0) return AUTO_ORDER[idx % 8];
  // fallback: hash the id
  const s = (group && group.id) || '';
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return AUTO_ORDER[h % 8];
}

export function pluralCount(n) { return new Intl.NumberFormat('ko-KR').format(n); }
