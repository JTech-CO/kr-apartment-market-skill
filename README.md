# KR Apartment Market AI Skill

대한민국 아파트의 최신 신고 실거래, 단지 비교, 지역 시장 흐름, 신고가·회복률·전세가율·추정 갭 등을 AI가 근거 데이터와 함께 설명하도록 설계한 SKILL + MCP 명세 패키지입니다.

> 이 프로젝트에서 말하는 “최신” 또는 “실시간”은 주식 체결처럼 즉시 발생하는 실시간 가격이 아니라, 원천 시스템에 **최신으로 신고·공개된 실거래 데이터**를 의미합니다.

## 핵심 원칙

1. 핵심 실거래 데이터는 국토교통부 등 이용 권한이 명확한 공공 원천으로 독립 구축합니다.
2. 아파트Me는 기능·사용자 경험의 참고 원천이며, 별도 허가 전에는 페이지 자동 수집이나 데이터 재배포를 하지 않습니다.
3. 허가되지 않은 아파트Me 데이터는 저장하지 않고, 사용자가 원문을 확인할 수 있는 링크만 제공합니다.
4. 현재 가격을 모델 지식으로 추측하지 않습니다. 최신성이 필요한 질문에는 반드시 MCP 도구를 호출합니다.
5. 사실, 자체 산식으로 계산한 지표, AI의 해석을 명확히 분리합니다.
6. 투자·감정평가·대출 승인·세무 판단을 확정하거나 보장하지 않습니다.

## 패키지 구조

```text
kr-apartment-market-skill/
├── README.md
├── PRD.md
├── MCP_TOOL_SPEC.md
├── SKILL.md
├── VALIDATION.md
├── MANIFEST.json
├── agents/
│   └── openai.yaml
├── database/
│   ├── DATABASE_SCHEMA.md
│   ├── schema.sql
│   └── seed.sql
├── mcp/
│   └── tool-definitions.json
├── references/
│   ├── DATA_SOURCES.md
│   ├── METRIC_DEFINITIONS.md
│   ├── OUTPUT_CONTRACT.md
│   └── SAFETY_AND_ACCESS_POLICY.md
├── evals/
│   └── golden-prompts.yaml
└── scripts/
    └── validate_package.py
```

## 주요 문서

- `PRD.md`: 제품 목표, 범위, 사용자 흐름, 기능 요구사항, 비기능 요구사항, 수용 기준, 로드맵
- `MCP_TOOL_SPEC.md`: MCP 2026-07-28 기준 전송·인증·도구·오류·출력 계약
- `SKILL.md`: ChatGPT/Codex가 도구를 선택하고 결과를 설명하는 완성형 워크플로
- `database/schema.sql`: PostgreSQL 16 기준 정규화 데이터베이스 DDL
- `mcp/tool-definitions.json`: MCP 도구의 기계 판독용 입력·출력 JSON Schema
- `evals/golden-prompts.yaml`: 활성화·도구 선택·안전·경계 조건을 다루는 51개 평가 케이스
- `VALIDATION.md`: 정적 검증 범위와 PostgreSQL·MCP 실행 검증 절차
- `scripts/validate_package.py`: YAML·JSON Schema·도구명·SQL 정적 검증 및 manifest 생성기

## 권장 배포 형태

```text
ChatGPT / Codex
  └─ KR Apartment Market SKILL
       └─ MCP Streamable HTTP
            ├─ Public Data Adapter
            ├─ Optional Authorized Partner Adapter
            ├─ Metric Engine
            ├─ PostgreSQL
            └─ Redis Cache (optional)
```

## 기본 활성 범위

- 대한민국 아파트 매매·전세·월세 실거래
- 단지명·지역명 해석 및 중복 단지 구분
- 최근 거래와 기간별 통계
- 동일 전용면적 기준 단지 비교
- 거래량, 신고가, 최고가 대비 회복률
- 전세가율, 추정 매매·전세 갭
- 지역 시장 펄스 및 단지 순위
- 관심 단지 저장과 변경 브리핑
- 공공 원문 및 아파트Me 원문 링크 이동

## 구현 전 필수 결정

- 운영 형태: 개인용 / 사내 도구 / 공개 플러그인
- 인증 형태: 공개 조회만 / OAuth 기반 관심 단지 기능 포함
- 데이터 범위: 아파트만 / 오피스텔·분양권·빌라 확장
- 원천별 수집·보관·재배포 권한
- 아파트Me 운영자와의 공식 연동 또는 링크 전용 정책
- 전국 일괄 수집과 온디맨드 조회의 비용·트래픽 배분

## 기준일과 규격

- 문서 기준일: 2026-08-18
- MCP 대상 규격: `2026-07-28`
- 데이터베이스: PostgreSQL 16+
- JSON Schema: 2020-12
- 기본 시간대: `Asia/Seoul`

## 패키지 정적 검증

```bash
python scripts/validate_package.py . --write-manifest
```

이 명령은 문서·YAML·JSON Schema·도구명 일치·SQL 정적 조건·원천 접근 정책을 검사합니다. 실제 PostgreSQL 마이그레이션과 배포된 MCP 서버의 프로토콜 적합성은 `VALIDATION.md`의 실행 절차로 별도 검증해야 합니다.
