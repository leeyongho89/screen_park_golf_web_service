# 다른 WSL 환경 배포 가이드

이 문서는 이 저장소를 **다른 Windows PC의 WSL 2 환경**에 배포하고, **Windows를 재부팅해도 자동으로 다시 올라오게** 만드는 절차입니다.

기준 경로 예시는 아래처럼 잡았습니다.

- WSL 배포 경로: `/opt/screen_park_golf_service`
- WSL 배포 배포판 이름: `Ubuntu`
- 외부 접속 주소: `http://localhost:8080`

실제 운영에서는 경로와 배포판 이름만 바꿔서 적용하면 됩니다.

## 권장 구성

운영 기준으로는 아래 구성이 가장 단순합니다.

1. Windows에 WSL 2 설치
2. WSL 안에 Ubuntu 설치
3. WSL 안에 **Docker Engine + docker compose plugin** 설치
4. 이 저장소를 WSL Linux 파일시스템 안에 복사
5. `.env` 설정
6. `docker compose up -d --build`로 기동
7. WSL 안에는 `systemd` 서비스 등록
8. Windows 쪽에는 **작업 스케줄러(Task Scheduler)** 로 `wsl.exe` 실행 등록

이 방식으로 하는 이유:

- 저장소가 이미 `docker compose` 기준으로 구성되어 있음
- Windows 재부팅 후 WSL이 자동으로 떠야 하므로 `systemd`만으로는 부족함
- Microsoft 문서 기준으로, **systemd 서비스만으로는 WSL 인스턴스를 계속 살려두지 않음**

참고:

- Microsoft Learn, systemd on WSL  
  https://learn.microsoft.com/en-us/windows/wsl/systemd
- Docker Engine on Ubuntu  
  https://docs.docker.com/engine/install/ubuntu/

## 1. Windows에서 WSL 준비

관리자 PowerShell에서 확인:

```powershell
wsl --version
wsl -l -v
```

`wsl --version` 이 동작하지 않으면 WSL을 최신으로 업데이트합니다.

```powershell
wsl --update
```

Ubuntu가 없다면 설치:

```powershell
wsl --install -d Ubuntu
```

설치 후 기본 확인:

```powershell
wsl -l -v
```

배포판이 `VERSION 2`인지 확인합니다.

## 2. WSL 안에서 systemd 활성화

Ubuntu 셸에서:

```bash
sudo nano /etc/wsl.conf
```

아래 내용을 넣습니다.

```ini
[boot]
systemd=true
```

저장 후 Windows PowerShell에서 WSL 전체 재시작:

```powershell
wsl --shutdown
```

다시 Ubuntu에 들어와 확인:

```bash
systemctl status
```

## 3. WSL 안에 Docker Engine 설치

Ubuntu에서 Docker 공식 문서 절차대로 설치합니다.

필수 패키지:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
```

Docker GPG 키와 저장소 등록:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

설치:

```bash
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Docker 자동 시작:

```bash
sudo systemctl enable docker
sudo systemctl start docker
```

현재 사용자로 Docker 실행 허용:

```bash
sudo usermod -aG docker $USER
```

그 뒤 WSL 셸을 완전히 다시 열거나 아래를 실행합니다.

```bash
newgrp docker
```

확인:

```bash
docker version
docker compose version
```

## 4. 저장소 배치

Windows 경로가 아니라 **WSL Linux 파일시스템** 안에 두는 걸 권장합니다.

예:

```bash
sudo mkdir -p /opt
sudo chown -R $USER:$USER /opt
cd /opt
git clone <저장소 URL> screen_park_golf_service
cd /opt/screen_park_golf_service
```

Git을 쓰지 않고 복사해도 됩니다. 중요한 건 최종 경로가 Linux 쪽이어야 한다는 점입니다.

## 5. 환경변수 설정

예제 파일 복사:

```bash
cd /opt/screen_park_golf_service
cp .env.example .env
```

`.env`에서 최소한 아래 항목은 환경에 맞게 바꿉니다.

```env
POSTGRES_DB=screen_golf
POSTGRES_USER=screen_golf
POSTGRES_PASSWORD=강한비밀번호로변경
DATABASE_URL=postgresql+psycopg://screen_golf:강한비밀번호로변경@db:5432/screen_golf
CORS_ORIGINS=http://localhost:5173,http://localhost:8080
VITE_API_URL=/api
OPERATOR_NAME=관리자
TZ=Asia/Seoul
```

문자 발송을 실제로 쓸 예정이면 아래도 추가합니다.

```env
NCP_SMS_SERVICE_ID=
NCP_ACCESS_KEY=
NCP_SECRET_KEY=
NCP_SMS_FROM_NUMBER=
```

## 6. 최초 배포

프로젝트 루트에서:

```bash
cd /opt/screen_park_golf_service
docker compose up -d --build
```

상태 확인:

```bash
docker compose ps
```

접속 확인:

```bash
curl -I http://localhost:8080
curl http://localhost:8000/api/health
```

정상 기준:

- `http://localhost:8080` -> 웹 화면
- `http://localhost:8000/docs` -> FastAPI 문서
- `/api/health` -> `{"status":"ok"}`

## 7. 마이그레이션 주의사항

이 저장소는 `db/migrations/` 파일을 **Postgres 볼륨이 비어 있을 때만 자동 적용**합니다.

즉:

- **새 WSL / 새 볼륨**: `001`, `002`가 자동 적용됨
- **기존 볼륨 재사용**: 새 마이그레이션은 직접 적용해야 함

현재 문자 관련 추가 마이그레이션은 아래 파일입니다.

- [002_sms_groups_and_message_metadata.sql](/home/najano89/projects/screen_park_golf_service/db/migrations/002_sms_groups_and_message_metadata.sql)

기존 볼륨에 수동 반영:

```bash
cd /opt/screen_park_golf_service
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/002_sms_groups_and_message_metadata.sql
```

## 8. WSL 내부 자동 실행 설정

이 저장소에 예시 파일이 들어 있습니다.

- `deploy/wsl/start-screen-golf.sh`
- `deploy/wsl/stop-screen-golf.sh`
- `deploy/wsl/screen-golf.service.example`

실행 권한 부여:

```bash
cd /opt/screen_park_golf_service
chmod +x deploy/wsl/start-screen-golf.sh
chmod +x deploy/wsl/stop-screen-golf.sh
```

systemd 서비스 등록:

```bash
sudo cp deploy/wsl/screen-golf.service.example /etc/systemd/system/screen-golf.service
sudo systemctl daemon-reload
sudo systemctl enable screen-golf.service
sudo systemctl start screen-golf.service
```

확인:

```bash
systemctl status screen-golf.service
docker compose ps
```

## 9. Windows 재부팅 후 자동 시작 설정

중요한 점:

- `screen-golf.service` 는 **WSL이 시작된 뒤**에만 동작합니다.
- Microsoft 문서 기준으로, **systemd 서비스만으로는 WSL 인스턴스를 계속 살려두지 않습니다.**
- 그래서 Windows 쪽에서 `wsl.exe`를 한 번 실행해 WSL을 깨워야 합니다.

이 저장소에 Windows 예시 스크립트가 들어 있습니다.

- `deploy/windows/start-screen-golf-wsl.ps1.example`

예시 내용:

```powershell
$DistroName = "Ubuntu"
$ServiceName = "screen-golf.service"
wsl.exe -d $DistroName --user root -- systemctl start $ServiceName
```

### 작업 스케줄러 등록 방법

Windows 작업 스케줄러에서 새 작업 생성:

1. `작업 만들기`
2. 이름: `Start Screen Golf WSL`
3. `가장 높은 수준의 권한으로 실행` 체크
4. 트리거:
   - 권장 1: `로그온할 때`
   - 권장 2: 운영 PC라면 `시작할 때`
5. 동작:
   - 프로그램/스크립트: `powershell.exe`
   - 인수 추가:

```powershell
-ExecutionPolicy Bypass -File "C:\배포경로\start-screen-golf-wsl.ps1"
```

또는 스크립트 파일 없이 직접:

```powershell
-ExecutionPolicy Bypass -Command "wsl.exe -d Ubuntu --user root -- systemctl start screen-golf.service"
```

작업 등록 후 테스트:

```powershell
schtasks /Run /TN "Start Screen Golf WSL"
```

그 다음 Ubuntu에서:

```bash
systemctl status screen-golf.service
docker compose ps
```

## 10. 운영 중 자주 쓰는 명령

업데이트 배포:

```bash
cd /opt/screen_park_golf_service
git pull
docker compose up -d --build
```

서비스 상태:

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f nginx
```

중지:

```bash
cd /opt/screen_park_golf_service
docker compose down
```

systemd 재시작:

```bash
sudo systemctl restart screen-golf.service
```

## 11. 점검 체크리스트

최종 점검은 아래 순서로 합니다.

1. Windows 재부팅
2. 작업 스케줄러가 실행됐는지 확인
3. `wsl -d Ubuntu`
4. `systemctl status screen-golf.service`
5. `docker compose ps`
6. `curl -I http://localhost:8080`
7. 브라우저에서 `http://localhost:8080` 접속

## 12. 트러블슈팅

### 1) `systemctl` 이 동작하지 않음

원인:

- `/etc/wsl.conf`에 `systemd=true`가 없음
- `wsl --shutdown` 후 재기동을 안 했음

### 2) `docker compose` 가 없음

원인:

- Docker Engine은 설치됐지만 compose plugin이 없음

확인:

```bash
docker compose version
```

### 3) DB 스키마가 일부 없음

원인:

- 예전 Postgres 볼륨을 재사용했고 새 마이그레이션을 안 넣음

조치:

```bash
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/002_sms_groups_and_message_metadata.sql
```

### 4) Windows는 켰는데 서비스가 안 올라옴

원인:

- 작업 스케줄러가 `wsl.exe`를 안 띄움
- 배포판 이름이 `Ubuntu`가 아님
- PowerShell 실행 정책 또는 계정 권한 문제

확인:

```powershell
wsl -l -v
schtasks /Query /TN "Start Screen Golf WSL" /V /FO LIST
```

### 5) 포트 충돌

현재 기본 포트:

- `8080` -> nginx
- `8000` -> backend
- `5173` -> frontend

다른 서비스가 이미 쓰고 있으면 `docker-compose.yml`의 포트 매핑을 바꿔야 합니다.
