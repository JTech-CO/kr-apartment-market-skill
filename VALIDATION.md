# v3.0.0 검증 절차

라이브 공공 API를 호출하지 않는 정적·fixture 검증과, 실제 API key를 사용하는 운영 검증을 분리합니다.

## 1. 로컬 정적 검증

```bash
python scripts/validate_package.py . --write-manifest
```

검사 범위:

- v3 필수 파일
- package version·resource packaging
- SKILL의 Home Finder·LINK_OUT_ONLY·점수 분리 규칙
- 32개 canonical JSON catalog
- runtime 등록 이름과 catalog 일치
- 호환 계층 포함 48개 도구
- Python compile
- 지역 코드와 11개 listing source registry
- HTTPS·사설 IP URL guard
- PostgreSQL `finder`·`listing` schema와 policy trigger
- MIT 및 upstream 고지
- hardcoded secret·로컬 사용자 데이터 부재
- 소개 페이지 OG·GitHub 링크
- Home Finder 평가 케이스

## 2. 런타임 테스트

```bash
PYTHONPATH=src python -m pytest tests/runtime -q
```

테스트 범위:

- 공공 API XML parser fixture
- 취소 거래
- market metric
- 금융 계산
- 관심 목록
- 프로필 검증·patch
- hard constraint·score·confidence
- 추천 후보 생성·순위
- 광고매물 링크·URL 안전
- 저장 검색·diff
- 32/48 도구 등록

## 3. 통합 검증

```bash
python scripts/validate_runtime.py
```

정적 validator와 runtime test를 순서대로 실행합니다.

## 4. 패키지 빌드

```bash
python -m build
python -m twine check dist/*
```

wheel 확인 항목:

```text
kr_apartment_market/resources/region_codes.tsv
kr_apartment_market/resources/listing_sources.json
real_estate/resources/region_codes.txt
real_estate/LICENSE
```

## 5. 신규 가상환경 smoke test

```bash
python -m venv /tmp/kr-home-v3
/tmp/kr-home-v3/bin/pip install dist/*.whl
/tmp/kr-home-v3/bin/kr-apartment-market --list-tools
```

canonical-only 확인:

```bash
/tmp/kr-home-v3/bin/kr-apartment-market --list-tools --no-upstream-compat
```

## 6. PostgreSQL 검증

```bash
createdb kr_apartment_market_test
psql kr_apartment_market_test -v ON_ERROR_STOP=1 -f database/schema.sql
psql kr_apartment_market_test -v ON_ERROR_STOP=1 -f database/seed.sql
```

정책 검증:

- `finder`·`listing` schema 존재
- 사용자 테이블 RLS·FORCE RLS
- link-only source에 `listing_observation` insert 거부
- authorized source + metadata flag + authorization reference에서만 insert 허용

## 7. 라이브 API 검증

유효한 API key가 있는 별도 환경에서만 실행합니다.

- 지역 하나·계약월 하나로 최소 호출
- 페이지네이션
- 취소 필드
- 아파트 매매·전월세
- 청약 공고
- rate-limit 오류
- key redaction

실제 API 응답을 fixture로 저장할 때 service key와 개인정보 가능 필드를 제거합니다.

## 8. ZIP 검증

```bash
unzip -t kr-apartment-market-skill-v3.0.0-source.zip
sha256sum kr-apartment-market-skill-v3.0.0-source.zip
```

압축에는 `.env`, `.data`, `.git`, cache, build directory를 포함하지 않습니다.
