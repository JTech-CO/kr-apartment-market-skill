# 광고매물 원천 접근 정책

정책 버전: 3.0.0

## 1. 기본 원칙

KR Apartment Market AI Skill은 광고매물 통합 크롤러가 아닙니다. 추천의 근거는 공공 실거래이며, 광고매물 계층은 사용자가 각 원문 플랫폼에서 현재 상태를 확인하도록 연결합니다.

```text
공개 열람 가능 ≠ 자동 수집 허용
링크 가능 ≠ 재배포 가능
광고가격 ≠ 실거래가
MIT 코드 라이선스 ≠ 제3자 데이터 사용권
```

## 2. 접근 모드

| 모드 | 의미 |
|---|---|
| `LINK_OUT_ONLY` | 공식 홈·지역·원문 링크만 제공 |
| `PUBLIC_DEEP_LINK` | 공개적으로 안정된 상세 URL 규칙을 사용 |
| `USER_SUPPLIED_URL` | 사용자가 붙여넣은 URL을 일회성 비교 대상으로 사용 |
| `AUTHORIZED_API` | 계약·정식 API 범위의 필드만 수집·표시 |
| `FIRST_PARTY_FEED` | 소유자·중개사가 직접 제공한 매물 피드 |

기본값은 `LINK_OUT_ONLY`입니다.

## 3. 기본 원천

| source code | 표시명 | 공식 시작 URL | 역할 |
|---|---|---|---|
| `naver` | 네이버 부동산 | `https://fin.land.naver.com/` | 주거·상업·토지 원문 확인 |
| `daangn` | 당근 부동산 | `https://realty.daangn.com/` | 지역 지도·직거래·중개 원문 확인 |
| `peterpan` | 피터팬 | `https://www.peterpanz.com/` | 주거 매물 원문 확인 |
| `asil` | 아실 | `https://asil.kr/asil/index.jsp` | 아파트 분석 교차 확인 |
| `kb` | KB부동산 | `https://kbland.kr/` | 시세·실거래·매물 교차 확인 |

추가 source code: `dabang`, `zigbang`, `disco`, `valuemap`, `ddangya`, `onbid`.

## 4. 기본 허용 필드

`LINK_OUT_ONLY`에서는 다음 정보만 저장할 수 있습니다.

```text
source code
공식 homepage URL
생성한 원문·검색 링크
허용 host
링크 생성 시각
사용자가 입력한 URL의 source classification
```

## 5. 기본 금지 필드

서면 허가 또는 정식 API 계약이 없으면 다음을 저장·재표시하지 않습니다.

- 매물 사진
- 광고 상세 설명
- 개인 연락처
- 중개사 개인 휴대전화
- 로그인 쿠키·세션
- 플랫폼 전체 매물 목록
- 비공식 endpoint 응답
- 대량 수집한 가격·등록일·매물번호

## 6. 링크 생성

### 당근

지역명이 있을 때 공개 지역 지도 경로를 생성할 수 있습니다.

```text
https://realty.daangn.com/map/{시도}/{시군구}
```

URL 구성 요소는 percent encoding합니다.

### 기타 원천

검증된 안정적 검색 경로가 registry에 없으면 다음 두 링크를 반환합니다.

1. 플랫폼 공식 홈
2. 일반 검색엔진의 `site:` 제한 discovery URL

두 번째 링크는 플랫폼 API가 아니며, 검색 결과의 정확성과 노출 여부를 보장하지 않습니다.

## 7. 사용자 제공 URL

`kr_home.inspect_listing_url`은 다음만 수행합니다.

- HTTPS URL 형식 검사
- hostname 정규화
- registry allowlist와 비교
- source 식별
- 지원 여부 반환

페이지 fetch, 로그인 우회, content parsing은 하지 않습니다.

## 8. 승인 데이터 활성화 절차

```text
계약 또는 서면 허가 확보
→ source_access_policy 등록
→ 허용 endpoint와 필드 allowlist 등록
→ 보관 기간·삭제 의무 설정
→ adapter 구현
→ 약관·보안·QA 검토
→ allow_metadata_* 플래그 활성화
```

단순 환경 변수로 승인 모드를 켜지 않습니다.

## 9. 매물 상태 표현

허가된 데이터가 있을 때도 다음 상태를 구분합니다.

```text
ACTIVE
STALE
REMOVED
REDIRECTED
LOGIN_REQUIRED
UNKNOWN
```

“현재 계약 가능”이나 “실매물 보장”으로 표현하지 않습니다. 플랫폼의 확인 표시가 있으면 “해당 플랫폼 기준 확인 상태”라고 표시합니다.

## 10. 중복 처리

여러 플랫폼의 매물 수를 단순 합산하지 않습니다. 허가된 메타데이터가 있을 때만 listing cluster를 만들며, 불확실한 경우 자동 병합하지 않습니다.

## 11. 삭제와 정정

- 원문 링크가 제거되면 상태만 변경하고 감사 이력을 보존
- 정책상 보관 기한이 끝난 metadata는 삭제
- 사진·연락처는 기본 미수집
- 사용자 제공 URL 삭제 요청을 지원

## 12. 원천 장애

광고매물 링크 원천이 중단돼도 공공데이터 기반 추천 결과는 반환합니다. 원천별 장애를 전체 실패로 승격하지 않습니다.
