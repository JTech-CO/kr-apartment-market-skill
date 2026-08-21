# real-estate-mcp 통합 설계

## 결론

`real-estate-mcp`를 Git submodule, 별도 pip dependency, 별도 서버로 두지 않습니다. 원본 소스와 지역 코드 리소스를 이 저장소에 vendoring하고, 하나의 FastMCP 인스턴스에서 고수준 canonical 도구와 upstream 호환 도구를 함께 등록합니다.

## 통합 전후

```text
이전
AI Client ─┬─ kr-apartment-market-skill (문서/계약)
           └─ real-estate-mcp (별도 설치/별도 서버)

이후
AI Client ── kr-apartment-market-skill
             ├─ SKILL
             ├─ canonical MCP runtime
             ├─ public-data adapter
             ├─ analytics engine
             └─ vendored real-estate-mcp compatibility layer
```

## 코드 소유 경계

| 경로 | 역할 | 출처 |
|---|---|---|
| `src/kr_apartment_market/` | canonical 서버, 정규화, 지표, 관심 목록 | JTech_CO 통합 구현 |
| `src/real_estate/` | 원본 도구 호환 계층과 지역 코드 | tae0y/real-estate-mcp vendored |
| `licenses/real-estate-mcp-MIT.txt` | 원본 MIT 전문 | upstream |
| `THIRD_PARTY_NOTICES.md` | 배포물 제3자 고지 | 통합 프로젝트 |

## canonical 계층을 별도로 둔 이유

원본 실행 코드는 폭넓은 API 커버리지가 강점이지만, KR Apartment Market의 기존 계약에는 다음 요구가 추가됩니다.

- 취소 거래 보존
- 원천 전체 페이지 순회
- 여러 계약월 통합
- 표준 Transaction 모델
- 데이터 없음과 0 분리
- 단지·지역 고수준 지표
- 표본 품질
- 공통 응답 envelope와 출처
- 관심 목록
- Apt2Me 접근 권한 게이트

원본 코드를 무리하게 변형하면 upstream 추적이 어려워집니다. 따라서 vendored 경로는 호환 계층으로 보존하고, 새 요구는 canonical 계층에서 구현합니다.

## 등록 순서

1. canonical `kr_apartment.*` 도구 등록
2. `ENABLE_REAL_ESTATE_MCP_COMPAT` 확인
3. vendored 모듈에서 `register*` 함수 동적 탐색
4. 동일 FastMCP 인스턴스에 원본 도구 등록
5. 호환 모듈 실패 시 경고를 남기고 canonical 서버 유지

## 데이터 흐름

```text
MCP input
→ 지역 코드 확인
→ 자산/거래 유형 endpoint 선택
→ 월별·페이지별 API 호출
→ XML header 검증
→ 공통 Transaction 정규화
→ exact source hash 중복 제거
→ 취소 제외/면적/단지 필터
→ 결정론적 지표
→ source + freshness envelope
```

## upstream 동기화

자동으로 최신 upstream을 덮어쓰지 않습니다. 업데이트 시 다음 절차를 사용합니다.

1. 새 upstream tag/commit을 별도 작업 트리에 가져옴
2. LICENSE와 README 변경 확인
3. `src/real_estate/` diff 검토
4. API endpoint·필드·등록 함수 변화 확인
5. upstream 테스트와 runtime 회귀 테스트 실행
6. `THIRD_PARTY_NOTICES.md`의 commit 기록 갱신
7. canonical wrapper의 호환성 확인

## 라이선스

MIT는 복사·수정·병합·배포·재라이선스·판매를 허용하지만, 원 저작권 및 허가 고지를 소프트웨어의 상당 부분에 포함해야 합니다. 따라서 원본 라이선스 파일을 삭제하거나 JTech_CO 단독 저작물처럼 표시해서는 안 됩니다.
