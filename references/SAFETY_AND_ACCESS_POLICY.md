# 안전·접근·권한 정책

버전: 3.0.0

## 1. 금융·주거 의사결정

이 프로젝트는 의사결정 보조 도구입니다. 투자 권유, 감정평가, 대출 승인, 법률·세무 확답을 제공하지 않습니다.

## 2. 현재성

현재 가격·현재 매물·현재 정책은 도구 또는 최신 공식 원천 없이 답하지 않습니다.

## 3. 광고매물 접근

기본 정책:

```text
access_mode = LINK_OUT_ONLY
allow_metadata_display = false
allow_metadata_storage = false
allow_description_storage = false
allow_image_storage = false
allow_contact_storage = false
allow_automated_collection = false
```

공식 제휴가 있으면 계약 범위 안에서 개별 flag를 활성화합니다.

## 4. URL 안전

- HTTPS만 허용
- hostname allowlist
- URL 내용을 서버에서 자동 fetch하지 않음
- `javascript:`, `file:`, 내부 IP URL 거부
- redirect follow 금지(기본)

## 5. 개인정보

저장 금지:

- 집주인·중개사 개인 전화번호
- 로그인 계정과 쿠키
- 상세 거주 주소와 개인 프로필의 불필요한 결합
- 광고 사진의 로컬 복제

## 6. 프로필 데이터

가구 구성·통근 목적지 등은 추천에 필요한 범위만 저장합니다. 공개 서비스에서는 사용자별 RLS, 삭제 API와 보존 기간을 적용합니다.

## 7. AI 환각 방지

- 미연결 통근시간 추정 금지
- 학교 성과 추정 금지
- 세대수·주차 추정 금지
- 링크만 보고 현재 매물 수 추정 금지
- 모델이 score 재계산 금지

## 8. Apt2Me

Apt2Me는 별도 승인 전 원문 링크와 기능 참고로만 사용합니다. v3의 listing source 정책과 동일한 권한 gate를 적용합니다.

## 9. 라이선스

MIT는 코드에 적용됩니다. 제3자 플랫폼의 데이터·사진·설명·상표 사용권은 별도입니다.

## 10. 운영자 체크리스트

- [ ] 원천별 약관 검토일 기록
- [ ] 허용 host 등록
- [ ] cache TTL 등록
- [ ] field allowlist 등록
- [ ] 삭제·정정 처리
- [ ] 사용자 데이터 삭제 경로
- [ ] API key secret 관리
- [ ] 로그 redaction
- [ ] rate limit
- [ ] RLS 검증
