# Validation Report — v2.0.0 Rebuilt Source Package

## 수행 환경

- 검증 유형: 오프라인 정적·fixture 기반
- 라이브 국토교통부/ODCloud 키: 사용하지 않음
- 대상: 재생성된 소스 배포물

## 결과

| 검증 | 결과 |
|---|---|
| Python 소스 컴파일 | 통과 |
| runtime pytest | 통과 |
| canonical 도구 등록 17개 | 통과 |
| 통합 도구 등록 33개 | 통과 |
| JSON 도구 카탈로그와 런타임 이름 일치 | 통과 |
| 지역 코드 해석 fixture | 통과 |
| 매매·전월세 XML fixture | 통과 |
| 취소 거래 보존 | 통과 |
| 지표·신호 계산 | 통과 |
| 금융 계산 | 통과 |
| 관심 목록 원자적 저장 | 통과 |
| 제3자 MIT 고지 | 통과 |
| ZIP CRC 무결성 | ZIP 생성 후 별도 검사 |

## 제한

유효 API 키가 없으므로 현재 원천 서버의 실응답, 호출 한도, 운영용 PostgreSQL 마이그레이션과 공개 HTTP 보안은 검증 범위에 포함되지 않습니다.
