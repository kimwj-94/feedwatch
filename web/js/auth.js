// Cloud auth: Firebase Google + email/password, gated to the FeedWatch users
// allowlist (mirrors app/auth.py). A signed-in but not-yet-approved account is
// recorded as an access request and shown a "pending approval" screen.

export class CloudAuth {
  constructor(adapter) { this.adapter = adapter; }

  async emailLogin(email, password) {
    if (!email || !password) throw new Error('이메일과 비밀번호를 입력하세요.');
    let u;
    try { u = await this.adapter.signInEmail(email, password); }
    catch (e) { throw new Error(friendly(e)); }
    return this._gate(u);
  }

  async googleLogin() {
    let u;
    try { u = await this.adapter.signInGoogle(); }
    catch (e) { throw new Error(friendly(e)); }
    return this._gate(u);
  }

  // 가입 신청: 비밀번호 계정을 만들고 승인 대기 상태로 둔다.
  async signUp(name, email, password) {
    if (!name || !email || !password) throw new Error('이름·이메일·비밀번호를 모두 입력하세요.');
    if (password.length < 6) throw new Error('비밀번호는 6자 이상이어야 합니다.');
    let u;
    try { u = await this.adapter.signUpEmail(email, password); }
    catch (e) { throw new Error(friendly(e)); }
    try {
      await this.adapter.createRequest({ email: u.email, name, provider: 'password', uid: u.uid });
    } catch (e) {
      await this.adapter.signOut().catch(() => {});
      throw new Error('계정은 만들어졌지만 가입 신청 저장에 실패했습니다. 로그인하면 신청을 다시 시도합니다.');
    }
    return { pending: true, email: u.email };
  }

  async resetPassword(email) {
    if (!email) throw new Error('비밀번호를 재설정할 이메일을 입력하세요.');
    try { await this.adapter.sendPasswordReset(email); }
    catch (e) { throw new Error(friendly(e)); }
  }

  async _gate(fbUser) {
    const user = await this.adapter.resolveAppUser(fbUser);
    if (user) {
      await this.adapter.startListeners(user);
      return { user, provider: providerOf(fbUser) };
    }
    // 미등록 → 가입 신청 생성, 승인 대기
    try {
      await this.adapter.createRequest({
        email: fbUser.email,
        name: fbUser.displayName || (fbUser.email || '').split('@')[0],
        provider: providerOf(fbUser),
        uid: fbUser.uid,
      });
    } catch (e) {
      await this.adapter.signOut().catch(() => {});
      throw new Error('가입 신청을 저장하지 못했습니다. 네트워크 연결을 확인하고 다시 로그인해 주세요.');
    }
    return { pending: true, email: fbUser.email };
  }
}

function providerOf(u) {
  const p = (u.providerData && u.providerData[0] && u.providerData[0].providerId) || 'firebase';
  return p.includes('google') ? 'google' : (p.includes('password') ? 'password' : p);
}

function friendly(e) {
  const code = (e && e.code) || '';
  const map = {
    'auth/invalid-email': '이메일 형식이 올바르지 않습니다.',
    'auth/user-disabled': '비활성화된 계정입니다.',
    'auth/user-not-found': '등록되지 않은 이메일입니다. 가입 신청을 이용하세요.',
    'auth/wrong-password': '비밀번호가 올바르지 않습니다.',
    'auth/invalid-credential': '이메일 또는 비밀번호가 올바르지 않습니다.',
    'auth/email-already-in-use': '이미 가입된 이메일입니다. 로그인해 주세요.',
    'auth/weak-password': '비밀번호는 6자 이상이어야 합니다.',
    'auth/popup-closed-by-user': 'Google 로그인 창이 닫혔습니다.',
    'auth/popup-blocked': '팝업이 차단되었습니다. 팝업을 허용해 주세요.',
    'auth/network-request-failed': '네트워크 오류입니다. 연결을 확인하세요.',
  };
  return map[code] || (e && e.message) || '인증에 실패했습니다.';
}
