// Adapter contract shared by the demo (local) and cloud (Firestore) backends.
// Both expose the same async API + a subscribe() for realtime/refresh notifications,
// mirroring shared/repository.py's BaseRepository so the UI is backend-agnostic.
//
//   mode            : 'demo' | 'cloud'
//   isCloud         : boolean
//   subscribe(cb)   : () => unsubscribe   (cb called whenever data changes)
//
//   listGroups()                       -> Group[]
//   saveGroup(group)                   -> Group
//   deleteGroup(id)                    -> void   (throws if sources still reference it)
//   reorderGroups(orderedIds)          -> void
//
//   listSources()                      -> Source[]
//   saveSource(source)                 -> Source
//   deleteSource(id)                   -> void
//
//   listItems()                        -> Item[]   (all; UI filters by status/group/date/search)
//   setItemStatus(id, status)          -> void
//   purgeItem(id)                      -> void
//
//   listUsers()                        -> User[]
//   saveUser(user)                     -> User
//   deleteUser(id)                     -> void
//
//   listLogs()                         -> CrawlLog[]
//   getConfig()                        -> AppConfig
//   saveConfig(patch)                  -> AppConfig
//
//   listRequests()                     -> AccessRequest[]   (가입 신청 대기 목록; admin)
//   createRequest({email,name,provider}) -> AccessRequest   (미등록 로그인 시 본인 신청)
//   approveRequest(id, {role})         -> User              (승인 = users 등록 + 신청 삭제)
//   deleteRequest(id)                  -> void              (거절)
//   updateProfile({name, notify_email, notify_sources}) -> User  (로그인 본인 수정)

export const ITEM_STATUS = { NEW: 'new', READ: 'read', ARCHIVED: 'archived_unread', DELETED: 'deleted' };
export const SOURCE_TYPES = ['general', 'youtube', 'naver', 'login_required'];
export const SOURCE_TYPE_LABELS = {
  general: '일반 사이트', youtube: '유튜브', naver: '네이버 카페/블로그', login_required: '로그인 필요',
};
// email_provider '' = 크롤러 환경설정(EMAIL_PROVIDER / GitHub Secrets)을 따름. shared/repository.py와 동일.
export const DEFAULT_CONFIG = { auto_archive_days: 7, trash_retention_days: 30, email_enabled: true, email_provider: '' };

export function newId(prefix) {
  const rnd = (crypto.getRandomValues(new Uint8Array(6)));
  return `${prefix}_${[...rnd].map(b => b.toString(16).padStart(2, '0')).join('')}`;
}

export function nowIso() { return new Date().toISOString(); }

export class Adapter {
  constructor() { this._subs = new Set(); }
  subscribe(cb) { this._subs.add(cb); return () => this._subs.delete(cb); }
  _emit() { for (const cb of [...this._subs]) { try { cb(); } catch (e) { console.error('[adapter] subscriber error', e); } } }
}
