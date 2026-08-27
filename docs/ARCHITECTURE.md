# Runtime Architecture

현재 버전: 3.0.0

전체 Home Finder 아키텍처는 [`HOME_FINDER_ARCHITECTURE.md`](HOME_FINDER_ARCHITECTURE.md)를 참조합니다.

## 단일 서버

```text
FastMCP: kr-apartment-market
├─ kr_apartment.* 17 canonical tools
├─ kr_home.* 15 canonical tools
└─ real_estate compatibility 16 optional tools
```

## canonical runtime

```text
src/kr_apartment_market/
├─ data/          public API client, endpoint registry, parser, region resolver
├─ services/      market metrics, finance, watchlist
├─ home/          profile, scoring, recommender, listing links, saved search
├─ tools/         MCP registration
├─ resources/     region codes and listing-source registry
└─ server.py      stdio / Streamable HTTP entry point
```

## 핵심 경계

```text
공공데이터       → 가격·거래량·시장 지표·추천 facts
결정론적 코드     → score·confidence·exclusion
AI               → 조건 추출과 결과 설명
제3자 플랫폼      → 원문 광고매물 확인 링크
승인 adapter      → 계약 범위의 선택형 metadata
```

## 확장 경로

```text
Local JSON
→ PostgreSQL finder/listing schemas
→ enrichment adapters
→ authorized listing APIs
→ first-party broker feeds
```
