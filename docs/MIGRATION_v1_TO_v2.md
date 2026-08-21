# v1 → v2 Migration

## Breaking changes

- 프로젝트가 문서 패키지에서 Python 실행 패키지로 확장되었습니다.
- `mcp/tool-definitions.json`은 실제 canonical runtime 도구 계약을 기준으로 재작성됩니다.
- DB 없이 동작하는 로컬 관심 목록 모드가 추가되었습니다.
- 아파트만이 아니라 여러 자산 유형을 `get_transactions`에서 선택합니다.

## 유지되는 항목

- 기존 고수준 도구명
- 동일 면적 비교 원칙
- 취소 거래 제외 원칙
- 사실·지표·해석 분리
- PostgreSQL 운영형 설계
- Apt2Me LINK_OUT_ONLY 기본 정책
- MIT 라이선스

## 사용자 작업

1. Python 3.11+ 설치
2. `.env.example`을 `.env`로 복사
3. `DATA_GO_KR_API_KEY` 설정
4. `pip install -e .` 또는 `uv sync`
5. MCP 클라이언트 설정을 `.mcp.json`에 맞춤
6. 기존 원격 MCP 예시 URL을 실제 endpoint로 교체하거나 stdio 사용

별도 `real-estate-mcp` 서버 설정은 제거해도 됩니다.
