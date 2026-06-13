from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query

from .config import settings
from .models import (
    BrokerAccountSummary,
    BrokerCancelResponse,
    BrokerOrdersResponse,
    BrokerPositionsResponse,
    CancelOrderRequest,
    DaemonStatusResponse,
    ProcessOrdersRequest,
    ProcessOrdersResponse,
    SubmitOrderRequest,
    BrokerOrderResponse,
    TerminalPreflightResponse,
    TerminalSessionControlRequest,
    TerminalSessionControlResponse,
    TerminalSessionStatus,
)
from .services import BrokerDaemonService, TerminalAdapterError

service = BrokerDaemonService()


def _authorize(authorization: str | None = Header(default=None)) -> None:
    if not settings.api_key:
        return
    expected = f"Bearer {settings.api_key}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await service.start()
    try:
        yield
    finally:
        await service.stop()


app = FastAPI(title="brokerd", version="0.1.0", lifespan=lifespan)


@app.get("/status", response_model=DaemonStatusResponse)
def status(_auth: None = Depends(_authorize)) -> DaemonStatusResponse:
    return service.status()


@app.get("/session", response_model=TerminalSessionStatus)
def session_status(_auth: None = Depends(_authorize)) -> TerminalSessionStatus:
    return service.session_status()


@app.get("/session/health", response_model=TerminalSessionStatus)
def session_health(_auth: None = Depends(_authorize)) -> TerminalSessionStatus:
    try:
        return service.session_health_check()
    except TerminalAdapterError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@app.get("/preflight", response_model=TerminalPreflightResponse)
def preflight(_auth: None = Depends(_authorize)) -> TerminalPreflightResponse:
    try:
        return service.preflight()
    except TerminalAdapterError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@app.post("/session/connect", response_model=TerminalSessionControlResponse)
def session_connect(
    request: TerminalSessionControlRequest,
    _auth: None = Depends(_authorize),
) -> TerminalSessionControlResponse:
    try:
        return service.connect_session(request)
    except TerminalAdapterError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@app.post("/session/login", response_model=TerminalSessionControlResponse)
def session_login(
    request: TerminalSessionControlRequest,
    _auth: None = Depends(_authorize),
) -> TerminalSessionControlResponse:
    try:
        return service.login_session(request)
    except TerminalAdapterError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@app.post("/session/disconnect", response_model=TerminalSessionControlResponse)
def session_disconnect(
    request: TerminalSessionControlRequest,
    _auth: None = Depends(_authorize),
) -> TerminalSessionControlResponse:
    try:
        return service.disconnect_session(request)
    except TerminalAdapterError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@app.post("/session/start", response_model=TerminalSessionControlResponse)
def session_start(
    request: TerminalSessionControlRequest,
    _auth: None = Depends(_authorize),
) -> TerminalSessionControlResponse:
    try:
        return service.start_terminal(request)
    except TerminalAdapterError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@app.post("/orders", response_model=BrokerOrderResponse)
def submit_order(request: SubmitOrderRequest, _auth: None = Depends(_authorize)) -> BrokerOrderResponse:
    try:
        return service.submit_order(request)
    except TerminalAdapterError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@app.post("/orders/cancel", response_model=BrokerCancelResponse)
def cancel_order(request: CancelOrderRequest, _auth: None = Depends(_authorize)) -> BrokerCancelResponse:
    try:
        return service.cancel_order(request)
    except TerminalAdapterError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@app.post("/orders/process", response_model=ProcessOrdersResponse)
def process_orders(
    request: ProcessOrdersRequest,
    _auth: None = Depends(_authorize),
) -> ProcessOrdersResponse:
    try:
        return service.process_orders(request)
    except TerminalAdapterError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@app.get("/orders", response_model=BrokerOrdersResponse)
def orders(
    account_id: str = Query(..., min_length=1),
    _adapter: str | None = Query(default=None),
    _auth: None = Depends(_authorize),
) -> BrokerOrdersResponse:
    try:
        return service.orders(account_id)
    except TerminalAdapterError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@app.get("/positions", response_model=BrokerPositionsResponse)
def positions(
    account_id: str = Query(..., min_length=1),
    _adapter: str | None = Query(default=None),
    _auth: None = Depends(_authorize),
) -> BrokerPositionsResponse:
    try:
        return service.positions(account_id)
    except TerminalAdapterError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@app.get("/account", response_model=BrokerAccountSummary)
def account(
    account_id: str = Query(..., min_length=1),
    _adapter: str | None = Query(default=None),
    _auth: None = Depends(_authorize),
) -> BrokerAccountSummary:
    try:
        return service.account(account_id)
    except TerminalAdapterError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
