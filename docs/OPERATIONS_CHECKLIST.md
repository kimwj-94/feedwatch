# FeedWatch 운영 체크리스트

## 매주

- [ ] 크롤링 이력에서 실패가 반복되는 소스가 없는지 확인
- [ ] GitHub Actions 최근 실행이 정상인지 확인
- [ ] 관리자 시스템 진단에서 이메일·푸시 알림 사용자와 등록 기기 수 확인
- [ ] 최근 크롤링 이력에 `[NOTIFICATION]` 오류가 없는지 확인

## 배포 전

- [ ] `python -m unittest discover -s tests -v`
- [ ] `npm ci && npm run test:rules`
- [ ] `FEEDWATCH_RUN_WEB_SMOKE=1 python -m unittest tests.test_web_smoke -v`
- [ ] 브라우저에서 데모 모드 기본 흐름 확인
- [ ] Firestore 규칙 변경 시 로컬 에뮬레이터 테스트 확인

## 배포 후

- [ ] `Deploy web app` 작업 성공 확인
- [ ] `Deploy Firestore Rules` 작업 성공 확인
- [ ] 가입 신청 → 관리자 승인 → 재로그인 흐름 확인
- [ ] 모바일 화면에서 메뉴, 프로필, 대시보드가 가로로 넘치지 않는지 확인

## 장애 대응

- [ ] 서비스 계정 키 만료·폐기 여부 확인
- [ ] SMTP 인증 실패 여부 확인
- [ ] Firebase Cloud Messaging Web Push 인증서와 `vapidKey` 설정 확인
- [ ] 사용자의 브라우저·운영체제 알림 권한 및 등록 기기 확인
- [ ] 실패 소스는 비활성화 후 원인 확인
