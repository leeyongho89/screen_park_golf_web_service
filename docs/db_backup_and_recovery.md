# DB 백업 및 복구 가이드

이 문서는 Docker/WSL 환경에서 PostgreSQL 데이터를 안전하게 백업하고, 컨테이너 레이어 오류가 났을 때 데이터 손실 없이 복구하는 절차입니다.

## 기본 원칙

- PostgreSQL 데이터는 `postgres_data` named volume에 저장합니다.
- 컨테이너는 지워도 되지만 DB volume은 지우지 않습니다.
- 운영 데이터가 있으면 `docker compose down -v`를 사용하지 않습니다.
- Windows 종료, 재부팅, WSL 종료 전에는 가능하면 `docker compose down`으로 정상 종료합니다.

## 수동 백업

프로젝트 루트에서 실행합니다.

```bash
deploy/wsl/backup-db.sh
```

백업 파일은 아래 형식으로 생성됩니다.

```text
backups/screen_golf_YYYYMMDD_HHMMSS.dump
```

백업 파일은 개인정보성 운영 데이터를 포함할 수 있으므로 소유자만 읽고 쓸 수 있는 권한으로 생성됩니다.

배포 경로가 기본값과 다르면 `PROJECT_DIR`를 지정합니다.

```bash
PROJECT_DIR=/opt/screen_park_golf_service /opt/screen_park_golf_service/deploy/wsl/backup-db.sh
```

오래된 백업은 기본 30일 뒤 자동 삭제됩니다. 보관 기간을 바꾸려면 `BACKUP_KEEP_DAYS`를 지정합니다.

```bash
BACKUP_KEEP_DAYS=90 deploy/wsl/backup-db.sh
```

## 자동 백업 예시

WSL 안에서 `crontab -e`를 열고 매일 새벽 2시에 실행되도록 등록합니다.

```cron
0 2 * * * PROJECT_DIR=/opt/screen_park_golf_service /opt/screen_park_golf_service/deploy/wsl/backup-db.sh >> /opt/screen_park_golf_service/backups/backup.log 2>&1
```

등록 후 백업 파일이 생성되는지 확인합니다.

```bash
ls -lh backups/screen_golf_*.dump
```

## Docker 레이어 오류 복구

아래와 같은 오류는 앱이나 PostgreSQL 스키마 문제가 아니라 Docker의 컨테이너 writable layer 메타데이터가 깨진 경우입니다.

```text
RWLayer of container ... is unexpectedly nil
```

이 경우 DB volume은 그대로 두고 컨테이너만 재생성합니다.

```bash
cd /home/user/app/screen_park_golf_web_service
docker compose rm -f db
docker compose up -d
```

아래 명령은 DB volume까지 삭제할 수 있으므로 운영 데이터가 있으면 사용하지 않습니다.

```bash
docker compose down -v
```

## 백업에서 복원

복원은 기존 DB 내용을 덮어쓸 수 있으므로, 먼저 현재 상태의 백업을 하나 더 만든 뒤 진행합니다.

```bash
deploy/wsl/backup-db.sh
```

복원할 파일을 지정해 실행합니다.

```bash
docker compose exec -T db sh -lc 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-privileges' < backups/screen_golf_YYYYMMDD_HHMMSS.dump
```

복원 후 상태를 확인합니다.

```bash
docker compose ps
curl http://localhost:8000/api/health
```
