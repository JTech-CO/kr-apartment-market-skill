# Validation Guide v2.0

## 검증 범위

이 저장소의 기본 검증은 라이브 공공 API 키 없이 수행할 수 있습니다.

```bash
python -m pip install -e '.[dev]'
python scripts/validate_runtime.py
```

검증 항목은 다음과 같습니다.

- 필수 문서·라이선스·소스 파일 존재
- `pyproject.toml` 버전과 패키지 메타데이터
- canonical MCP 도구 17개의 JSON 카탈로그
- 코드 등록 이름과 카탈로그 이름의 일치
- 선택형 호환 도구를 포함한 통합 도구 33개 등록
- Python 소스 컴파일
- 압축 오프라인 지역 코드 표
- `real-estate-mcp` MIT 저작권·허가 고지
- XML 파싱과 취소 거래 보존
- 전세·월세 정규화
- 단지·지역 지표와 거래 재개 처리
- 금융 계산
- 관심 목록 원자적 저장

## 라이브 검증

유효한 공공데이터포털 키가 있는 환경에서는 다음 항목을 별도로 확인합니다.

1. 현재 월과 이전 월의 아파트 매매 조회
2. 동일 지역·월의 아파트 전월세 조회
3. `totalCount`가 페이지 크기를 넘는 지역의 페이지네이션
4. 취소 거래의 `include_canceled` 전환
5. 오피스텔·연립다세대·단독주택·상업용 매매
6. 청약홈/ODCloud 공고와 통계
7. stdio MCP 클라이언트 연결
8. Streamable HTTP 프록시·인증·rate limit

## 운영형 데이터베이스 검증

`database/schema.sql`, `database/seed.sql`, `database/migrations/002_real_estate_mcp_integration.sql`을 PostgreSQL 16 이상에서 순서대로 실행합니다. RLS와 OAuth 사용자 컨텍스트는 실제 애플리케이션 역할을 사용해 별도로 검증해야 합니다.

## 검증하지 않았다고 간주해야 하는 항목

- 유효 API 키 없이 실제 원천 응답의 현재 가용성
- 외부 서비스의 향후 필드·약관 변경
- 공개 HTTP 배포의 보안 구성
- 세금·대출 승인·감정평가 결과
- 허가되지 않은 Apt2Me 데이터 자동 수집
