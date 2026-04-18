from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.routers import dashboard, members, memberships, products, reservations, sales, sms
from app.services import normalize_legacy_reservation_statuses, seed_default_products


FIELD_LABELS = {
    "name": "이름",
    "phone": "휴대전화",
    "email": "이메일",
    "birth_date": "생년월일",
    "amount": "금액",
    "sale_date": "매출일",
    "product_id": "상품명",
    "sale_type": "상품명",
    "start_date": "시작일",
    "end_date": "종료일",
    "total_count": "횟수",
    "duration_days": "유효 일수",
    "payment_method": "결제수단",
    "bay_number": "타석",
    "customer_name": "예약자명",
    "customer_phone": "예약자 연락처",
    "reservation_date": "예약일",
    "start_time": "시작 시간",
    "end_time": "종료 시간",
}


def validation_message(field: str, error_type: str, message: str) -> str:
    if message.startswith("Value error, "):
        message = message.replace("Value error, ", "", 1)
    if field == "email":
        return "이메일 형식을 확인해 주세요."
    if error_type == "missing":
        return "필수 입력값입니다."
    if error_type in {"string_too_short", "too_short"}:
        return "입력값이 너무 짧습니다."
    if error_type in {"greater_than", "greater_than_equal"}:
        return "0보다 큰 값을 입력해 주세요."
    return message


def clean_validation_errors(exc: RequestValidationError) -> tuple[str, list[dict[str, str]]]:
    details: list[dict[str, str]] = []
    messages: list[str] = []
    for error in exc.errors():
        loc = error.get("loc", [])
        field = str(loc[-1]) if loc else "input"
        label = FIELD_LABELS.get(field, field)
        message = validation_message(field, str(error.get("type", "")), str(error.get("msg", "입력값 오류")))
        details.append({"field": field, "label": label, "message": message})
        messages.append(f"{label}: {message}")
    return " / ".join(messages) if messages else "입력값을 확인해 주세요.", details


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_default_products(db)
        normalize_legacy_reservation_statuses(db)
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"code": "error", "message": str(exc.detail)})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    message, details = clean_validation_errors(exc)
    return JSONResponse(
        status_code=422,
        content={"code": "validation_error", "message": message, "details": details},
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(dashboard.router, prefix="/api")
app.include_router(members.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(memberships.router, prefix="/api")
app.include_router(sales.router, prefix="/api")
app.include_router(reservations.router, prefix="/api")
app.include_router(sms.router, prefix="/api")
