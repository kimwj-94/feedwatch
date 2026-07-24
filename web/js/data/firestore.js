// Cloud adapter: live Firestore + Auth via the Firebase JS SDK (modular, CDN).
// Loaded lazily only when firebase_config.json is present, so demo mode stays
// dependency-free. Exposes the same interface as LocalAdapter and respects the
// security rules in firestore.rules (members manage sources/groups and item status;
// users/config and encrypted credentials are restricted to admins).
import { Adapter, DEFAULT_CONFIG, ITEM_STATUS, newId, nowIso } from './adapter.js';

const SDK = 'https://www.gstatic.com/firebasejs/10.12.5';
const MEMBER_COLLECTIONS = ['groups', 'sources', 'items', 'crawl_logs'];
const ADMIN_COLLECTIONS = ['users', 'access_requests'];

export class CloudAdapter extends Adapter {
  constructor(fb) {
    super();
    this.mode = 'cloud';
    this.isCloud = true;
    this.fb = fb;                // { app, db, auth, fns }
    this.cache = { groups: [], sources: [], items: [], users: [], crawl_logs: [], access_requests: [], config: { ...DEFAULT_CONFIG } };
    this._unsubs = [];
    this._started = false;
  }

  static async create(config) {
    const [{ initializeApp }, fs, auth] = await Promise.all([
      import(`${SDK}/firebase-app.js`),
      import(`${SDK}/firebase-firestore.js`),
      import(`${SDK}/firebase-auth.js`),
    ]);
    const app = initializeApp(config);
    const db = fs.getFirestore(app);
    const authMod = auth.getAuth(app);
    return new CloudAdapter({ app, db, fs, auth, authMod });
  }

  /* ---------- auth lifecycle ---------- */
  waitForAuth() {
    return new Promise(resolve => {
      const stop = this.fb.auth.onAuthStateChanged(this.fb.authMod, user => { stop(); resolve(user); });
    });
  }
  async signInEmail(email, password) {
    const { signInWithEmailAndPassword } = this.fb.auth;
    const cred = await signInWithEmailAndPassword(this.fb.authMod, email, password);
    return cred.user;
  }
  async signInGoogle() {
    const { GoogleAuthProvider, signInWithPopup } = this.fb.auth;
    const cred = await signInWithPopup(this.fb.authMod, new GoogleAuthProvider());
    return cred.user;
  }
  async signUpEmail(email, password) {
    const { createUserWithEmailAndPassword } = this.fb.auth;
    const cred = await createUserWithEmailAndPassword(this.fb.authMod, email, password);
    return cred.user;
  }
  async sendPasswordReset(email) {
    const { sendPasswordResetEmail } = this.fb.auth;
    await sendPasswordResetEmail(this.fb.authMod, email);
  }
  async signOut() { this._stopListeners(); await this.fb.auth.signOut(this.fb.authMod); }

  /* ---------- realtime listeners ---------- */
  async startListeners(user) {
    if (this._started) return;
    this._started = true;
    const { collection, onSnapshot, doc } = this.fb.fs;
    const collections = user && user.role === 'admin'
      ? [...MEMBER_COLLECTIONS, ...ADMIN_COLLECTIONS]
      : MEMBER_COLLECTIONS;
    for (const name of collections) {
      const unsub = onSnapshot(collection(this.fb.db, name), snap => {
        this.cache[name] = snap.docs.map(d => ({ id: d.id, ...d.data() }));
        this._emit();
      }, err => console.error(`[firestore] ${name} listener`, err));
      this._unsubs.push(unsub);
    }
    if (user && user.role !== 'admin') {
      const userUnsub = onSnapshot(doc(this.fb.db, 'users', user.id), d => {
        this.cache.users = d.exists() ? [{ id: d.id, ...d.data() }] : [];
        this._emit();
      }, err => console.error('[firestore] current user listener', err));
      this._unsubs.push(userUnsub);
    }
    const cfgUnsub = onSnapshot(doc(this.fb.db, 'app_config', 'global'), d => {
      this.cache.config = { ...DEFAULT_CONFIG, ...(d.exists() ? d.data() : {}) };
      this._emit();
    }, err => console.error('[firestore] app_config listener', err));
    this._unsubs.push(cfgUnsub);
  }
  _stopListeners() { this._unsubs.forEach(u => { try { u(); } catch {} }); this._unsubs = []; this._started = false; }

  /* ---------- helpers ---------- */
  async _fetchUsers() {
    const { collection, getDocs } = this.fb.fs;
    const snap = await getDocs(collection(this.fb.db, 'users'));
    return snap.docs.map(d => ({ id: d.id, ...d.data() }));
  }
  async resolveAppUser(fbUser) {
    if (!fbUser || !fbUser.uid) return null;
    const { doc, getDoc } = this.fb.fs;
    const snap = await getDoc(doc(this.fb.db, 'users', fbUser.uid));
    if (!snap.exists()) return null;
    const user = { id: snap.id, ...snap.data() };
    this.cache.users = [user];
    return user;
  }
  _set(coll, id, data) { const { doc, setDoc } = this.fb.fs; return setDoc(doc(this.fb.db, coll, id), data); }
  _del(coll, id) { const { doc, deleteDoc } = this.fb.fs; return deleteDoc(doc(this.fb.db, coll, id)); }

  /* ---------- groups ---------- */
  async listGroups() { return [...this.cache.groups].sort((a, b) => (a.order || 0) - (b.order || 0)); }
  async saveGroup(group) {
    const g = { ...group };
    if (!g.id) { g.id = newId('group'); g.created_at = nowIso(); }
    await this._set('groups', g.id, g);
    return g;
  }
  async deleteGroup(id) {
    if (this.cache.sources.some(s => (s.group_ids || (s.group_id ? [s.group_id] : [])).includes(id))) throw new Error('이 구분값에 연결된 URL이 있어 삭제할 수 없습니다.');
    await this._del('groups', id);
  }
  async reorderGroups(orderedIds) {
    const { doc, writeBatch } = this.fb.fs;
    const batch = writeBatch(this.fb.db);
    orderedIds.forEach((id, i) => batch.update(doc(this.fb.db, 'groups', id), { order: i + 1 }));
    await batch.commit();
  }

  /* ---------- sources ---------- */
  async listSources() { return [...this.cache.sources].sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || '')); }
  async saveSource(source) {
    const s = { ...source };
    if (!s.id) { s.id = newId('src'); s.created_at = nowIso(); }
    s.updated_at = nowIso();
    if (s.consecutive_failures == null) s.consecutive_failures = 0;
    await this._set('sources', s.id, s);
    return s;
  }
  async deleteSource(id) {
    const { doc, writeBatch } = this.fb.fs;
    const source = this.cache.sources.find(s => s.id === id);
    const batch = writeBatch(this.fb.db);
    batch.delete(doc(this.fb.db, 'sources', id));
    if (source && source.credential_id) {
      batch.delete(doc(this.fb.db, 'credentials', source.credential_id));
    }
    await batch.commit();
  }
  // 자격증명: 관리자만 쓰기(규칙). 이미 암호화된 값만 저장하며 앱에서 읽지 않는다.
  async saveCredential(cred) {
    const c = { ...cred };
    if (!c.id) c.id = newId('cred');
    c.updated_at = nowIso();
    await this._set('credentials', c.id, c);
    return c;
  }
  async deleteCredential(id) { if (id) await this._del('credentials', id); }

  /* ---------- items ---------- */
  async listItems() { return [...this.cache.items].sort((a, b) => (b.fetched_at || '').localeCompare(a.fetched_at || '')); }
  async setItemStatus(id, status) {
    const { doc, updateDoc } = this.fb.fs;
    const patch = { status };
    const now = nowIso();
    if (status === ITEM_STATUS.READ) patch.read_at = now;
    if (status === ITEM_STATUS.DELETED) patch.deleted_at = now;
    if (status === ITEM_STATUS.ARCHIVED) patch.auto_archived_at = now;
    await updateDoc(doc(this.fb.db, 'items', id), patch);
  }
  async purgeItem(id) { await this._del('items', id); }   // 휴지통 완전삭제 — 규칙상 승인된 가족이면 가능

  /* ---------- users ---------- */
  async listUsers() { return this.cache.users.length ? [...this.cache.users] : this._fetchUsers(); }
  async saveUser(user) {
    const { doc, setDoc } = this.fb.fs;
    const u = { ...user };
    if (!u.id) throw new Error('새 사용자는 가입 신청을 승인해 추가해야 합니다.');
    // merge — 문서를 통째로 갈아끼우면 보내지 않은 필드(role 등)가 삭제된다.
    await setDoc(doc(this.fb.db, 'users', u.id), u, { merge: true });
    return u;
  }
  async deleteUser(id) { await this._del('users', id); }

  /* ---------- logs / config ---------- */
  async listLogs() { return [...this.cache.crawl_logs].sort((a, b) => (b.run_at || '').localeCompare(a.run_at || '')).slice(0, 50); }
  async getConfig() { return { ...this.cache.config }; }
  async saveConfig(patch) {
    const { doc, setDoc } = this.fb.fs;
    const next = { ...this.cache.config, ...patch };
    await setDoc(doc(this.fb.db, 'app_config', 'global'), next, { merge: true });
    return next;
  }

  /* ---------- access requests (가입 신청) ---------- */
  async listRequests() { return [...this.cache.access_requests].sort((a, b) => (b.requested_at || '').localeCompare(a.requested_at || '')); }
  async createRequest({ email, name, provider, uid }) {
    const found = this.cache.access_requests.find(r => (r.email || '').toLowerCase() === (email || '').toLowerCase());
    if (found) return found;
    // 승인 대기 중에는 목록을 읽을 수 없으므로(규칙) 문서 ID를 uid로 고정해 재로그인해도 신청이 쌓이지 않게 한다.
    const req = { id: uid ? `req_${uid}` : newId('req'), email, name: name || (email || '').split('@')[0], provider: provider || 'firebase', uid: uid || null, requested_at: nowIso(), status: 'pending' };
    await this._set('access_requests', req.id, req);
    return req;
  }
  // 이미 등록된 사람의 신청인지 판별(본인 신청이 남아 있는 경우 등)
  _registeredFor(req) {
    const email = (req.email || '').toLowerCase();
    return this.cache.users.find(u => u.id === req.uid || (u.email || '').toLowerCase() === email) || null;
  }
  async approveRequest(id, opts = {}) {
    const req = this.cache.access_requests.find(r => r.id === id);
    if (!req) return null;
    // Key the user doc by the requester's auth uid so Firestore rules (uid-based) recognize them.
    if (!req.uid) throw new Error('이 신청에는 로그인 계정 UID가 없어 승인할 수 없습니다. 신청자가 다시 로그인한 뒤 승인하세요.');
    // 이미 등록된 계정이면 권한을 절대 건드리지 않고 신청만 정리한다.
    // (예전에는 role을 member로 덮어써서, 관리자가 자기 신청을 승인하면 스스로 강등되고
    //  그 직후 관리자 권한이 없어져 신청 삭제까지 실패하는 악순환이 있었다.)
    const existing = this._registeredFor(req);
    const user = existing || await this.saveUser({
      id: req.uid, email: req.email, name: req.name,
      role: opts.role || 'member', notify_email: true, notify_sources: [],
    });
    await this._del('access_requests', id);
    return user;
  }
  async deleteRequest(id) { await this._del('access_requests', id); }

  /* ---------- self profile ---------- */
  // 본인 설정 저장 — '내가 바꿀 수 있는 필드'만 병합해서 쓴다.
  // 문서 전체를 덮어쓰면 role이 사라질 수 있고, 규칙상 관리자는 그 쓰기가 허용되므로
  // 관리자만 스스로 권한을 날리는 사고가 난다. 여기서 role은 아예 건드리지 않는다.
  async updateProfile(user) {
    const { doc, setDoc } = this.fb.fs;
    const patch = {
      name: user.name || '',
      notify_email: user.notify_email !== false,
      notify_sources: user.notify_sources || [],
    };
    if (user.last_seen) patch.last_seen = user.last_seen;
    if (user.last_login) patch.last_login = user.last_login;
    await setDoc(doc(this.fb.db, 'users', user.id), patch, { merge: true });
    return { ...user, ...patch };
  }
}
