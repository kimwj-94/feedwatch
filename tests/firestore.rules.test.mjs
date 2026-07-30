import { after, before, beforeEach, test } from 'node:test';
import { readFile } from 'node:fs/promises';
import {
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
} from '@firebase/rules-unit-testing';
import {
  doc,
  getDoc,
  setDoc,
  updateDoc,
} from 'firebase/firestore';

const PROJECT_ID = 'demo-feedwatch';
let env;

before(async () => {
  env = await initializeTestEnvironment({
    projectId: PROJECT_ID,
    firestore: {
      host: '127.0.0.1',
      port: 8080,
      rules: await readFile('firestore.rules', 'utf8'),
    },
  });
});

after(async () => {
  await env.cleanup();
});

beforeEach(async () => {
  await env.clearFirestore();
  await env.withSecurityRulesDisabled(async context => {
    const db = context.firestore();
    await setDoc(doc(db, 'users', 'admin-uid'), {
      id: 'admin-uid', name: '관리자', email: 'admin@example.com', role: 'admin',
      notify_email: true, notify_sources: [], notify_push: false, push_fids: [],
    });
    await setDoc(doc(db, 'users', 'member-uid'), {
      id: 'member-uid', name: '구성원', email: 'member@example.com', role: 'member',
      notify_email: true, notify_sources: [], notify_push: false, push_fids: [],
    });
    await setDoc(doc(db, 'groups', 'group-common'), { name: '공통', order: 1 });
    await setDoc(doc(db, 'items', 'item-1'), {
      status: 'new', title: '새 글', fetched_at: new Date().toISOString(),
    });
  });
});

function request(uid = 'pending-uid', email = 'pending@example.com') {
  return {
    id: `req_${uid}`,
    uid,
    email,
    name: '신청자',
    provider: 'password',
    requested_at: new Date().toISOString(),
    status: 'pending',
  };
}

test('가입 신청은 로그인 UID와 같은 문서 ID·uid일 때만 생성된다', async () => {
  const db = env.authenticatedContext('pending-uid', { email: 'pending@example.com' }).firestore();
  await assertSucceeds(setDoc(doc(db, 'access_requests', 'req_pending-uid'), request()));
  await assertFails(setDoc(doc(db, 'access_requests', 'req_other'), request()));
  await assertFails(setDoc(doc(db, 'access_requests', 'req_pending-uid'), {
    ...request(),
    id: 'forged-id',
  }));
  await assertFails(setDoc(
    doc(db, 'access_requests', 'req_pending-uid'),
    request('other-uid', 'pending@example.com'),
  ));
});

test('신청자는 신청 UID와 이메일을 바꿀 수 없다', async () => {
  const db = env.authenticatedContext('pending-uid', { email: 'pending@example.com' }).firestore();
  await setDoc(doc(db, 'access_requests', 'req_pending-uid'), request());
  await assertSucceeds(updateDoc(doc(db, 'access_requests', 'req_pending-uid'), { name: '새 이름' }));
  await assertFails(updateDoc(doc(db, 'access_requests', 'req_pending-uid'), { uid: 'other-uid' }));
  await assertFails(updateDoc(doc(db, 'access_requests', 'req_pending-uid'), { email: 'other@example.com' }));
});

test('구성원은 본인 알림 필드만 수정하고 role은 바꿀 수 없다', async () => {
  const db = env.authenticatedContext('member-uid', { email: 'member@example.com' }).firestore();
  await assertSucceeds(updateDoc(doc(db, 'users', 'member-uid'), {
    notify_push: true,
    push_fids: ['fid-1', 'fid-2'],
  }));
  await assertFails(updateDoc(doc(db, 'users', 'member-uid'), { role: 'admin' }));
  await assertFails(updateDoc(doc(db, 'users', 'member-uid'), {
    push_fids: ['1', '2', '3', '4', '5', '6'],
  }));
  await assertFails(updateDoc(doc(db, 'users', 'member-uid'), {
    push_fids: ['fid-1', { invalid: true }],
  }));
});

test('미승인 사용자는 콘텐츠를 읽지 못하고 구성원은 읽을 수 있다', async () => {
  const pending = env.authenticatedContext('pending-uid', { email: 'pending@example.com' }).firestore();
  const member = env.authenticatedContext('member-uid', { email: 'member@example.com' }).firestore();
  await assertFails(getDoc(doc(pending, 'groups', 'group-common')));
  await assertSucceeds(getDoc(doc(member, 'groups', 'group-common')));
});

test('항목 상태는 정해진 값으로만 변경된다', async () => {
  const db = env.authenticatedContext('member-uid', { email: 'member@example.com' }).firestore();
  await assertSucceeds(updateDoc(doc(db, 'items', 'item-1'), {
    status: 'read',
    read_at: new Date().toISOString(),
  }));
  await assertFails(updateDoc(doc(db, 'items', 'item-1'), { status: 'hacked' }));
});
