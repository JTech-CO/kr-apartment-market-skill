# v2.0.0에서 v3.0.0으로 마이그레이션

## 1. 변경 성격

v3.0.0은 기존 시장 분석 기능을 제거하지 않는 additive update입니다.

```text
v2
├─ kr_apartment.* 17개
├─ 실거래·청약 런타임
├─ 시장 지표
└─ 관심 단지

v3
├─ v2 전체 기능
├─ kr_home.* 15개
├─ 검색 프로필
├─ 설명 가능한 추천
├─ 광고매물 원문 링크
└─ 저장 검색·변경 비교
```

## 2. 소스 업데이트

```bash
git checkout -b feat/home-finder-v3
git pull origin main
# v3 파일 적용
uv sync --extra dev
```

## 3. 환경 변수

기존 환경 변수에 다음을 추가할 수 있습니다.

```env
KR_HOME_FINDER_PATH=.data/home_finder.json
```

미설정 시 위 경로를 기본값으로 사용합니다.

## 4. MCP 설정

기존 실행 명령은 동일합니다.

```bash
uv run kr-apartment-market --transport stdio
```

canonical 도구만 노출하려면:

```bash
uv run kr-apartment-market --transport stdio --no-upstream-compat
```

## 5. 데이터베이스

PostgreSQL 운영 환경에서는 백업 후 migration을 적용합니다.

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f database/migrations/003_home_finder.sql
```

migration은 `finder`와 `listing` schema를 추가하며 기존 거래·분석·관심 목록 테이블을 삭제하지 않습니다.

## 6. 클라이언트 변경

기존 호출:

```text
kr_apartment.get_complex_snapshot
kr_apartment.compare_complexes
```

새로운 추천 흐름:

```text
kr_home.validate_search_profile
→ kr_home.create_search_profile
→ kr_home.recommend_complexes
→ kr_home.explain_complex_match
→ kr_home.find_listing_links
```

## 7. 광고매물 정책

v2에서 원문 링크만 허용했던 Apt2Me 정책을 일반화해 모든 광고매물 원천에 적용합니다. 별도 승인 기록이 없는 원천은 `LINK_OUT_ONLY`로 유지해야 합니다.

## 8. 롤백

코드 롤백은 v2 tag 또는 commit으로 되돌립니다. DB migration은 새 schema를 사용하는 애플리케이션을 먼저 중단하고 백업을 확인한 후 처리합니다. 운영 데이터가 생긴 경우 단순 `DROP SCHEMA`는 금지합니다.
