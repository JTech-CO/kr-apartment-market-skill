# 데이터 원천과 신선도 정책

버전: 3.0.0

## 1. 원천 계층

### A. 공공 거래 원천

국토교통부 실거래 공개 API를 가격·거래량·임대차 분석의 우선 원천으로 사용합니다.

지원 범위:

- 아파트 매매·전월세
- 오피스텔 매매·전월세
- 연립다세대 매매·전월세
- 단독다가구 매매·전월세
- 상업업무용 매매

API 입력의 핵심은 5자리 법정동 코드와 계약연월입니다.

### B. 청약 원천

청약홈·ODCloud의 공고와 통계를 사용합니다.

- 모집 공고
- 접수·발표·계약 일정
- 신청자·당첨자·경쟁률·가점 통계

### C. 오프라인 기준정보

`src/kr_apartment_market/resources/region_codes.tsv`와 vendored 호환 리소스를 지역 해석에 사용합니다. 원본 갱신 시 source와 갱신일을 기록합니다.

### D. 파생 지표

공공 거래를 입력으로 deterministic metric engine이 계산합니다.

- 중위가격
- 최고가·회복률
- 거래량 모멘텀
- 전세가율
- 추정 갭
- 신고가·거래 재개 신호

### E. Optional Enrichment

다음은 기본 실거래 API만으로 완전하지 않으므로 별도 검증 원천이 있을 때만 반영합니다.

- 통근시간
- 학교 거리·생활 인프라
- 세대수·주차·엘리베이터
- 관리비
- 승인된 광고매물 수·호가

각 enrichment는 `source`, `observed_at`, `confidence`를 포함해야 합니다.

### F. 광고매물 원문 링크

기본 원천:

```text
naver
daangn
peterpan
asil
kb
```

추가 원천:

```text
dabang
zigbang
disco
valuemap
ddangya
onbid
```

이들은 기본적으로 데이터 원천이 아니라 **사용자가 원문을 확인하기 위한 link source**입니다.

## 2. 시간 필드

```text
contract_date      실제 계약일
source_updated_at  원천이 공개·갱신된 시각
collected_at       시스템 수집 시각
answered_at        MCP 응답 시각
listing_verified_at 승인된 매물 링크·데이터 최종 확인 시각
```

계약일과 수집일을 혼동하지 않습니다.

## 3. “최신” 표현

허용:

```text
최신 신고·공개된 실거래
2026-08-26 수집 기준
최근 90일 유효 거래
```

금지:

```text
실시간 체결가
현재 확정 시세
오늘 반드시 거래 가능한 매물
```

## 4. 증분 수집

운영형 저장소는 현재월과 이전월을 반복 조회해 지연 신고·취소·정정을 반영합니다. 최근 12개월은 주기적으로 정합성을 재검사합니다.

## 5. 원천 장애

- 한 지역 실패: 부분 성공
- 공공 API 전체 실패: 추천을 추측으로 대체하지 않음
- 광고 link source 실패: 추천 결과 유지
- 청약 원천 실패: 실거래 기능 유지

## 6. 데이터 보관

### 개인용

온디맨드 조회와 로컬 프로필·관심 목록만 저장합니다.

### 운영형

원본 수집 로그, normalized transaction, revision, metric snapshot, recommendation run을 PostgreSQL에 저장합니다.

### 제3자 광고매물

승인 기록 없이는 URL과 source classification 외 metadata를 저장하지 않습니다.
