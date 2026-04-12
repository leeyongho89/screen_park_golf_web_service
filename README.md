# 스크린골프 운영 서비스

설계서 `docs/screen_golf_service_design.md`의 1단계 MVP를 기준으로 구현한 운영 웹 서비스입니다.

## 포함 기능

- 회원 등록, 검색, 상세 조회, 비활성화 API
- 정기권/쿠폰 상품 등록과 보유권 관리
- 매출 등록, 일별/월별 요약, 환불 처리
- 정기권 구매 및 쿠폰 구매 매출 저장 시 회원 보유권 자동 생성
- 쿠폰 1회 차감, 잔여 횟수 보정, 정지/재개, 사용 로그 저장
- 감사 로그 저장
- React 운영 화면과 Docker Compose 실행 환경

## 실행

```bash
cp .env.example .env
docker compose up --build
```

브라우저에서 `http://localhost:8080`으로 접속합니다.

개발 중 API만 확인할 때는 `http://localhost:8000/docs`를 사용할 수 있습니다.

## 주요 명령

```bash
docker compose down
docker compose up --build
```

백엔드 테스트:

```bash
cd backend
pytest
```

Docker 환경에서 바로 실행:

```bash
docker compose run --rm --no-deps backend pytest
```

프론트엔드 타입 검사:

```bash
cd frontend
npm test
```

Docker 환경에서 바로 실행:

```bash
docker compose run --rm --no-deps frontend npm test
```

## 다른 WSL 환경 배포

다른 PC의 WSL 2 환경에 옮겨 배포하고, Windows 재부팅 후 자동 실행까지 설정하려면 아래 문서를 기준으로 진행합니다.

- [WSL 배포 가이드](docs/wsl_deployment_guide.md)

## 원천 엑셀 회원 이관

`db/raw/raw_data/*.xlsx`에서 회원 이름과 전화번호만 추출해 이관할 수 있습니다. 먼저 dry-run으로 후보, 제외, 이름 충돌 목록을 확인합니다.

```bash
docker compose run --rm backend python scripts/import_members_from_raw.py
```

실제 등록 전에는 DB 백업을 먼저 만들고, 결과의 이름 충돌 목록을 확인한 뒤 실행합니다.

```bash
docker compose run --rm backend python scripts/import_members_from_raw.py --apply
```

## 운영 메모

- `.env`, 업로드 파일, 백업 파일, `db/raw/`의 원천 자료는 Git에 커밋하지 않습니다.
- 최초 PostgreSQL 컨테이너 생성 시 `db/migrations/001_initial_schema.sql`이 실행됩니다.
- 이미 생성된 DB 볼륨에 스키마를 다시 적용하려면 마이그레이션 절차를 별도로 수행해야 합니다.
- 문자 발송과 문서관리는 설계서상 2단계 범위이므로 DB 초안만 준비되어 있습니다.
