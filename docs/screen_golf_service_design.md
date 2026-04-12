# 스크린골프 파크장 서비스 설계서

## 1. 문서 개요

### 1.1 문서 목적
본 문서는 **스크린골프 파크장 운영을 위한 웹 서비스**의 설계 방향을 정의한다.  
서비스의 핵심 목적은 다음과 같다.

- 회원 정보를 쉽게 등록·조회·수정할 수 있도록 지원
- 정기권, 쿠폰, 타석 이용료 매출을 체계적으로 관리
- 일별/월별 매출을 한눈에 확인. 기간별 조회 가능.
- 문자메시지 단체 발송 및 발송 이력 관리. 예약 메세지 전송 및 관리
- 운영 문서(공지, 이용안내, 정산자료 등) 업로드 및 보관
- 고령 관리자도 쉽게 사용할 수 있는 단순하고 직관적인 UI 제공

### 1.2 대상 사용자
- **주 운영자(관리자)**: 60~70대, PC 사용이 익숙하지 않을 수 있음
- **보조 운영자**: 데스크 직원 또는 가족/지인
- **시스템 관리자**: 윈도우 + WSL + Docker 환경에서 서비스 유지보수 담당

### 1.3 서비스 운영 환경
- 호스트 OS: **Windows**
- 실행 환경: **WSL2**
- 배포 방식: **Docker Compose 기반 컨테이너 운영**
- 접속 방식: 내부망 또는 지정된 외부망에서 브라우저 접속

---

## 2. 설계 원칙

### 2.1 사용성 우선
운영자가 고령층이라는 점을 고려하여 다음 원칙을 적용한다.

- 메뉴 수를 최소화한다.
- 화면마다 주요 버튼을 크게 배치한다.
- 중요한 기능은 2~3단계 안에 수행 가능하도록 한다.
- 복잡한 용어 대신 쉬운 한글 표현을 사용한다.
- 오입력 방지를 위해 확인창과 자동완성 기능을 제공한다.

### 2.2 운영 안정성
- 데이터 입력 실수를 줄이기 위해 필수값 검증 수행
- 삭제 대신 **비활성화/보관 처리** 우선. 비활성화 데이터는 필요시 모두 조회가능하게.
- 문자 발송, 쿠폰 차감, 매출 수정은 이력 로그를 남김
- 컨테이너 재기동 시에도 데이터가 유지되도록 볼륨 분리

### 2.3 확장성
향후 다음 기능 확장이 가능하도록 설계한다.

- 예약 관리
- 타석/방 배정 관리
- 키오스크 연동
- 카드결제/PG 연동
- 카카오 알림톡 연동
- 통계 대시보드 고도화

---

## 3. 서비스 범위

### 3.1 전체 서비스 핵심 기능
1. **회원관리**
2. **정기권 및 쿠폰 관리**
3. **매출관리**
4. **문자메시지 단체발송 및 관리**
5. **문서관리**
6. **로그 및 백업 관리**

> 1차 MVP 범위는 15.1을 기준으로 하며, 문자메시지와 문서관리는 2단계 기능으로 분리한다.

### 3.2 제외 범위(1차 개발)
- 실시간 결제 연동
- 모바일 앱 개발
- AI 기반 추천 기능
- POS/출입통제 외부 장비 직접 연동

---

## 4. 사용자 시나리오

### 4.1 신규 회원 등록
1. 관리자가 `회원등록` 메뉴 진입
2. 이름, 휴대전화(포맷자동검사), 생년월일(선택), 성별(선택), 메모 입력. 이메일(포멧자동검사. 필수아님.). 주소(필수아님)
3. 저장 버튼 클릭
4. 시스템이 중복 휴대전화 여부 확인
5. 저장 완료 후 회원 상세 화면으로 이동

### 4.2 매출 입력 및 회원별 자동 기록
1. 운영자가 `매출관리` 메뉴에서 매출 등록 화면 진입
2. 회원을 검색/선택하거나 이름, 휴대전화 등 회원정보 입력
3. 매출 유형 선택: `정기권 구매`, `타석 이용료`, `쿠폰 구매`, `레슨`, `골프용품`, `기타`
4. 정기권은 `한달` 또는 `지정 일수`를 선택하고, 쿠폰은 기본 10회 또는 직접 입력. 레슨은 레슨 담당자, 레슨 회수 입력. 골프 용품은 품목, 메모 입력. 기타는 메모 입력
5. 저장 시 매출 기록 생성
6. 회원정보가 입력되어 기존 회원과 매칭되거나 신규 회원으로 저장되면 해당 회원의 매출 이력에도 자동 연결. 매출 등록시에 회원이름은 현재 시스템에 등록된 회원 선택 가능하게(중복고려해야함)

### 4.3 단체 문자 발송
1. `문자발송` 메뉴 진입
2. 발송 대상 선택(전체회원, 정기권 만료 예정자, 특정 그룹(전체그룹은 자동생성, 시스템에 그룹관리가능, 다중그룹 선택가능))
3. 문자 내용 작성
4. 발송 전 대상 인원 확인. 제외 가능. 추가가능. 수정가능
5. 발송 후 성공/실패 결과 저장
6. 이력 조회 가능

### 4.4 일일 매출 확인
1. `매출관리` 메뉴 진입
2. 오늘 날짜 기준 매출 요약 자동 표시. 기간 선택 및 조회가능. 그래프로도 별도표시
3. 카드/현금/정기권/타석 이용료/쿠폰 등 유형별 합계 확인
4. 필요 시 엑셀 다운로드

---

## 5. 기능 요구사항

### 5.1 회원관리

#### 5.1.1 주요 기능
- 회원 등록 / 조회 / 수정 / 비활성화
- 이름, 전화번호, 메모 기반 검색
- 최근 방문일 확인
- 회원별 정기권/쿠폰 보유 현황 확인
- 회원별 매출 이력 자동 기록 및 조회
- 문자 수신 동의 여부 관리. 문자 발송시에 문자 수신 미동의 사용자 목록 출력해서 발송시점에 알수있게.
- 회원별 특이사항 메모

#### 5.1.2 화면 요구사항
- 상단에 **큰 검색창** 배치
- 검색 결과는 글자 크기를 크게 표시
- 회원 상세 화면에서 `정기권/쿠폰`, `매출`, `문자이력`을 탭으로 구분

#### 5.1.3 검증 규칙
- 이름: 필수
- 휴대전화: 숫자 형식 검증
- 동일 전화번호 중복 등록 시 경고

---

### 5.2 정기권 및 쿠폰 관리

#### 5.2.1 주요 기능
- 정기권 상품 등록
- 쿠폰 상품 등록
- 매출 입력과 연동된 회원별 정기권/쿠폰 생성
- 횟수 차감 / 기간 만료 관리
- 만료 예정 회원 조회
- 정지/재개 처리
- 정기권/쿠폰 변경 및 수기 보정 이력 저장

#### 5.2.2 상품 예시
- 1개월 정기권
- 지정 일수 정기권
- 10회 쿠폰
- 직접 입력 쿠폰

#### 5.2.3 요구사항
- 쿠폰 사용 시 잔여 횟수 자동 계산
- 정기권은 한달 또는 지정 일수 기준으로 만료일 자동 계산
- 정기권/쿠폰 수정 시 변경 전/후 이력 저장

---

### 5.3 매출관리

#### 5.3.1 주요 기능
- 매출 발생 시마다 매출 등록
- 일별/월별 매출 조회
- 결제수단별 구분
- 정기권 구매, 타석 이용료, 쿠폰 구매 입력
- 회원정보가 입력된 매출은 회원별 매출 이력에 자동 연결
- 정기권/쿠폰 구매 매출은 정기권 또는 쿠폰 정보 자동 생성
- 수기 매출 입력 가능
- 환불 처리 및 환불 이력 저장
- 매출 통계 제공

#### 5.3.2 분류 기준 예시
- 정기권 구매
- 타석 이용료
- 쿠폰 구매
- 레슨비
- 음료/부가상품
- 기타

#### 5.3.3 결제 수단 예시
- 현금
- 카드
- 계좌이체
- 기타

#### 5.3.4 대시보드 항목
- 오늘 매출
- 이번 달 누적 매출
- 결제수단별 비중
- 상품별 판매 순위
- 환불 건수

---

### 5.4 문자메시지 관리(2단계)

#### 5.4.1 주요 기능
- 단건 / 단체 문자 발송
- 대상 조건 필터링
- 예약 발송(2차 개발 가능)
- 발송 이력 조회
- 실패 건 재발송
- 자주 쓰는 문구 템플릿 저장

#### 5.4.2 대상 필터 예시
- 전체 회원
- 최근 방문 회원
- 장기 미방문 회원
- 정기권 만료 7일 전 회원
- 특정 태그 회원(태그 기능 추가 후)

#### 5.4.3 문자 템플릿 예시
- 정기권 만료 안내
- 휴장 공지
- 이벤트 안내
- 예약 확인

#### 5.4.4 주의사항
- 문자 발송 기능은 외부 SMS API 연동 방식으로 설계
- 발송 전 미리보기와 발송 건수 확인 필수
- 개인정보 보호 및 광고성 문자 법규 검토 필요

---

### 5.5 문서관리(2단계)

#### 5.5.1 주요 기능
- 운영 문서 업로드
- 문서 목록 조회
- 다운로드
- 카테고리 분류
- 버전/업로드일 확인

#### 5.5.2 대상 문서 예시
- 공지문
- 회원 안내문
- 정산자료
- 계약서
- 운영 매뉴얼
- 이벤트 홍보물

#### 5.5.3 요구사항
- 파일명 중복 시 버전 처리 또는 업로드일 기준 구분
- PDF, 이미지, 엑셀, 한글, 워드 파일 업로드 허용
- 파일당 최대 용량은 기본 20MB로 제한
- 중요 문서는 내부 운영 화면에서만 열람
- 문서 삭제는 실제 파일 삭제보다 숨김 처리 우선

---

## 6. 비기능 요구사항

### 6.1 성능
- 일반 조회 화면 응답시간: 3초 이내
- 동시 접속 사용자 수: 소규모 운영 기준 5~20명 수준
- 검색 기능은 이름/전화번호 기준 빠르게 동작해야 함

### 6.2 가용성
- 도커 컨테이너 재시작 후 자동 복구 가능
- DB 데이터는 영속 볼륨에 저장
- 정기 백업 수행

### 6.3 보안
- 운영 화면은 내부망, VPN, IP 제한 등으로 접근 범위 최소화
- 단일 운영자 로그인은 필요 시 환경설정 기반으로 단순 적용
- HTTPS 적용 권장
- 장시간 미사용 시 자동 잠금 또는 재확인 처리
- 주요 작업 로그 저장
- 개인정보 최소 수집 원칙 적용

### 6.4 유지보수성
- 프론트엔드/백엔드/API 구조 분리
- 환경변수 기반 설정 관리
- 로그 파일 분리
- Docker Compose로 재현 가능한 배포 구조 유지

---

## 7. 추천 시스템 아키텍처

### 7.1 전체 구조

```text
[사용자 브라우저]
        |
        v
[웹 프론트엔드]
        |
        v
[백엔드 API 서버]
        |
   +----+----------------+
   |                     |
   v                     v
[DB 서버]          [파일 저장소]
   |
   v
[백업 저장소]
```

### 7.2 권장 기술 스택
운영 편의성과 개발 생산성을 고려한 권장안이다.

#### 프론트엔드
- React 권장
- 단순한 화면부터 시작할 경우 HTML / CSS / JavaScript도 가능하나, MVP 구현 기준은 React로 통일

> 관리자 화면은 복잡한 애니메이션보다 단순하고 큰 버튼, 큰 글씨, 명확한 배치가 더 중요하다.

#### 백엔드
- Python FastAPI 권장
- Node.js Express/NestJS는 대체안으로만 검토

> 빠른 개발과 유지보수를 고려하면 **FastAPI**가 유리하다.

#### 데이터베이스
- PostgreSQL 권장
- 다중 사용자, 이력관리, 백업 운영을 고려하여 MVP부터 PostgreSQL을 기본 DB로 사용

#### 파일 저장
- 로컬 볼륨 저장
- 향후 필요 시 NAS 또는 오브젝트 스토리지 연동 확장 가능

#### 문자 발송 연동
- 국내 SMS API 사업자 연동
- 발송 요청/응답 로그 저장 구조 포함

---

## 8. 배포 구조 설계

### 8.1 Docker Compose 구성 예시

```text
services:
  frontend:
    - 관리자 웹 화면 제공
  backend:
    - 회원/정기권/쿠폰/매출/문자/문서 API 제공
  db:
    - PostgreSQL
  nginx:
    - 리버스 프록시, HTTPS, 정적 파일 처리
```

### 8.2 권장 디렉토리 구조

```text
screen_park_golf_service/
├─ docker-compose.yml
├─ .env
├─ frontend/
├─ backend/
├─ nginx/
├─ db/
│  ├─ migrations/
│  └─ raw/
├─ uploads/
├─ backups/
└─ docs/
```

### 8.3 운영 포인트
- `uploads/`는 문서 업로드 파일 저장
- `backups/`는 DB 백업 파일 저장
- `db/raw/`는 초기 정리용 원천 엑셀 자료 보관(개인정보 포함 가능, Git 추적 제외)
- `.env`에는 비밀번호, API 키, DB 접속정보 저장
- WSL 내부 경로와 Windows 경로 간 권한 차이를 고려해야 함

---

## 9. 화면 설계 방향

### 9.1 공통 UI 정책
- 글자 크기 크게
- 버튼 크기 크게
- 주요 버튼 색상 통일
- 저장/삭제 버튼을 멀리 배치하여 오작동 방지
- 화면 상단에 현재 위치 표시
- 뒤로가기보다 **홈 버튼** 중심 설계

### 9.2 메인 메뉴 구성

전체 서비스 기준 메뉴 구성은 다음과 같다. 1단계 MVP에서는 `문자발송`, `문서관리`, `통계현황`은 제외하고 2단계 이후 추가한다.

```text
[홈]
 ├─ 회원관리
 ├─ 정기권/쿠폰관리
 ├─ 매출관리
 ├─ 문자발송
 ├─ 문서관리
 ├─ 통계현황
 └─ 환경설정
```

### 9.3 홈 대시보드 구성
- 오늘 신규 등록 수
- 오늘 매출
- 만료 예정 정기권 수
- 최근 문자 발송 결과(2단계 이후)
- 자주 사용하는 메뉴 바로가기

### 9.4 화면별 우선순위
1. 홈
2. 회원 검색/상세
3. 매출 등록
4. 매출 조회
5. 문자 발송
6. 문서 업로드/조회

> 1~4번은 1단계 MVP, 5~6번은 2단계 구현 대상으로 본다.

---

## 10. 데이터베이스 설계

### 10.1 주요 엔티티
- members
- membership_products
- member_memberships
- membership_usage_logs
- sales
- sms_messages
- sms_message_recipients
- sms_templates
- documents
- audit_logs

### 10.2 테이블 초안

#### 10.2.1 members
| 컬럼명 | 타입 | 설명 |
|---|---|---|
| id | bigint | PK |
| name | varchar | 회원명 |
| phone | varchar | 휴대전화 |
| birth_date | date | 생년월일 |
| gender | varchar | 성별 |
| sms_agree | boolean | 문자 수신 동의 |
| memo | text | 특이사항 |
| last_visit_at | timestamp | 최근 방문일 |
| is_active | boolean | 활성 여부 |
| created_at | timestamp | 생성일 |
| updated_at | timestamp | 수정일 |

#### 10.2.2 membership_products
| 컬럼명 | 타입 | 설명 |
|---|---|---|
| id | bigint | PK |
| name | varchar | 상품명 |
| product_type | varchar | 정기권/쿠폰 |
| duration_days | int | 유효기간 |
| total_count | int | 총 횟수 |
| price | numeric | 판매가 |
| is_active | boolean | 판매 여부 |
| created_at | timestamp | 생성일 |
| updated_at | timestamp | 수정일 |

#### 10.2.3 member_memberships
| 컬럼명 | 타입 | 설명 |
|---|---|---|
| id | bigint | PK |
| member_id | bigint | 회원 ID |
| product_id | bigint | 상품 ID |
| start_date | date | 시작일 |
| end_date | date | 종료일 |
| duration_type | varchar | 한달/지정일수 |
| duration_days | int | 정기권 유효 일수 |
| total_count | int | 총 횟수 |
| remaining_count | int | 잔여 횟수 |
| status | varchar | 사용중/만료/정지 |
| sold_price | numeric | 실제 판매금액 |
| source_sale_id | bigint | 생성 원인이 된 매출 ID |
| created_at | timestamp | 생성일 |
| updated_at | timestamp | 수정일 |

#### 10.2.4 membership_usage_logs
| 컬럼명 | 타입 | 설명 |
|---|---|---|
| id | bigint | PK |
| member_membership_id | bigint | 정기권/쿠폰 ID |
| member_id | bigint | 회원 ID |
| action_type | varchar | 사용/보정/취소 |
| change_count | int | 차감 또는 복원 횟수 |
| before_remaining_count | int | 변경 전 잔여 횟수 |
| after_remaining_count | int | 변경 후 잔여 횟수 |
| note | text | 사유 |
| operator_name | varchar | 작업자명 |
| created_at | timestamp | 작업일 |

#### 10.2.5 sales
| 컬럼명 | 타입 | 설명 |
|---|---|---|
| id | bigint | PK |
| member_id | bigint | 회원 ID |
| member_name_snapshot | varchar | 매출 당시 회원명 |
| member_phone_snapshot | varchar | 매출 당시 휴대전화 |
| sale_type | varchar | 정기권구매/타석이용료/쿠폰구매/기타 |
| payment_method | varchar | 결제수단 |
| amount | numeric | 금액 |
| sale_date | date | 매출일 |
| related_membership_id | bigint | 관련 정기권/쿠폰 ID |
| duration_type | varchar | 한달/지정일수 |
| duration_days | int | 정기권 유효 일수 |
| coupon_count | int | 쿠폰 횟수 |
| status | varchar | 정상/환불/부분환불/취소 |
| original_sale_id | bigint | 환불 매출의 원매출 ID |
| note | text | 메모 |
| operator_name | varchar | 입력자명 |
| created_at | timestamp | 생성일 |
| refunded_at | timestamp | 환불일 |
| updated_at | timestamp | 수정일 |

#### 10.2.6 sms_messages
| 컬럼명 | 타입 | 설명 |
|---|---|---|
| id | bigint | PK |
| target_type | varchar | 단건/단체 |
| title | varchar | 템플릿명 또는 제목 |
| content | text | 문자 내용 |
| target_count | int | 대상 수 |
| success_count | int | 성공 수 |
| fail_count | int | 실패 수 |
| status | varchar | 대기/발송중/완료/실패 |
| provider_request_id | varchar | SMS API 요청 ID |
| sent_at | timestamp | 발송시각 |
| operator_name | varchar | 발송자명 |
| created_at | timestamp | 생성일 |

#### 10.2.7 sms_message_recipients
| 컬럼명 | 타입 | 설명 |
|---|---|---|
| id | bigint | PK |
| sms_message_id | bigint | 문자 발송 ID |
| member_id | bigint | 회원 ID |
| recipient_name | varchar | 수신자명 |
| phone | varchar | 발송 전화번호 |
| status | varchar | 성공/실패 |
| provider_message_id | varchar | SMS API 메시지 ID |
| fail_code | varchar | 실패 코드 |
| fail_reason | text | 실패 사유 |
| sent_at | timestamp | 발송시각 |

#### 10.2.8 sms_templates
| 컬럼명 | 타입 | 설명 |
|---|---|---|
| id | bigint | PK |
| title | varchar | 템플릿명 |
| content | text | 문자 내용 |
| is_active | boolean | 사용 여부 |
| operator_name | varchar | 생성자명 |
| created_at | timestamp | 생성일 |
| updated_at | timestamp | 수정일 |

#### 10.2.9 documents
| 컬럼명 | 타입 | 설명 |
|---|---|---|
| id | bigint | PK |
| category | varchar | 문서 분류 |
| file_name | varchar | 저장 파일명 |
| original_name | varchar | 원본 파일명 |
| file_path | varchar | 저장 경로 |
| file_size | bigint | 파일 크기 |
| mime_type | varchar | 파일 형식 |
| is_hidden | boolean | 숨김 여부 |
| hidden_at | timestamp | 숨김 처리일 |
| hidden_by_name | varchar | 숨김 처리자명 |
| uploader_name | varchar | 업로더명 |
| created_at | timestamp | 업로드일 |
| updated_at | timestamp | 수정일 |

#### 10.2.10 audit_logs
| 컬럼명 | 타입 | 설명 |
|---|---|---|
| id | bigint | PK |
| actor_name | varchar | 작업자명 |
| action_type | varchar | 작업 유형 |
| target_type | varchar | 대상 종류 |
| target_id | bigint | 대상 ID |
| before_data | jsonb | 변경 전 |
| after_data | jsonb | 변경 후 |
| created_at | timestamp | 작업 시각 |

### 10.3 주요 제약 및 인덱스
- `members.phone`은 숫자만 저장하고, 활성 회원 기준 중복을 막는 unique partial index를 둔다.
- `members.name`, `members.phone`은 검색 성능을 위해 인덱스를 둔다.
- `sales.sale_date`, `member_memberships.status`, `member_memberships.end_date`는 조회 조건으로 자주 사용하므로 인덱스를 둔다.
- 회원, 정기권/쿠폰, 매출, 문자, 문서 관련 참조 컬럼은 외래키로 연결한다.
- `sales.member_id`는 비회원 매출을 허용하기 위해 nullable로 두되, 회원정보가 입력되면 기존 회원 매칭 또는 신규 회원 생성 후 자동 연결한다.

---

## 11. API 설계 초안

### 11.1 공통 API 규칙
- 목록 API는 `page`, `size`, `keyword`, 날짜 범위 조건을 필요한 범위에서 지원한다.
- 오류 응답은 `{ code, message }` 형식으로 통일하고, `message`는 운영자가 이해하기 쉬운 한글 문구로 제공한다.
- 생성/수정/차감/환불/숨김 처리 API는 감사 로그를 남긴다.

### 11.2 회원관리 API
- `GET /api/members?keyword=&page=&size=`
- `POST /api/members`
- `GET /api/members/{id}`
- `PUT /api/members/{id}`
- `PATCH /api/members/{id}/deactivate`
- `GET /api/members/{id}/sales`

### 11.3 정기권/쿠폰 API
- `GET /api/membership-products`
- `POST /api/membership-products`
- `POST /api/member-memberships`
- `PATCH /api/member-memberships/{id}/pause`
- `PATCH /api/member-memberships/{id}/resume`
- `POST /api/member-memberships/{id}/deduct`
- `POST /api/member-memberships/{id}/adjust`
- `GET /api/member-memberships/{id}/usage-logs`

### 11.4 매출 API
- `GET /api/sales?from_date=&to_date=&page=&size=`
- `POST /api/sales`
- `GET /api/sales/summary/daily`
- `GET /api/sales/summary/monthly`
- `POST /api/sales/{id}/refund`

`POST /api/sales`는 매출 유형에 따라 다음 후속 처리를 함께 수행한다.
- `정기권 구매`: 한달 또는 지정 일수 기준으로 정기권 생성
- `쿠폰 구매`: 기본 10회 또는 입력 횟수 기준으로 쿠폰 생성
- `타석 이용료`: 회원정보가 있으면 회원 매출 이력에만 연결

### 11.5 문자 API
- `POST /api/sms/send`
- `GET /api/sms/history`
- `GET /api/sms/{id}/recipients`
- `GET /api/sms/templates`
- `POST /api/sms/templates`
- `PUT /api/sms/templates/{id}`

### 11.6 문서 API
- `GET /api/documents`
- `POST /api/documents/upload`
- `GET /api/documents/{id}/download`
- `PATCH /api/documents/{id}/hide`
- `PATCH /api/documents/{id}/restore`

---

## 12. 업무 규칙

### 12.1 회원 관련 규칙
- 휴대전화는 숫자만 정규화하여 저장하고 회원 식별의 핵심 기준으로 사용
- 활성 회원 간 동일 번호 중복 등록은 저장 단계에서 차단
- 비활성 회원과 번호가 같으면 기존 회원 재활성화 또는 운영자 확인 후 신규 등록
- 탈퇴 대신 비활성화 처리 우선

### 12.2 정기권/쿠폰 관련 규칙
- 정기권 또는 쿠폰 구매 매출 저장 시 정기권/쿠폰 정보를 자동 생성
- 정기권은 `한달` 선택 시 기본 1개월, `지정 일수` 선택 시 입력 일수로 만료일 계산
- 쿠폰은 기본 10회로 시작하고 운영자가 횟수를 직접 수정 가능
- 정기권/쿠폰 환불 시 원매출과 연결된 음수 환불 매출 기록 생성
- 환불 시 원매출의 상태를 `환불` 또는 `부분환불`로 변경
- 잔여 횟수 차감, 보정, 취소는 `membership_usage_logs`에 기록
- 만료 정기권은 자동 상태 변경 가능

### 12.3 매출 입력 규칙
- 모든 매출은 발생 시점마다 `매출관리`에서 직접 입력
- 매출 유형은 `정기권 구매`, `타석 이용료`, `쿠폰 구매`, `기타`를 기본값으로 사용
- 회원 이름 또는 휴대전화가 입력되면 기존 회원을 우선 검색하고, 일치 회원이 있으면 `sales.member_id`에 자동 연결
- 일치 회원이 없으면 비회원 매출로 저장하고, 필요하면 회원등록 후 다시 연결한다
- 회원정보가 없는 매출은 비회원 매출로 저장하되 일별/월별 통계에는 포함
- 회원과 연결된 매출은 회원 상세 화면의 `매출` 탭에 자동 표시

### 12.4 문자 관련 규칙
- 수신동의 회원만 광고성 문자 발송 대상 포함
- 발송 전 대상 인원, 예상 비용, 문자 내용을 미리보기로 확인
- 발송 묶음은 `sms_messages`, 개별 수신 결과는 `sms_message_recipients`에 저장
- 발송 실패 건은 수신자별 실패 코드와 실패 사유 저장
- 동일 메시지 재발송 시 중복 발송 경고 가능

### 12.5 문서 관련 규칙
- 문서 삭제는 실제 삭제보다 숨김 처리 우선
- 중요 문서는 내부 운영 화면에서만 열람
- 업로드 파일은 허용 확장자, 최대 용량, MIME 타입을 검증
- 저장 파일명은 UUID 등으로 변경하고 원본 파일명은 별도 보관

---

## 13. 보안 및 개인정보 보호

### 13.1 보호 대상 정보
- 회원 이름
- 휴대전화
- 생년월일
- 결제/매출 관련 정보

### 13.2 보안 대책
- 운영 화면은 내부망, VPN, IP 제한 등으로 접근 범위 최소화
- 단일 운영자 로그인은 필요 시 별도 계정관리 화면 없이 환경설정 기반으로 시작
- 장시간 미사용 시 자동 잠금 또는 재확인 처리
- 감사 로그 저장
- 업로드 파일 확장자, MIME 타입, 용량 제한
- 업로드 파일 저장명 난수화 및 실행 권한 차단
- DB 정기 백업
- 운영 화면 외부 공개 최소화

### 13.3 권장 추가 사항
- 사설망 운영 시에도 HTTPS 적용
- 운영자 IP 제한 가능하면 적용
- 외부 공개 시 VPN 또는 접근제어 권장

---

## 14. 백업 및 장애 대응

### 14.1 백업 정책
- DB: 일 1회 자동 백업
- 업로드 문서: 일 1회 또는 변경 시 백업
- 백업 파일 보관: 최근 7일, 주간 4회, 월간 3회 권장

### 14.2 장애 대응
- 컨테이너 재시작 절차 문서화
- DB 복구 절차 문서화
- `.env`, `docker-compose.yml`, 업로드 파일, 백업 파일 별도 보관

### 14.3 운영 점검 항목
- 운영 화면 접속 정상 여부
- 회원 검색 정상 여부
- 문자 발송 API 연결 상태(2단계 이후)
- 디스크 사용량
- DB 백업 성공 여부

---

## 15. 개발 우선순위 제안

### 15.1 1단계(MVP)
- 회원관리
- 정기권/쿠폰 관리
- 매출관리
- 기본 대시보드

### 15.2 2단계
- 문자 단체발송
- 문서관리
- 엑셀 다운로드
- 상세 통계

### 15.3 3단계
- 예약관리
- 알림 자동화
- 외부 서비스 연동
- 모바일 대응 고도화

---

## 16. 1단계 MVP 화면 목록 제안

1. 홈 대시보드
2. 회원 목록/검색 화면
3. 회원 상세 화면
4. 회원 등록/수정 화면
5. 상품/요금 관리 화면
6. 매출 등록 화면
7. 정기권/쿠폰 사용/보정 이력 화면
8. 매출 목록/등록 화면
9. 매출 환불 처리 화면

문자 발송, 문서 목록/업로드, 엑셀 다운로드, 상세 통계 화면은 2단계에서 추가한다.

---

## 17. 구현 시 권장 사항

### 17.1 프론트엔드
- 모바일 우선보다 **데스크탑 운영 화면 최적화** 우선
- 테이블은 너무 빽빽하지 않게 설계
- 검색과 상세 보기 중심 UX 구성

### 17.2 백엔드
- CRUD + 이력관리 구조를 먼저 안정화
- 공통 응답 형식 통일
- 예외 발생 시 사용자에게 쉬운 문구 제공

### 17.3 데이터 처리
- 숫자/금액/횟수 입력은 자동 포맷팅
- 날짜 선택기는 큰 UI로 제공
- 입력 후 저장 성공 메시지를 명확히 표시

---

## 18. 결론
본 서비스는 화려한 기능보다 **운영자가 쉽게 배우고 매일 실수 없이 사용하는 것**이 가장 중요하다.  
따라서 1차 개발에서는 다음 3가지를 최우선으로 삼는다.

1. **회원을 빠르게 찾을 수 있는 검색 중심 구조**
2. **정기권/쿠폰과 매출이 자동으로 연결되는 단순한 업무 흐름**
3. **고령 관리자도 사용할 수 있는 쉬운 화면 구성**

또한 Windows + WSL + Docker 환경에 맞춰 배포와 백업, 복구 절차까지 함께 설계해야 실제 운영이 가능하다.

---

## 19. 권장 다음 작업

1. 화면 와이어프레임 작성
2. DB 스키마 확정
3. API 명세 상세화
4. Docker Compose 개발환경 구성
5. MVP 기능부터 단계별 구현
