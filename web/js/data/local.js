// Demo / offline adapter: seeds from sample/feedwatch_sample.json, keeps working
// state in localStorage, and re-bases sample timestamps to "now" so the demo always
// looks fresh. Mirrors LocalJsonRepository in shared/repository.py.
import { Adapter, DEFAULT_CONFIG, ITEM_STATUS, newId, nowIso } from './adapter.js';

const STORE_KEY = 'feedwatch_demo_v1';
const TS_FIELDS = {
  items: ['fetched_at', 'read_at', 'deleted_at', 'auto_archived_at'],
  users: ['created_at', 'last_login', 'last_seen'],
  groups: ['created_at'],
  sources: ['created_at', 'updated_at'],
  crawl_logs: ['run_at'],
  access_requests: ['requested_at'],
};

function shiftTs(iso, deltaMs) {
  if (!iso) return iso;
  const t = Date.parse(iso);
  return isNaN(t) ? iso : new Date(t + deltaMs).toISOString();
}

function rebase(data) {
  const base = Date.parse(data._generated_at || '');
  if (isNaN(base)) return data;
  const delta = Date.now() - base;
  for (const [coll, fields] of Object.entries(TS_FIELDS)) {
    for (const row of data[coll] || []) for (const f of fields) if (row[f]) row[f] = shiftTs(row[f], delta);
  }
  return data;
}

export class LocalAdapter extends Adapter {
  constructor(data) {
    super();
    this.mode = 'demo';
    this.isCloud = false;
    this.data = data;
  }

  static async create() {
    const saved = localStorage.getItem(STORE_KEY);
    if (saved) {
      try { return new LocalAdapter(JSON.parse(saved)); } catch { /* fall through to reseed */ }
    }
    const res = await fetch(new URL('../../sample/feedwatch_sample.json', import.meta.url), { cache: 'no-store' });
    if (!res.ok) throw new Error('샘플 데이터를 불러오지 못했습니다 (' + res.status + ')');
    const data = rebase(await res.json());
    const adapter = new LocalAdapter(data);
    adapter._persist();
    return adapter;
  }

  _persist() { localStorage.setItem(STORE_KEY, JSON.stringify(this.data)); }
  _commit() { this._persist(); this._emit(); }
  _clone(x) { return JSON.parse(JSON.stringify(x)); }

  resetDemo() { localStorage.removeItem(STORE_KEY); }

  // ---- groups ----
  async listGroups() { return this._clone(this.data.groups).sort((a, b) => a.order - b.order); }
  async saveGroup(group) {
    const g = { ...group };
    if (!g.id) { g.id = newId('group'); g.created_at = nowIso(); }
    this.data.groups = this.data.groups.filter(x => x.id !== g.id).concat(g);
    this._commit();
    return g;
  }
  async deleteGroup(id) {
    if (this.data.sources.some(s => (s.group_ids || (s.group_id ? [s.group_id] : [])).includes(id))) throw new Error('이 구분값에 연결된 URL이 있어 삭제할 수 없습니다.');
    this.data.groups = this.data.groups.filter(x => x.id !== id);
    this._commit();
  }
  async reorderGroups(orderedIds) {
    orderedIds.forEach((id, i) => { const g = this.data.groups.find(x => x.id === id); if (g) g.order = i + 1; });
    this._commit();
  }

  // ---- sources ----
  async listSources() { return this._clone(this.data.sources).sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || '')); }
  async saveSource(source) {
    const s = { ...source };
    if (!s.id) { s.id = newId('src'); s.created_at = nowIso(); }
    s.updated_at = nowIso();
    if (s.consecutive_failures == null) s.consecutive_failures = 0;
    this.data.sources = this.data.sources.filter(x => x.id !== s.id).concat(s);
    this._commit();
    return s;
  }
  async deleteSource(id) {
    this.data.sources = this.data.sources.filter(x => x.id !== id);
    this.data.credentials = (this.data.credentials || []).filter(c => c.source_id !== id);
    this._commit();
  }
  async saveCredential(cred) {
    const c = { ...cred };
    if (!c.id) c.id = newId('cred');
    c.updated_at = nowIso();
    this.data.credentials = (this.data.credentials || []).filter(x => x.id !== c.id).concat(c);
    this._commit();
    return c;
  }

  // ---- items ----
  async listItems() { return this._clone(this.data.items).sort((a, b) => (b.fetched_at || '').localeCompare(a.fetched_at || '')); }
  async setItemStatus(id, status) {
    const it = this.data.items.find(x => x.id === id);
    if (!it) return;
    it.status = status;
    const now = nowIso();
    if (status === ITEM_STATUS.READ) it.read_at = now;
    if (status === ITEM_STATUS.DELETED) it.deleted_at = now;
    if (status === ITEM_STATUS.ARCHIVED) it.auto_archived_at = now;
    this._commit();
  }
  async purgeItem(id) { this.data.items = this.data.items.filter(x => x.id !== id); this._commit(); }

  // ---- users ----
  async listUsers() { return this._clone(this.data.users); }
  async saveUser(user) {
    const u = { ...user };
    if (!u.id) { u.id = newId('user'); u.created_at = nowIso(); }
    this.data.users = this.data.users.filter(x => x.id !== u.id).concat(u);
    this._commit();
    return u;
  }
  async deleteUser(id) { this.data.users = this.data.users.filter(x => x.id !== id); this._commit(); }

  // ---- logs / config ----
  async listLogs() { return this._clone(this.data.crawl_logs || []).sort((a, b) => (b.run_at || '').localeCompare(a.run_at || '')).slice(0, 50); }
  async getConfig() { return { ...DEFAULT_CONFIG, ...(this.data.app_config || {}) }; }
  async saveConfig(patch) {
    this.data.app_config = { ...DEFAULT_CONFIG, ...(this.data.app_config || {}), ...patch };
    this._commit();
    return this.data.app_config;
  }

  // ---- access requests (가입 신청) ----
  async listRequests() {
    return this._clone(this.data.access_requests || []).sort((a, b) => (b.requested_at || '').localeCompare(a.requested_at || ''));
  }
  async createRequest({ email, name, provider, uid }) {
    this.data.access_requests = this.data.access_requests || [];
    const found = this.data.access_requests.find(r => (r.email || '').toLowerCase() === (email || '').toLowerCase());
    if (found) return found;
    const req = { id: newId('req'), email, name: name || (email || '').split('@')[0], provider: provider || 'demo', uid: uid || null, requested_at: nowIso(), status: 'pending' };
    this.data.access_requests.push(req);
    this._commit();
    return req;
  }
  async approveRequest(id, opts = {}) {
    const req = (this.data.access_requests || []).find(r => r.id === id);
    if (!req) return null;
    // 이미 등록된 계정이면 권한을 건드리지 않고 신청만 정리한다(클라우드와 동일 동작).
    const email = (req.email || '').toLowerCase();
    const existing = this.data.users.find(u => u.id === req.uid || (u.email || '').toLowerCase() === email);
    const user = existing || await this.saveUser({ id: req.uid || '', email: req.email, name: req.name, role: opts.role || 'member', notify_email: true, notify_sources: [] });
    this.data.access_requests = this.data.access_requests.filter(r => r.id !== id);
    this._commit();
    return user;
  }
  async deleteRequest(id) {
    this.data.access_requests = (this.data.access_requests || []).filter(r => r.id !== id);
    this._commit();
  }

  // ---- self profile ----
  // 클라우드와 동작을 맞춘다: 본인이 바꿀 수 있는 필드만 기존 문서에 덮어쓴다(role 등은 보존).
  async updateProfile(user) {
    const prev = this.data.users.find(x => x.id === user.id) || {};
    const patch = { name: user.name || '', notify_email: user.notify_email !== false, notify_sources: user.notify_sources || [] };
    if (user.last_seen) patch.last_seen = user.last_seen;
    if (user.last_login) patch.last_login = user.last_login;
    return this.saveUser({ ...prev, ...patch });
  }

  // 7-day auto-archive (applied on boot, like main.py / main_crawler.py)
  async archiveOld(days = 7) {
    const threshold = Date.now() - days * 86400000;
    let n = 0;
    for (const it of this.data.items) {
      if (it.status === ITEM_STATUS.NEW && Date.parse(it.fetched_at) <= threshold) {
        it.status = ITEM_STATUS.ARCHIVED; it.auto_archived_at = nowIso(); n++;
      }
    }
    if (n) this._commit();
    return n;
  }
}
