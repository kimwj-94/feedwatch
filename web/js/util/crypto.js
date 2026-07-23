// 브라우저 측 자격증명 암호화 (WebCrypto).
// shared/crypto.py 의 PassphraseCipher 와 동일 포맷이라 크롤러가 그대로 복호화한다:
//   PBKDF2-HMAC-SHA256(passphrase, salt[16], 200000) → AES-256-GCM
//   저장값 = base64( salt[16] + iv[12] + ciphertext||tag )
// 브라우저는 '암호화'만 수행한다(복호화는 크롤러 전용).
const ITERATIONS = 200000;

export async function encryptSecret(passphrase, plaintext) {
  if (!passphrase) throw new Error('수집 비밀번호가 필요합니다.');
  if (!window.crypto || !window.crypto.subtle) throw new Error('이 브라우저는 보안 암호화를 지원하지 않습니다(HTTPS/localhost 필요).');
  const enc = new TextEncoder();
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const baseKey = await crypto.subtle.importKey('raw', enc.encode(passphrase), 'PBKDF2', false, ['deriveKey']);
  const key = await crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt, iterations: ITERATIONS, hash: 'SHA-256' },
    baseKey, { name: 'AES-GCM', length: 256 }, false, ['encrypt'],
  );
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, enc.encode(plaintext)));
  const blob = new Uint8Array(16 + 12 + ct.length);
  blob.set(salt, 0); blob.set(iv, 16); blob.set(ct, 28);
  let bin = '';
  for (let i = 0; i < blob.length; i++) bin += String.fromCharCode(blob[i]);
  return btoa(bin);
}
