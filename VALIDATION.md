# 검증 및 배포 전 확인

이 문서는 패키지에서 완료한 정적 검증과 실제 서비스 배포 전에 추가로 수행해야 하는 실행 검증을 구분합니다.

## 1. 완료 가능한 정적 검증

다음 명령을 패키지 루트에서 실행합니다.

```bash
python scripts/validate_package.py . --write-manifest
```

검증 범위는 다음과 같습니다.

- 필수 파일 존재 여부
- `SKILL.md` YAML front matter
- `agents/openai.yaml` 구문 및 MCP 의존성
- 평가 YAML 구문과 케이스 ID 중복
- MCP 도구 카탈로그 JSON 구문
- 14개 도구의 입력·출력 JSON Schema 2020-12 유효성
- `SKILL.md`, `MCP_TOOL_SPEC.md`, 기계 판독 카탈로그의 도구명 일치
- SKILL이 참조하는 보조 문서 존재 여부
- SQL 문자열·주석을 제외한 괄호 균형, 객체명 중복, 트랜잭션 래퍼
- 29개 테이블의 외래 키 대상 테이블·컬럼 존재 여부
- 아파트Me `LINK_OUT_ONLY`와 비활성 수집 권한 시드
- 활성 거래 뷰의 취소·비활성 거래 제외 조건
- 5개 사용자 테이블의 `FORCE ROW LEVEL SECURITY`
- 단지와 면적 타입 복합 참조 무결성
- 지표 상태별 typed value와 `null` 계약
- 허용된 배포 URL 이외의 미완성 placeholder

`MANIFEST.json`은 각 파일의 바이트 크기와 SHA-256을 기록합니다.

## 2. 정적 검증의 한계

정적 검증 통과는 다음을 증명하지 않습니다.

- PostgreSQL이 전체 DDL과 시드 데이터를 실제로 수락함
- RLS 정책이 실제 OAuth 사용자 격리를 정확히 수행함
- 국토교통부 API 응답 변화가 어댑터와 호환됨
- 배포된 MCP 서버가 2026-07-28 프로토콜을 완전히 준수함
- 지표 SQL·배치 계산 결과가 golden fixture와 수치상 일치함
- 아파트Me 또는 다른 민간 원천 사용 권한이 확보됨

따라서 배포 파이프라인에는 아래 실행 검증을 별도로 포함해야 합니다.

## 3. PostgreSQL 실행 검증

PostgreSQL 16 이상에서 빈 데이터베이스를 준비한 뒤 실행합니다.

```bash
createdb kr_apartment_market_test
psql -v ON_ERROR_STOP=1 \
  -d kr_apartment_market_test \
  -f database/schema.sql
psql -v ON_ERROR_STOP=1 \
  -d kr_apartment_market_test \
  -f database/seed.sql
```

이후 최소한 다음을 검사합니다.

```sql
SELECT source_code, access_mode, collection_enabled, storage_enabled, redistribution_enabled
FROM ref.data_source
ORDER BY source_code;

SELECT COUNT(*) FROM market.v_active_transactions;
SELECT COUNT(*) FROM analytics.metric_definition;

SELECT schemaname, tablename, policyname
FROM pg_policies
WHERE schemaname = 'app'
ORDER BY tablename, policyname;
```

### 필수 기대값

- `apt2me`의 접근 모드는 `LINK_OUT_ONLY`
- `apt2me`의 collection/storage/redistribution은 모두 `false`
- 관심 목록 관련 테이블에는 RLS가 활성화됨
- 지표 정의에는 `formula_version`이 존재함
- `market.v_active_transactions`는 `VALID` 거래만 노출함

## 4. MCP 프로토콜 검증

배포 전에 `agents/openai.yaml`과 `mcp/tool-definitions.json`의 다음 URL을 실제 HTTPS 엔드포인트로 교체합니다.

```text
https://REPLACE_WITH_DEPLOYED_HOST.example/mcp
```

서버 검증 항목:

1. 단일 Streamable HTTP POST 엔드포인트
2. HTTPS 적용
3. 허용 Origin 검증
4. 도구 호출 요청의 JSON-RPC 오류와 도구 실행 오류 구분
5. `structuredContent`가 선언된 `outputSchema`와 일치
6. 하위 호환을 위한 텍스트 `content` 병행 반환
7. 읽기 도구와 쓰기 도구의 인증 경계
8. 관심 목록 도구의 OAuth scope 강제
9. `Idempotency-Key` 재시도 안전성
10. 요청 ID·데이터 기준 시각·산식 버전 로깅

## 5. 데이터와 지표 검증

실제 또는 비식별 fixture로 다음 사례를 재현합니다.

- 동일 전용면적의 정상 거래 5건
- 취소 거래와 후속 정정 revision
- 같은 날짜·가격·면적의 복수 거래
- 직전 30일 0건, 최근 30일 1건인 거래 재개
- 매매 표본은 있으나 전세 표본이 없는 경우
- 전세 표본은 있으나 매매 표본이 없는 경우
- 84.82㎡와 84.99㎡가 분리되는 경우
- 동일 이름 단지가 여러 지역에 있는 경우
- 현재 월 데이터가 부분 수집된 경우
- 원천 partition이 stale 또는 failed인 경우

각 결과는 `evals/golden-prompts.yaml`의 응답·도구 호출 assertion과 함께 검증합니다.

## 6. 권한 게이트

민간 데이터 원천은 `ref.data_source`와 `ref.dataset`에 다음 증빙이 기록되기 전까지 활성화하지 않습니다.

- 계약 또는 명시적 허가 문서
- 허용된 수집 방식
- 저장 가능 기간
- 파생 지표 생성 가능 여부
- 재배포 범위
- 출처 표기 방식
- 계약 만료일과 재검토일

권한이 불명확하면 해당 어댑터는 비활성 상태를 유지하고 `get_source_link`만 사용합니다.
