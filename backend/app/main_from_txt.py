from __future__ import annotations

import hashlib
import hmac
import csv
import json
import math
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import StringIO
from pathlib import Path
from typing import Any, Callable, Literal
from urllib.parse import unquote, urlencode
from urllib.request import Request as UrlRequest, urlopen

import jwt
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from jwt import InvalidTokenError
from pydantic import BaseModel, ConfigDict, Field
from .payment import configured_provider
from .member_images import MAX_UPLOAD_BYTES, image_directory, save_image
from starlette.concurrency import run_in_threadpool
from sqlalchemy import Date, DateTime, Float, Integer, String, Text, and_, case, create_engine, func, inspect, or_, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy import cast
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError


BASE_DIR = Path(__file__).resolve().parents[2]
PUBLIC_DIR = BASE_DIR / "public"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'backend' / 'app.db'}")
APP_ENV = os.getenv("APP_ENV", "development").lower()
JWT_SECRET = os.getenv("JWT_SECRET", "development-only-change-this-secret")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin123!")
TAKU_SEC_KEY = os.getenv("TAKU_SEC_KEY", "").strip()

if APP_ENV == "production":
    if JWT_SECRET == "development-only-change-this-secret" or JWT_SECRET.startswith("replace-with") or len(JWT_SECRET) < 32:
        raise RuntimeError("生产环境必须设置至少 32 个字符的非默认 JWT_SECRET")
    if ADMIN_PASSWORD == "Admin123!" or ADMIN_PASSWORD.startswith("replace-with") or len(ADMIN_PASSWORD) < 10:
        raise RuntimeError("生产环境必须设置至少 10 个字符的非默认 ADMIN_PASSWORD")
    if not configured_provider().available:
        raise RuntimeError("生产环境必须配置真实 PAYMENT_PROVIDER；测试或未配置渠道禁止启用提现转账入口")

engine_kwargs: dict[str, Any] = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, future=True, echo=False, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


class Base(DeclarativeBase):
    pass


def now() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now, nullable=False)


class AdminUser(Base, TimestampMixin):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    mobile: Mapped[str] = mapped_column(String(32), default="", server_default="")
    avatar: Mapped[str] = mapped_column(String(1024), default="/assets/img/avatar.png", server_default="/assets/img/avatar.png")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    password_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), default="")
    role: Mapped[str] = mapped_column(String(32), default="superadmin", nullable=False)
    status: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AdminOperation(Base, TimestampMixin):
    __tablename__ = "admin_operations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(128))
    path: Mapped[str] = mapped_column(String(255))
    ip: Mapped[str] = mapped_column(String(64), default="")


class Agent(Base, TimestampMixin):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    user_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    avatar: Mapped[str] = mapped_column(String(255), default="")
    password: Mapped[str] = mapped_column(String(255), default="")
    salt: Mapped[str] = mapped_column(String(64), default="")
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    role_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    security_key: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[int] = mapped_column(Integer, default=1)
    game_ad_status: Mapped[int] = mapped_column(Integer, default=0)
    ht_status: Mapped[int] = mapped_column(Integer, default=0)
    is_gx: Mapped[int] = mapped_column(Integer, default=0)
    oss_config: Mapped[str] = mapped_column(Text, default="{}")


class Game(Base, TimestampMixin):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    game_icon: Mapped[str] = mapped_column(String(255), default="")
    game_key: Mapped[str] = mapped_column(String(128), default="")
    game_url: Mapped[str] = mapped_column(String(255), default="")
    game_type: Mapped[int] = mapped_column(Integer, default=0)
    game_ad_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    game_lottery_num: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=1)
    ad_status: Mapped[int] = mapped_column(Integer, default=1)
    lucky_enable: Mapped[int] = mapped_column(Integer, default=1)
    is_landscape: Mapped[int] = mapped_column(Integer, default=0)
    is_game: Mapped[int] = mapped_column(Integer, default=1)
    is_mobile: Mapped[int] = mapped_column(Integer, default=0)
    is_imei: Mapped[int] = mapped_column(Integer, default=0)
    raffle_num: Mapped[int] = mapped_column(Integer, default=500)
    star_countdown: Mapped[float] = mapped_column(Float, default=30.0)
    over_countdown: Mapped[float] = mapped_column(Float, default=50.0)
    star_coin: Mapped[float] = mapped_column(Float, default=0.01)
    over_coin: Mapped[float] = mapped_column(Float, default=0.01)
    coin_get: Mapped[float] = mapped_column(Float, default=1000000.0)
    exchange_num: Mapped[int] = mapped_column(Integer, default=10)
    commission_status: Mapped[int] = mapped_column(Integer, default=0)
    commission_source: Mapped[int] = mapped_column(Integer, default=0)
    commission_rate: Mapped[float] = mapped_column(Float, default=0.0)
    tixian_price: Mapped[str] = mapped_column(String(255), default="")
    tixian_coin: Mapped[str] = mapped_column(String(255), default="")
    tixian_wx: Mapped[int] = mapped_column(Integer, default=0)
    wx_appid: Mapped[str] = mapped_column(String(128), default="")
    wx_secert: Mapped[str] = mapped_column(String(128), default="")
    other_url: Mapped[str] = mapped_column(String(255), default="")
    settings_json: Mapped[str] = mapped_column(Text, default="{}")


class Member(Base, TimestampMixin):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(Integer, default=0)
    game_id: Mapped[int] = mapped_column(Integer, default=0)
    parent_id: Mapped[int] = mapped_column(Integer, default=0)
    is_true: Mapped[int | None] = mapped_column(Integer, nullable=True)
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    ip: Mapped[str] = mapped_column(String(64), default="", server_default="")
    name: Mapped[str] = mapped_column(String(128), default="")
    image_url: Mapped[str] = mapped_column(String(255), default="")
    otherlevel: Mapped[str] = mapped_column(Text, default="")
    device_id: Mapped[str] = mapped_column(String(128), default="")
    sex: Mapped[int] = mapped_column(Integer, default=0)
    real_name: Mapped[str] = mapped_column(String(64), default="")
    realname_enable: Mapped[int | None] = mapped_column(Integer, nullable=True)
    receive_name: Mapped[str] = mapped_column(String(64), default="", server_default="")
    card_no: Mapped[str] = mapped_column(String(64), default="")
    address: Mapped[str] = mapped_column(String(255), default="")
    coin: Mapped[float] = mapped_column(Float, default=0.0)
    freeze_coin: Mapped[float] = mapped_column(Float, default=0.0)
    coin_user: Mapped[float] = mapped_column(Float, default=0.0)
    coin_user_month: Mapped[float] = mapped_column(Float, default=0.0)
    coin_user_day: Mapped[float] = mapped_column(Float, default=0.0)
    vip: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(Integer, default=1)
    exchange_enable: Mapped[int] = mapped_column(Integer, default=1)
    game_addiction_enable: Mapped[int] = mapped_column(Integer, default=0)
    game_addiction_time: Mapped[str] = mapped_column(String(64), default="")
    is_white: Mapped[int] = mapped_column(Integer, default=0)
    ht_status: Mapped[int] = mapped_column(Integer, default=0)
    ht_id: Mapped[int] = mapped_column(Integer, default=0)
    ht_top_id: Mapped[int] = mapped_column(Integer, default=0)
    beishu: Mapped[float] = mapped_column(Float, default=0.0)
    percent_zhi: Mapped[float] = mapped_column(Float, default=0.0)
    percent_jian: Mapped[float] = mapped_column(Float, default=0.0)
    percent_dai: Mapped[float] = mapped_column(Float, default=0.0)
    percent_dai_two: Mapped[float] = mapped_column(Float, default=0.0)
    last_login_ip: Mapped[str] = mapped_column(String(64), default="")
    last_login_time: Mapped[str] = mapped_column(String(64), default="")
    last_login_device_id: Mapped[str] = mapped_column(String(128), default="")
    raffle_open: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raffle_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    star_countdown: Mapped[float | None] = mapped_column(Float, nullable=True)
    over_countdown: Mapped[float | None] = mapped_column(Float, nullable=True)
    down_load: Mapped[str] = mapped_column(String(255), default="")
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    password_salt: Mapped[str] = mapped_column(String(64), default="")
    pay_password_hash: Mapped[str] = mapped_column(String(255), default="")
    pay_password_salt: Mapped[str] = mapped_column(String(64), default="")
    raffle_num2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    star_countdown2: Mapped[float | None] = mapped_column(Float, nullable=True)
    over_countdown2: Mapped[float | None] = mapped_column(Float, nullable=True)


class AdRecord(Base, TimestampMixin):
    __tablename__ = "ad_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(Integer, default=0)
    parent_payment_name: Mapped[str] = mapped_column(String(64), default="")
    user_id: Mapped[int] = mapped_column(Integer, default=0)
    user_account: Mapped[str] = mapped_column(String(128), default="")
    agent_id: Mapped[int] = mapped_column(Integer, default=0)
    game_id: Mapped[int] = mapped_column(Integer, default=0)
    game_name: Mapped[str] = mapped_column(String(128), default="")
    receive_name: Mapped[str] = mapped_column(String(64), default="")
    ecpm: Mapped[float] = mapped_column(Float, default=0.0)
    coin: Mapped[float] = mapped_column(Float, default=0.0)
    estimate_income: Mapped[float] = mapped_column(Float, default=0.0)
    ad_network_platform_name: Mapped[str] = mapped_column(String(64), default="")
    is_lottery: Mapped[int] = mapped_column(Integer, default=0)
    is_rw: Mapped[int] = mapped_column(Integer, default=0)
    reward_type: Mapped[str] = mapped_column(String(32), default="领取")
    ad_type: Mapped[str] = mapped_column(String(32), default="激励")
    sub_ad_type: Mapped[str] = mapped_column(String(32), default="")
    ad_group: Mapped[str] = mapped_column(String(32), default="主广", server_default="主广")
    is_type: Mapped[int] = mapped_column(Integer, default=0)
    is_fu: Mapped[int] = mapped_column(Integer, default=0)
    fu_type: Mapped[int] = mapped_column(Integer, default=1)
    is_look: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="成功")
    watched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ad_code: Mapped[str] = mapped_column(String(128), default="")
    request_id: Mapped[str] = mapped_column(String(128), default="")
    trans_id: Mapped[str] = mapped_column(String(128), default="")


class GameTakuConfig(Base):
    """Server-only settings, deliberately excluded from game settings_json."""
    __tablename__ = "game_taku_configs"
    game_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sec_key: Mapped[str] = mapped_column(String(512), default="", nullable=False)


def taku_credentials(session: Session, game_id: int) -> tuple[bool, str]:
    config = session.get(GameTakuConfig, game_id)
    if config is not None:
        return bool(config.enabled), config.sec_key
    # Preserve existing deployments until a game saves its own callback settings.
    return bool(TAKU_SEC_KEY), TAKU_SEC_KEY


def taku_admin_config(session: Session, game_id: int) -> dict[str, Any]:
    enabled, key = taku_credentials(session, game_id)
    return {"taku_callback_enabled": enabled, "taku_sec_key_configured": bool(key),
            "taku_config_source": "game" if session.get(GameTakuConfig, game_id) else "environment",
            "taku_callback_path": "/api/callbacks/taku/reward"}


class AppRefreshSession(Base, TimestampMixin):
    """Rotating refresh tokens for the user APP.

    Only a hash of the opaque refresh token is persisted.  This keeps a
    leaked database from being enough to impersonate an APP user.
    """

    __tablename__ = "app_refresh_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    device_id: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AppAdSession(Base, TimestampMixin):
    """A server-issued, single-use advertisement session."""

    __tablename__ = "app_ad_sessions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    member_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    agent_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    game_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    device_id: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    client_request_id: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    placement: Mapped[str] = mapped_column(String(64), default="rewarded", nullable=False)
    ad_type: Mapped[str] = mapped_column(String(64), default="rewarded", nullable=False)
    provider: Mapped[str] = mapped_column(String(64), default="internal", nullable=False)
    ad_unit_id: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    reward_coin: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="issued", nullable=False)
    session_token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    impressed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    coin_log_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_json: Mapped[str] = mapped_column(Text, default="", nullable=False)


class AppAdEvent(Base, TimestampMixin):
    """Idempotency record for APP impression/complete/fail events."""

    __tablename__ = "app_ad_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_app_ad_event_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    ad_session_id: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    member_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    result_json: Mapped[str] = mapped_column(Text, default="", nullable=False)


class AdFlowLog(Base, TimestampMixin):
    """Append-only audit trail for one APP rewarded-ad flow."""

    __tablename__ = "ad_flow_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ad_session_id: Mapped[str] = mapped_column(String(80), index=True, default="", nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), index=True, default="", nullable=False)
    member_id: Mapped[int] = mapped_column(Integer, index=True, default=0, nullable=False)
    game_id: Mapped[int] = mapped_column(Integer, index=True, default=0, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    trans_id: Mapped[str] = mapped_column(String(128), index=True, default="", nullable=False)
    error_code: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    detail_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)


def _ad_flow_log(session: Session, item: AppAdSession | None, event_type: str, status: str = "ok",
                 detail: dict[str, Any] | None = None, error_code: str = "", trans_id: str = "") -> None:
    """Write a durable flow checkpoint in the same transaction as its state change."""
    session.add(AdFlowLog(
        ad_session_id=item.id if item else "",
        request_id=item.request_id if item else "",
        member_id=item.member_id if item else 0,
        game_id=item.game_id if item else 0,
        event_type=event_type,
        status=status,
        provider=item.provider if item else "taku",
        trans_id=trans_id,
        error_code=error_code,
        detail_json=json.dumps(detail or {}, ensure_ascii=False, default=str),
    ))


class AdImportBatch(Base, TimestampMixin):
    __tablename__ = "ad_import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String(255), default="")
    operator_id: Mapped[int] = mapped_column(Integer, default=0)
    operator_name: Mapped[str] = mapped_column(String(128), default="")
    total: Mapped[int] = mapped_column(Integer, default=0)
    accepted: Mapped[int] = mapped_column(Integer, default=0)
    rejected: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="完成")


class AdImportError(Base, TimestampMixin):
    __tablename__ = "ad_import_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, default=0)
    request_id: Mapped[str] = mapped_column(String(128), default="")
    message: Mapped[str] = mapped_column(String(255), default="")
    raw_data: Mapped[str] = mapped_column(Text, default="")


class Withdrawal(Base, TimestampMixin):
    __tablename__ = "withdrawals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=0)
    agent_id: Mapped[int] = mapped_column(Integer, default=0)
    game_id: Mapped[int] = mapped_column(Integer, default=0)
    good_name: Mapped[str] = mapped_column(String(255), default="")
    device_manufacturer: Mapped[str] = mapped_column(String(128), default="")
    check_status_txt: Mapped[str] = mapped_column(String(255), default="")
    delivery_name: Mapped[str] = mapped_column(String(128), default="")
    delivery_no: Mapped[str] = mapped_column(String(128), default="")
    remark: Mapped[str] = mapped_column(Text, default="")
    receive_name: Mapped[str] = mapped_column(String(64), default="")
    receive_tel: Mapped[str] = mapped_column(String(64), default="")
    receive_address: Mapped[str] = mapped_column(String(255), default="")
    exchange_value: Mapped[float] = mapped_column(Float, default=0.0)
    exchange_type: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(Integer, default=0)
    plan_status: Mapped[int] = mapped_column(Integer, default=0)
    sub_msg: Mapped[str] = mapped_column(String(255), default="")
    reason: Mapped[str] = mapped_column(String(255), default="")
    audit_operator_id: Mapped[int] = mapped_column(Integer, default=0)
    audit_operator_name: Mapped[str] = mapped_column(String(128), default="")
    audited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    transfer_operator_id: Mapped[int] = mapped_column(Integer, default=0)
    transfer_operator_name: Mapped[str] = mapped_column(String(128), default="")
    transferred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WithdrawalBlacklist(Base, TimestampMixin):
    __tablename__ = 'withdrawal_blacklist'
    __table_args__ = (UniqueConstraint('receive_name', 'receive_tel', name='uq_withdrawal_blacklist_recipient'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    receive_name: Mapped[str] = mapped_column(String(64), nullable=False, default='')
    receive_tel: Mapped[str] = mapped_column(String(64), nullable=False, default='')
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_withdrawal_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Subsidy(Base, TimestampMixin):
    __tablename__ = "subsidies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=0)
    agent_id: Mapped[int] = mapped_column(Integer, default=0)
    game_id: Mapped[int] = mapped_column(Integer, default=0)
    tx_price: Mapped[float] = mapped_column(Float, default=0.0)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    pics: Mapped[str] = mapped_column(Text, default="")
    receive_name: Mapped[str] = mapped_column(String(64), default="")
    receive_tel: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[int] = mapped_column(Integer, default=0)
    sub_msg: Mapped[str] = mapped_column(String(255), default="")
    audit_operator_id: Mapped[int] = mapped_column(Integer, default=0)
    audit_operator_name: Mapped[str] = mapped_column(String(128), default="")
    audited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CoinLog(Base, TimestampMixin):
    __tablename__ = "coin_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=0)
    agent_id: Mapped[int] = mapped_column(Integer, default=0)
    game_id: Mapped[int] = mapped_column(Integer, default=0)
    coin_before: Mapped[float] = mapped_column(Float, default=0.0)
    coin: Mapped[float] = mapped_column(Float, default=0.0)
    coin_after: Mapped[float] = mapped_column(Float, default=0.0)
    type: Mapped[int] = mapped_column(Integer, default=100)
    remark: Mapped[str] = mapped_column(String(255), default="")


class LotteryRecord(Base, TimestampMixin):
    __tablename__ = "lottery_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    game_id: Mapped[int] = mapped_column(Integer, index=True)
    lottery_price: Mapped[float] = mapped_column(Float, default=0.0)
    ecpm: Mapped[float] = mapped_column(Float, default=0.0)
    adn_name: Mapped[str] = mapped_column(String(128), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    network_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tag: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ad_network_rit_id: Mapped[str] = mapped_column(String(128), default="")
    request_id: Mapped[str] = mapped_column(String(128), default="")
    trans_id: Mapped[str] = mapped_column(String(128), default="")


class DailyActivity(Base):
    __tablename__ = "daily_activity"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(Integer, index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    num: Mapped[int] = mapped_column(Integer, default=0)


class MemberLoginLog(Base, TimestampMixin):
    __tablename__ = "member_login_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    game_id: Mapped[int] = mapped_column(Integer, index=True)
    device_id: Mapped[str] = mapped_column(String(128), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")


class MemberDevice(Base, TimestampMixin):
    __tablename__ = "member_devices"
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[str] = mapped_column(String(128), default="")
    imei: Mapped[str] = mapped_column(String(128), default="")
    android_version: Mapped[str] = mapped_column(String(64), default="")
    model: Mapped[str] = mapped_column(String(128), default="")
    app_version: Mapped[str] = mapped_column(String(64), default="")
    ip_address: Mapped[str] = mapped_column(String(255), default="")
    sim_info: Mapped[str] = mapped_column(String(255), default="")
    risk_flag: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usb_debugging: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rooted: Mapped[int | None] = mapped_column(Integer, nullable=True)
    device_id_ban: Mapped[int] = mapped_column(Integer, default=0)
    imei_id_ban: Mapped[int] = mapped_column(Integer, default=0)
    total_clicks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    today_clicks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    today_failed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    counter_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class WechatIdentity(Base, TimestampMixin):
    __tablename__ = "wechat_identities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), default="mini_program", nullable=False)
    app_id: Mapped[str] = mapped_column(String(128), nullable=False)
    openid: Mapped[str] = mapped_column(String(128), nullable=False)
    unionid: Mapped[str] = mapped_column(String(128), default="")
    nickname: Mapped[str] = mapped_column(String(128), default="")
    avatar_url: Mapped[str] = mapped_column(String(512), default="")
    __table_args__ = (UniqueConstraint("provider", "app_id", "openid", name="uq_wechat_identity_provider_app_openid"),)


class AgentAnalysisConfig(Base, TimestampMixin):
    __tablename__ = "agent_analysis_config"
    agent_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    buckets: Mapped[str] = mapped_column(Text, nullable=False, default="{}", server_default="{}")


class MemberAppUsage(Base, TimestampMixin):
    __tablename__ = "member_app_usage"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    game_id: Mapped[int] = mapped_column(Integer, index=True)
    app_name: Mapped[str] = mapped_column(String(255), default="")
    package_name: Mapped[str] = mapped_column(String(255), default="")
    count: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    first_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RiskRecord(Base, TimestampMixin):
    __tablename__ = "risk_records"
    network_status: Mapped[int | None] = mapped_column(Integer, nullable=True)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=0)
    agent_id: Mapped[int] = mapped_column(Integer, default=0)
    game_id: Mapped[int] = mapped_column(Integer, default=0)
    tagcode: Mapped[str] = mapped_column(String(64), default="")
    tags: Mapped[str] = mapped_column(String(255), default="")
    hardware_main_id: Mapped[str] = mapped_column(String(128), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    action: Mapped[str] = mapped_column(String(128), default="")
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    risk_level: Mapped[str] = mapped_column(String(32), default="")


class KuaishouRiskAssessment(Base, TimestampMixin):
    """Manual, versioned Kwai risk assessment snapshots.

    This is an operator advisory record. It is intentionally separate from
    RiskRecord because it is based on manually entered aggregate metrics and
    must never be used as a user-level reward or ban decision by itself.
    """

    __tablename__ = "kuaishou_risk_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    agent_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    game_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    pay_rate: Mapped[float] = mapped_column(Float, nullable=False)
    retain_1: Mapped[float] = mapped_column(Float, nullable=False)
    ctr: Mapped[float] = mapped_column(Float, nullable=False)
    flow_growth: Mapped[float] = mapped_column(Float, nullable=False)
    device_repeat: Mapped[float] = mapped_column(Float, nullable=False)
    pay_score: Mapped[float] = mapped_column(Float, nullable=False)
    retain_score: Mapped[float] = mapped_column(Float, nullable=False)
    ctr_score: Mapped[float] = mapped_column(Float, nullable=False)
    flow_score: Mapped[float] = mapped_column(Float, nullable=False)
    device_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    suggestion: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1-revised")
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    operator_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    operator_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")


def stringify(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return value


def serialize(model: Any, fields: list[str]) -> dict[str, Any]:
    return {field: stringify(getattr(model, field)) for field in fields}


AGENT_FIELDS = [
    "id",
    "parent_id",
    "name",
    "user_name",
    "status",
    "game_ad_status",
    "ht_status",
    "is_gx",
    "created_at",
    "updated_at",
]

AGENT_EDITOR_FIELDS = [
    "id",
    "parent_id",
    "name",
    "user_name",
    "avatar",
    "user_id",
    "role_id",
    "security_key",
    "status",
    "game_ad_status",
    "ht_status",
    "is_gx",
    "created_at",
    "updated_at",
]

GAME_FIELDS = [
    "id",
    "agent_id",
    "name",
    "game_icon",
    "game_key",
    "game_url",
    "status",
    "ad_status",
    "lucky_enable",
    "is_landscape",
    "is_game",
    "is_mobile",
    "is_imei",
    "raffle_num",
    "star_countdown",
    "over_countdown",
    "star_coin",
    "over_coin",
    "coin_get",
    "exchange_num",
    "commission_status",
    "commission_source",
    "commission_rate",
    "tixian_price",
    "tixian_coin",
    "tixian_wx",
    "wx_appid",
    "wx_secert",
    "other_url",
    "settings_json",
    "created_at",
    "updated_at",
]

GAME_EDITOR_FIELDS = [
    "id",
    "agent_id",
    "name",
    "game_icon",
    "game_key",
    "game_url",
    "game_type",
    "game_ad_status",
    "game_lottery_num",
    "status",
    "ad_status",
    "lucky_enable",
    "is_landscape",
    "is_game",
    "is_mobile",
    "is_imei",
    "raffle_num",
    "star_countdown",
    "over_countdown",
    "star_coin",
    "over_coin",
    "coin_get",
    "exchange_num",
    "commission_status",
    "commission_source",
    "commission_rate",
    "tixian_price",
    "tixian_coin",
    "tixian_wx",
    "wx_appid",
    "wx_secert",
    "other_url",
    "settings_json",
    "created_at",
    "updated_at",
]

GAME_AD_EDITOR_FIELDS = [
    "ad_provider",
    "ad_app_id",
    "ad_app_key",
    "ad_rewarded_unit_id",
    "ad_interstitial_unit_id",
    "ad_banner_unit_id",
    "ad_splash_unit_id",
    "ad_native_unit_id",
    "ad_reward_coin",
    "ad_cooldown_seconds",
    "ad_config_enabled",
]

MEMBER_FIELDS = [
    "raffle_open", "raffle_num", "star_countdown", "over_countdown", "down_load", "raffle_num2", "star_countdown2", "over_countdown2",
    "realname_enable",
    "is_true",
    "sex",
    "receive_name",
    "ip",
    "id",
    "agent_id",
    "game_id",
    "parent_id",
    "username",
    "name",
    "image_url",
    "otherlevel",
    "device_id",
    "real_name",
    "card_no",
    "address",
    "coin",
    "freeze_coin",
    "coin_user",
    "coin_user_month",
    "coin_user_day",
    "vip",
    "status",
    "exchange_enable",
    "game_addiction_enable",
    "game_addiction_time",
    "is_white",
    "ht_status",
    "ht_id",
    "ht_top_id",
    "beishu",
    "percent_zhi",
    "percent_jian",
    "percent_dai",
    "percent_dai_two",
    "last_login_ip",
    "last_login_time",
    "last_login_device_id",
    "created_at",
    "updated_at",
]

AD_FIELDS = [
    "id",
    "parent_id",
    "parent_payment_name",
    "user_id",
    "user_account",
    "receive_name",
    "game_name",
    "ecpm",
    "coin",
    "agent_id",
    "game_id",
    "estimate_income",
    "ad_network_platform_name",
    "is_lottery",
    "is_rw",
    "reward_type",
    "ad_type",
    "sub_ad_type",
    "ad_group",
    "is_type",
    "is_fu",
    "fu_type",
    "is_look",
    "status",
    "watched_at",
    "ad_code",
    "request_id",
    "trans_id",
    "created_at",
]

MAIN_AD_LABEL = '主广'
SECONDARY_AD_LABEL = '副广'
SECONDARY_AD_TYPES = ("插屏", "激励视频", "开屏广告", "信息流")
AD_SEARCH_FIELDS = [
    "parent_payment_name",
    "user_account",
    "receive_name",
    "game_name",
    "ad_network_platform_name",
    "ad_code",
    "request_id",
    "trans_id",
]
AD_EXPORT_COLUMNS = [('ID', 'id'), ('上级ID', 'parent_id'), ('上级支付宝姓名', 'parent_payment_name'), ('会员ID', 'user_id'), ('用户账号', 'user_account'), ('支付宝姓名', 'receive_name'), ('游戏名称', 'game_name'), ('ECPM', 'ecpm'), ('金币', 'estimate_income'), ('广告平台', 'ad_network_platform_name'), ('奖励类型', 'reward_type'), ('广告分组', 'ad_group'), ('状态', 'status'), ('观看时间', 'watched_at'), ('广告代码位', 'ad_code'), ('广告request_id', 'request_id'), ('交易trans_id', 'trans_id')]
AD_STATS_GROUP_LABELS = {'day': '日期', 'ad_group': '广告分组', 'game': '游戏', 'agent': '代理商'}
from .recovered_constants import (COINLOG_FIELDS, RISK_FIELDS, SUBSIDY_FIELDS, WITHDRAWAL_FIELDS, AD_IMPORT_FIELD_ALIASES, AD_IMPORT_NUMERIC_FIELDS, AD_IMPORT_STRING_FIELDS, AD_IMPORT_BATCH_FIELDS, AD_IMPORT_ERROR_FIELDS, AD_ALERT_TYPE_LABELS, AD_ALERT_SEVERITY_LABELS, AD_ALERT_SEVERITY_ORDER)

def filter_stmt(model: Any, q: str | None, fields: list[str]):
    stmt = select(model)
    if q:
        stmt = stmt.where(or_(*[getattr(model, field).ilike(f"%{q}%") for field in fields]))
    return stmt


def apply_search_like(stmt: Any, model: Any, q: str | None, fields: list[str]) -> Any:
    if q:
        stmt = stmt.where(or_(*[getattr(model, field).ilike(f"%{q}%") for field in fields]))
    return stmt


def list_payload(
    session: Session,
    model: Any,
    fields: list[str],
    serializer: Callable[[Any], dict[str, Any]],
    q: str | None,
    limit: int,
    offset: int,
    conditions: list[Any] | None = None,
    ordering: list[Any] | None = None,
):
    stmt = filter_stmt(model, q, fields)
    if conditions:
        stmt = stmt.where(*conditions)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = session.scalar(count_stmt) or 0
    rows = session.execute(stmt.order_by(*(ordering or [model.id.desc()])).offset(offset).limit(limit)).scalars().all()
    return {"total": total, "items": [serializer(row) for row in rows], "limit": limit, "offset": offset}


def summarize_flags(
    session: Session,
    model: Any,
    conditions: list[Any],
    metrics: list[tuple[str, Any]],
) -> dict[str, Any]:
    if not metrics:
        return {}
    stmt = select(
        *[
            func.coalesce(func.sum(case((expression, 1), else_=0)), 0).label(name)
            for name, expression in metrics
        ]
    ).select_from(model)
    if conditions:
        stmt = stmt.where(*conditions)
    row = session.execute(stmt).one()
    return {name: int(getattr(row, name) or 0) for name, _expression in metrics}


def serialize_agent(item: Agent) -> dict[str, Any]:
    return serialize(item, AGENT_FIELDS)


def serialize_game(item: Game) -> dict[str, Any]:
    return serialize(item, GAME_FIELDS + ["game_ad_status", "game_lottery_num"])


def game_settings(item: Game) -> dict[str, Any]:
    try:
        value = json.loads(item.settings_json or "{}")
    except (TypeError, json.JSONDecodeError):
        value = {}
    return value if isinstance(value, dict) else {}


def game_ad_config(item: Game) -> dict[str, Any]:
    settings = game_settings(item)
    configured = settings.get("ad_config")
    configured = configured if isinstance(configured, dict) else {}
    placements = configured.get("placements")
    placements = placements if isinstance(placements, dict) else {}

    def placement(name: str, fallback_coin: float = 0.0) -> dict[str, Any]:
        value = placements.get(name)
        value = value if isinstance(value, dict) else {}
        return {
            "unit_id": str(value.get("unit_id") or ""),
            "reward_coin": max(float(value.get("reward_coin", fallback_coin) or 0), 0),
            "cooldown_seconds": max(int(value.get("cooldown_seconds", configured.get("cooldown_seconds", 0)) or 0), 0),
        }

    rewarded = placement("rewarded", float(item.star_coin or 0.01))
    interstitial = placement("interstitial")
    banner = placement("banner")
    splash = placement("splash")
    native = placement("native")
    return {
        "enabled": bool(configured.get("enabled", item.ad_status == 1)),
        "provider": str(configured.get("provider") or "internal"),
        "app_id": str(configured.get("app_id") or ""),
        "app_key": str(configured.get("app_key") or ""),
        "placements": {
            "rewarded": rewarded,
            "interstitial": interstitial,
            "banner": banner,
            "splash": splash,
            "native": native,
        },
    }


def serialize_game_editor(item: Game) -> dict[str, Any]:
    payload = serialize(item, GAME_EDITOR_FIELDS)
    config = game_ad_config(item)
    payload.update({
        "ad_provider": config["provider"],
        "ad_app_id": config["app_id"],
        "ad_app_key": config["app_key"],
        "ad_rewarded_unit_id": config["placements"]["rewarded"]["unit_id"],
        "ad_interstitial_unit_id": config["placements"]["interstitial"]["unit_id"],
        "ad_banner_unit_id": config["placements"]["banner"]["unit_id"],
        "ad_splash_unit_id": config["placements"]["splash"]["unit_id"],
        "ad_native_unit_id": config["placements"]["native"]["unit_id"],
        "ad_reward_coin": config["placements"]["rewarded"]["reward_coin"],
        "ad_cooldown_seconds": config["placements"]["rewarded"]["cooldown_seconds"],
        "ad_config_enabled": 1 if config["enabled"] else 0,
    })
    return payload


def merge_game_ad_config(changes: dict[str, Any], existing_settings: str | None = None) -> None:
    keys = set(GAME_AD_EDITOR_FIELDS)
    ad_changes = {key: changes.pop(key) for key in list(changes) if key in keys}
    if not ad_changes:
        return
    raw = changes.get("settings_json", existing_settings or "{}")
    try:
        settings = json.loads(raw or "{}")
    except (TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="settings_json must be a JSON object") from exc
    if not isinstance(settings, dict):
        raise HTTPException(status_code=422, detail="settings_json must be a JSON object")
    current = settings.get("ad_config")
    current = dict(current) if isinstance(current, dict) else {}
    placements = current.get("placements")
    placements = {name: dict(value) for name, value in placements.items() if isinstance(value, dict)} if isinstance(placements, dict) else {}
    if "ad_provider" in ad_changes: current["provider"] = str(ad_changes["ad_provider"] or "internal").strip()
    if "ad_app_id" in ad_changes: current["app_id"] = str(ad_changes["ad_app_id"] or "").strip()
    if "ad_app_key" in ad_changes: current["app_key"] = str(ad_changes["ad_app_key"] or "").strip()
    if "ad_config_enabled" in ad_changes: current["enabled"] = bool(ad_changes["ad_config_enabled"])
    rewarded = placements.setdefault("rewarded", {})
    if "ad_rewarded_unit_id" in ad_changes: rewarded["unit_id"] = str(ad_changes["ad_rewarded_unit_id"] or "").strip()
    if "ad_reward_coin" in ad_changes: rewarded["reward_coin"] = float(ad_changes["ad_reward_coin"] or 0)
    if "ad_cooldown_seconds" in ad_changes: rewarded["cooldown_seconds"] = int(ad_changes["ad_cooldown_seconds"] or 0)
    for field, placement_name in (("ad_interstitial_unit_id", "interstitial"), ("ad_banner_unit_id", "banner"), ("ad_splash_unit_id", "splash"), ("ad_native_unit_id", "native")):
        if field in ad_changes:
            placements.setdefault(placement_name, {})["unit_id"] = str(ad_changes[field] or "").strip()
    current["placements"] = placements
    settings["ad_config"] = current
    changes["settings_json"] = json.dumps(settings, ensure_ascii=False, separators=(",", ":"))


def serialize_member(item: Member) -> dict[str, Any]:
    return serialize(item, MEMBER_FIELDS)


def secondary_ad_condition() -> Any:
    legacy_secondary = legacy_secondary_ad_condition()
    missing_group = or_(AdRecord.ad_group.is_(None), AdRecord.ad_group == "")
    return or_(
        AdRecord.ad_group == SECONDARY_AD_LABEL,
        and_(missing_group, legacy_secondary),
    )


def main_ad_condition() -> Any:
    missing_group = or_(AdRecord.ad_group.is_(None), AdRecord.ad_group == "")
    return or_(
        AdRecord.ad_group == MAIN_AD_LABEL,
        and_(missing_group, ~legacy_secondary_ad_condition()),
    )


def build_ad_conditions(
    parent_id: int | None = None,
    member_id: int | None = None,
    game_name: str | None = None,
    agent_name: str | None = None,
    game_id: int | None = None,
    agent_id: int | None = None,
    coin_min: float | None = None,
    coin_max: float | None = None,
    estimate_income_min: float | None = None,
    estimate_income_max: float | None = None,
    ad_platform: str | None = None,
    ad_type_filter: str | None = None,
    sub_ad_type_filter: str | None = None,
    is_fu_filter: int | None = None,
    fu_type_filter: int | None = None,
    is_look_filter: int | None = None,
    ad_group_filter: str | None = None,
    status_filter: str | None = None,
    watched_from: datetime | None = None,
    watched_to: datetime | None = None,
) -> list[Any]:
    conditions: list[Any] = []
    if parent_id is not None:
        conditions.append(AdRecord.parent_id == parent_id)
    if member_id is not None:
        conditions.append(AdRecord.user_id == member_id)
    if game_name:
        conditions.append(AdRecord.game_id.in_(select(Game.id).where(Game.name == game_name)))
    if agent_name:
        conditions.append(AdRecord.agent_id.in_(select(Agent.id).where(Agent.name.contains(agent_name, autoescape=True))))
    if game_id is not None:
        conditions.append(AdRecord.game_id == game_id)
    if agent_id is not None:
        conditions.append(AdRecord.agent_id == agent_id)
    if coin_min is not None:
        conditions.append(AdRecord.coin >= coin_min)
    if coin_max is not None:
        conditions.append(AdRecord.coin <= coin_max)
    if estimate_income_min is not None:
        conditions.append(AdRecord.estimate_income >= estimate_income_min)
    if estimate_income_max is not None:
        conditions.append(AdRecord.estimate_income <= estimate_income_max)
    if ad_platform:
        conditions.append(AdRecord.ad_network_platform_name == ad_platform)
    if ad_type_filter:
        conditions.append(AdRecord.ad_type == ad_type_filter)
    if sub_ad_type_filter:
        conditions.append(AdRecord.sub_ad_type == sub_ad_type_filter)
    if is_fu_filter is not None:
        conditions.append(AdRecord.is_fu == is_fu_filter)
    if fu_type_filter is not None:
        conditions.append(AdRecord.fu_type == fu_type_filter)
    if is_look_filter is not None:
        conditions.append(AdRecord.is_look == is_look_filter)
    if ad_group_filter == SECONDARY_AD_LABEL:
        conditions.append(secondary_ad_condition())
    elif ad_group_filter == MAIN_AD_LABEL:
        conditions.append(main_ad_condition())
    if status_filter:
        conditions.append(AdRecord.status == status_filter)
    if watched_from is not None:
        conditions.append(AdRecord.watched_at >= watched_from)
    if watched_to is not None:
        conditions.append(AdRecord.watched_at <= watched_to)
    return conditions


def legacy_secondary_ad_condition() -> Any:
    return or_(
        AdRecord.is_fu == 1,
        AdRecord.ad_type == SECONDARY_AD_LABEL,
        AdRecord.sub_ad_type == SECONDARY_AD_LABEL,
        *[AdRecord.ad_type.ilike(f"%{keyword}%") for keyword in SECONDARY_AD_TYPES],
        *[AdRecord.sub_ad_type.ilike(f"%{keyword}%") for keyword in SECONDARY_AD_TYPES],
    )


def classify_ad_group(item: AdRecord) -> str:
    ad_group = (item.ad_group or "").strip()
    if ad_group in (MAIN_AD_LABEL, SECONDARY_AD_LABEL):
        return ad_group
    if item.is_fu == 1:
        return SECONDARY_AD_LABEL
    ad_type = (item.ad_type or "").strip()
    sub_ad_type = (item.sub_ad_type or "").strip()
    if ad_type == SECONDARY_AD_LABEL or sub_ad_type == SECONDARY_AD_LABEL:
        return SECONDARY_AD_LABEL
    if ad_type == MAIN_AD_LABEL or sub_ad_type == MAIN_AD_LABEL:
        return MAIN_AD_LABEL
    if any(keyword in ad_type or keyword in sub_ad_type for keyword in SECONDARY_AD_TYPES):
        return SECONDARY_AD_LABEL
    return MAIN_AD_LABEL


def ad_group_sql_expression() -> Any:
    return case(
        (AdRecord.ad_group == SECONDARY_AD_LABEL, SECONDARY_AD_LABEL),
        (AdRecord.ad_group == MAIN_AD_LABEL, MAIN_AD_LABEL),
        (legacy_secondary_ad_condition(), SECONDARY_AD_LABEL),
        else_=MAIN_AD_LABEL,
    )


def expected_ad_group_sql_expression() -> Any:
    return case(
        (legacy_secondary_ad_condition(), SECONDARY_AD_LABEL),
        else_=MAIN_AD_LABEL,
    )


def serialize_ad(item: AdRecord) -> dict[str, Any]:
    payload = serialize(item, AD_FIELDS)
    payload["ad_group"] = classify_ad_group(item)
    payload["pre_ecpm"] = payload.get("ecpm", 0.0)
    payload["ad_network_rit_id"] = payload.get("ad_code", "")
    watched_at = item.watched_at or item.created_at
    payload["create_time"] = int(watched_at.timestamp()) if watched_at else 0
    return payload


def export_ads_csv(rows: list[AdRecord]) -> Response:
    buffer = StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow([label for label, _field in AD_EXPORT_COLUMNS])
    for row in rows:
        payload = serialize_ad(row)
        writer.writerow([payload.get(field, "") for _label, field in AD_EXPORT_COLUMNS])
    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="ads-export.csv"'},
    )


def apply_ad_filters(stmt: Any, q: str | None, conditions: list[Any]) -> Any:
    if q:
        stmt = stmt.where(or_(*[getattr(AdRecord, field).ilike(f"%{q}%") for field in AD_SEARCH_FIELDS]))
    if conditions:
        stmt = stmt.where(*conditions)
    return stmt


def ad_stats_label(group_by: str, key: Any, label: Any = None) -> str:
    if group_by == "day":
        return str(stringify(key) or "??")
    if group_by == "ad_group":
        return str(key or MAIN_AD_LABEL)
    if group_by == "game":
        return str(label or (f"?? {key}" if key else "????"))
    if group_by == "agent":
        return str(label or (f"??? {key}" if key else "?????"))
    return str(label or key or "-")


def serialize_ad_stats_row(row: Any, group_by: str) -> dict[str, Any]:
    return {
        "dimension": group_by,
        "dimension_label": ad_stats_label(group_by, row.dimension_key, getattr(row, "dimension_label", None)),
        "dimension_key": stringify(row.dimension_key),
        "count": int(row.ad_count or 0),
        "member_count": int(row.member_count or 0),
        "ecpm": round(float(row.ecpm or 0.0), 4),
        "avg_ecpm": round(float(row.avg_ecpm or 0.0), 4),
        "coin": round(float(row.coin or 0.0), 2),
        "estimate_income": round(float(row.estimate_income or 0.0), 4),
    }


def ad_stats_summary(row: Any) -> dict[str, Any]:
    return {
        "count": int(row.ad_count or 0),
        "member_count": int(row.member_count or 0),
        "ecpm": round(float(row.ecpm or 0.0), 4),
        "avg_ecpm": round(float(row.avg_ecpm or 0.0), 4),
        "coin": round(float(row.coin or 0.0), 2),
        "estimate_income": round(float(row.estimate_income or 0.0), 4),
    }


def ad_stats_columns() -> list[Any]:
    return [
        func.count(AdRecord.id).label("ad_count"),
        func.count(func.distinct(AdRecord.user_id)).label("member_count"),
        func.coalesce(func.sum(AdRecord.ecpm), 0.0).label("ecpm"),
        func.coalesce(func.avg(AdRecord.ecpm), 0.0).label("avg_ecpm"),
        func.coalesce(func.sum(AdRecord.coin), 0.0).label("coin"),
        func.coalesce(func.sum(AdRecord.estimate_income), 0.0).label("estimate_income"),
    ]


def decode_ad_import_body(body: bytes) -> str:
    if not body.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="导入文件不能为空")
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="导入文件编码必须是 UTF-8 或 GB18030（兼容 GBK）")


def parse_ad_import_rows(body: bytes) -> list[dict[str, Any]]:
    content = decode_ad_import_body(body)
    try:
        reader = csv.DictReader(StringIO(content), skipinitialspace=True, strict=True)
        if not reader.fieldnames:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="导入文件缺少表头")
        return list(reader)
    except csv.Error as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="CSV 格式错误") from exc


def parse_ad_import_int(value: str) -> int:
    normalized = value.strip().lower()
    if normalized in {"1", "yes", "true", "on"}:
        return 1
    if normalized in {"0", "no", "false", "off"}:
        return 0
    try:
        number = Decimal(normalized.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError("必须是整数") from exc
    # Avoid float rounding and reject values that cannot fit the database column.
    bits = 64 if engine.dialect.name == "sqlite" else 32
    if not number.is_finite() or number != number.to_integral_value() or not -(2 ** (bits - 1)) <= number < 2 ** (bits - 1):
        raise ValueError("整数无效或超出数据库范围")
    return int(number)


def parse_ad_import_float(value: str) -> float:
    number = float(value.strip().replace(",", ""))
    if not math.isfinite(number):
        raise ValueError("必须是有限数字")
    return number


def parse_ad_import_datetime(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                parsed = datetime.strptime(normalized, fmt)
                break
            except ValueError:
                parsed = None
        if parsed is None:
            raise
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def classify_ad_group_payload(payload: dict[str, Any]) -> str:
    ad_group = str(payload.get("ad_group") or "").strip()
    if ad_group in (MAIN_AD_LABEL, SECONDARY_AD_LABEL):
        return ad_group
    if int(payload.get("is_fu") or 0) == 1:
        return SECONDARY_AD_LABEL
    ad_type = str(payload.get("ad_type") or "").strip()
    sub_ad_type = str(payload.get("sub_ad_type") or "").strip()
    if ad_type == SECONDARY_AD_LABEL or sub_ad_type == SECONDARY_AD_LABEL:
        return SECONDARY_AD_LABEL
    if ad_type == MAIN_AD_LABEL or sub_ad_type == MAIN_AD_LABEL:
        return MAIN_AD_LABEL
    if any(keyword in ad_type or keyword in sub_ad_type for keyword in SECONDARY_AD_TYPES):
        return SECONDARY_AD_LABEL
    return MAIN_AD_LABEL


def normalize_ad_import_row(raw_row: dict[str, Any], row_number: int, seen_request_ids: set[str]) -> tuple[dict[str, Any] | None, list[str]]:
    payload: dict[str, Any] = {}
    errors: list[str] = []

    for raw_key, raw_value in raw_row.items():
        if raw_key is None:
            continue
        key = raw_key.strip().lstrip("\ufeff")
        field = AD_IMPORT_FIELD_ALIASES.get(key)
        if field is None or field == "id":
            continue
        value = str(raw_value or "").strip()
        if value == "":
            continue
        if field in AD_IMPORT_STRING_FIELDS:
            payload[field] = value
        elif field in AD_IMPORT_NUMERIC_FIELDS:
            try:
                parser = parse_ad_import_float if AD_IMPORT_NUMERIC_FIELDS[field] is float else parse_ad_import_int
                payload[field] = parser(value)
            except ValueError:
                errors.append(f"{key} 不是有效数字")
        elif field == "watched_at":
            try:
                payload[field] = parse_ad_import_datetime(value)
            except ValueError:
                errors.append("观看时间格式错误")

    request_id = str(payload.get("request_id") or "").strip()
    if not request_id:
        errors.append("request_id 不能为空")
    elif request_id in seen_request_ids:
        errors.append("request_id在导入文件中重复")
    else:
        seen_request_ids.add(request_id)

    ad_group = str(payload.get("ad_group") or "").strip()
    if ad_group and ad_group not in (MAIN_AD_LABEL, SECONDARY_AD_LABEL):
        errors.append("广告分组必须是主广或副广")

    if errors:
        return None, errors

    payload["ad_group"] = classify_ad_group_payload(payload)
    payload.setdefault("is_fu", 1 if payload["ad_group"] == SECONDARY_AD_LABEL else 0)
    payload.setdefault("fu_type", 1)
    payload.setdefault("is_look", 1)
    payload.setdefault("status", "成功")
    payload.setdefault("reward_type", "领取")
    payload.setdefault("ad_type", "激励" if payload["ad_group"] == MAIN_AD_LABEL else SECONDARY_AD_LABEL)
    return payload, []


def ad_import_error(row_number: int, errors: list[str]) -> dict[str, Any]:
    return {"row": row_number, "errors": errors}


def serialize_ad_import_batch(item: AdImportBatch) -> dict[str, Any]:
    return serialize(item, AD_IMPORT_BATCH_FIELDS)


def serialize_ad_import_error(item: AdImportError) -> dict[str, Any]:
    return serialize(item, AD_IMPORT_ERROR_FIELDS)


def serialize_ad_alert_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: stringify(value) for key, value in item.items()}


def ad_alert_title(alert_type: str) -> str:
    return AD_ALERT_TYPE_LABELS.get(alert_type, alert_type)


def ad_alert_severity_label(severity: str) -> str:
    return AD_ALERT_SEVERITY_LABELS.get(severity, severity)


def make_ad_alert(
    *,
    alert_type: str,
    severity: str,
    summary: str,
    source_type: str,
    source_id: int,
    created_at: datetime | None,
    request_id: str = "",
    row_number: int | None = None,
    file_name: str = "",
    operator_name: str = "",
    ad_group: str = "",
    coin: float | None = None,
    ecpm: float | None = None,
    occurrence_count: int = 1,
    source_label: str = "",
) -> dict[str, Any]:
    if source_label:
        source_label_value = source_label
    elif source_type == "import_batch":
        source_label_value = f"鐎电厧鍙嗛幍瑙勵偧 #{source_id}"
    else:
        source_label_value = f"楠炲灝鎲＄拋鏉跨秿 #{source_id}"
    if alert_type == "duplicate_request_id":
        alert_key = f"{alert_type}:{request_id}"
    elif source_type == "import_batch":
        alert_key = f"{alert_type}:{source_id}:{row_number or 0}"
    else:
        alert_key = f"{alert_type}:{source_id}"
    return {
        "id": alert_key,
        "alert_key": alert_key,
        "alert_type": alert_type,
        "alert_type_label": ad_alert_title(alert_type),
        "severity": severity,
        "severity_label": ad_alert_severity_label(severity),
        "title": ad_alert_title(alert_type),
        "summary": summary,
        "source_type": source_type,
        "source_id": source_id,
        "source_label": source_label_value,
        "request_id": request_id,
        "row_number": row_number,
        "file_name": file_name,
        "operator_name": operator_name,
        "ad_group": ad_group,
        "coin": coin if coin is not None else 0.0,
        "ecpm": ecpm if ecpm is not None else 0.0,
        "occurrence_count": occurrence_count,
        "created_at": created_at,
    }


def build_ad_alert_conditions(
    ad_group_filter: str | None = None,
    watched_from: datetime | None = None,
    watched_to: datetime | None = None,
) -> list[Any]:
    conditions: list[Any] = []
    if ad_group_filter == SECONDARY_AD_LABEL:
        conditions.append(secondary_ad_condition())
    elif ad_group_filter == MAIN_AD_LABEL:
        conditions.append(main_ad_condition())
    if watched_from is not None:
        conditions.append(AdRecord.watched_at >= watched_from)
    if watched_to is not None:
        conditions.append(AdRecord.watched_at <= watched_to)
    return conditions


def alert_matches_filters(
    alert: dict[str, Any],
    *,
    alert_type_filter: str | None = None,
    severity_filter: str | None = None,
    source_type_filter: str | None = None,
    ad_group_filter: str | None = None,
    watched_from: datetime | None = None,
    watched_to: datetime | None = None,
) -> bool:
    if alert_type_filter and alert["alert_type"] != alert_type_filter:
        return False
    if severity_filter and alert["severity"] != severity_filter:
        return False
    if source_type_filter and alert["source_type"] != source_type_filter:
        return False
    if ad_group_filter and alert.get("ad_group") != ad_group_filter:
        return False
    created_at = alert.get("created_at")
    if watched_from is not None and isinstance(created_at, datetime) and created_at < watched_from:
        return False
    if watched_to is not None and isinstance(created_at, datetime) and created_at > watched_to:
        return False
    return True


def alert_sort_key(item: dict[str, Any]) -> tuple[int, datetime, str]:
    created_at = item.get("created_at")
    if not isinstance(created_at, datetime):
        created_at = datetime(1970, 1, 1, tzinfo=UTC)
    return (AD_ALERT_SEVERITY_ORDER.get(str(item.get("severity") or ""), 0), created_at, str(item.get("alert_key") or ""))


def build_ad_alerts(
    session: Session,
    q: str | None = None,
    ad_group_filter: str | None = None,
    watched_from: datetime | None = None,
    watched_to: datetime | None = None,
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    record_conditions = build_ad_alert_conditions(ad_group_filter=ad_group_filter, watched_from=watched_from, watched_to=watched_to)
    success_conditions = [*record_conditions, AdRecord.status == "成功"]
    text_conditions = [*record_conditions]

    duplicate_stmt = select(
        AdRecord.request_id.label("request_id"),
        func.count(AdRecord.id).label("occurrence_count"),
        func.max(AdRecord.id).label("source_id"),
        func.max(AdRecord.created_at).label("created_at"),
        func.max(AdRecord.ad_group).label("ad_group"),
        func.max(AdRecord.coin).label("coin"),
        func.max(AdRecord.ecpm).label("ecpm"),
        func.max(AdRecord.game_name).label("game_name"),
        func.max(AdRecord.user_account).label("user_account"),
        func.max(AdRecord.ad_network_platform_name).label("ad_network_platform_name"),
    ).select_from(AdRecord)
    duplicate_stmt = apply_search_like(duplicate_stmt, AdRecord, q, AD_SEARCH_FIELDS)
    if text_conditions:
        duplicate_stmt = duplicate_stmt.where(*text_conditions)
    duplicate_stmt = duplicate_stmt.where(AdRecord.request_id.is_not(None), AdRecord.request_id != "")
    duplicate_stmt = duplicate_stmt.group_by(AdRecord.request_id).having(func.count(AdRecord.id) > 1)
    for row in session.execute(duplicate_stmt).all():
        alerts.append(
            make_ad_alert(
                alert_type="duplicate_request_id",
                severity="high",
                source_type="ad_record",
                summary=f"request_id {row.request_id} 出现 {row.occurrence_count} 次",
                source_id=int(row.source_id or 0),
                created_at=row.created_at,
                request_id=str(row.request_id or ""),
                ad_group=str(row.ad_group or ""),
                coin=float(row.coin or 0.0),
                ecpm=float(row.ecpm or 0.0),
                occurrence_count=int(row.occurrence_count or 0),
            )
        )

    missing_stmt = apply_search_like(select(AdRecord), AdRecord, q, AD_SEARCH_FIELDS)
    if text_conditions:
        missing_stmt = missing_stmt.where(*text_conditions)
    missing_stmt = missing_stmt.where(or_(AdRecord.request_id.is_(None), AdRecord.request_id == ""))
    for row in session.execute(missing_stmt.order_by(AdRecord.id.desc()).limit(120)).scalars().all():
        alerts.append(
            make_ad_alert(
                alert_type="missing_request_id",
                severity="high",
                summary="楠炲灝鎲＄拋鏉跨秿缂傚搫鐨?request_id",
                source_type="ad_record",
                source_id=row.id,
                created_at=row.created_at,
                ad_group=classify_ad_group(row),
                coin=float(row.coin or 0.0),
                ecpm=float(row.ecpm or 0.0),
            )
        )

    zero_coin_stmt = apply_search_like(select(AdRecord), AdRecord, q, AD_SEARCH_FIELDS)
    if success_conditions:
        zero_coin_stmt = zero_coin_stmt.where(*success_conditions)
    zero_coin_stmt = zero_coin_stmt.where(AdRecord.coin <= 0)
    for row in session.execute(zero_coin_stmt.order_by(AdRecord.id.desc()).limit(120)).scalars().all():
        alerts.append(
            make_ad_alert(
                alert_type="zero_coin",
                severity="medium",
                summary="閹存劕濮涢獮鍨啞鐠佹澘缍嶉惃鍕櫨鐢椒璐?0",
                source_type="ad_record",
                source_id=row.id,
                created_at=row.created_at,
                ad_group=classify_ad_group(row),
                coin=float(row.coin or 0.0),
                ecpm=float(row.ecpm or 0.0),
            )
        )

    zero_ecpm_stmt = apply_search_like(select(AdRecord), AdRecord, q, AD_SEARCH_FIELDS)
    if success_conditions:
        zero_ecpm_stmt = zero_ecpm_stmt.where(*success_conditions)
    zero_ecpm_stmt = zero_ecpm_stmt.where(AdRecord.ecpm <= 0)
    for row in session.execute(zero_ecpm_stmt.order_by(AdRecord.id.desc()).limit(120)).scalars().all():
        alerts.append(
            make_ad_alert(
                alert_type="zero_ecpm",
                severity="medium",
                summary="閹存劕濮涢獮鍨啞鐠佹澘缍嶉惃?ECPM 娑?0",
                source_type="ad_record",
                source_id=row.id,
                created_at=row.created_at,
                ad_group=classify_ad_group(row),
                coin=float(row.coin or 0.0),
                ecpm=float(row.ecpm or 0.0),
            )
        )

    mismatch_stmt = apply_search_like(select(AdRecord), AdRecord, q, AD_SEARCH_FIELDS)
    if success_conditions:
        mismatch_stmt = mismatch_stmt.where(*success_conditions)
    mismatch_stmt = mismatch_stmt.where(
        or_(
            AdRecord.ad_group.is_(None),
            AdRecord.ad_group == "",
            AdRecord.ad_group != expected_ad_group_sql_expression(),
        )
    )
    for row in session.execute(mismatch_stmt.order_by(AdRecord.id.desc()).limit(120)).scalars().all():
        alerts.append(
            make_ad_alert(
                alert_type="group_mismatch",
                severity="low",
                summary=f"楠炲灝鎲￠崚鍡欑矋娑撳氦顫夐崚娆愬腹閺傤厺绗夋稉鈧懛杈剧礉瑜版挸澧犻崐闂磋礋 {row.ad_group or '-'}",
                source_type="ad_record",
                source_id=row.id,
                created_at=row.created_at,
                ad_group=classify_ad_group(row),
                coin=float(row.coin or 0.0),
                ecpm=float(row.ecpm or 0.0),
            )
        )

    import_stmt = select(
        AdImportError.id,
        AdImportError.batch_id,
        AdImportError.row_number,
        AdImportError.request_id,
        AdImportError.message,
        AdImportError.raw_data,
        AdImportError.created_at,
        AdImportBatch.file_name,
        AdImportBatch.operator_name,
        AdImportBatch.status.label("batch_status"),
    ).join(AdImportBatch, AdImportBatch.id == AdImportError.batch_id)
    if q:
        import_stmt = import_stmt.where(
            or_(
                AdImportError.request_id.ilike(f"%{q}%"),
                AdImportError.message.ilike(f"%{q}%"),
                AdImportError.raw_data.ilike(f"%{q}%"),
                AdImportBatch.file_name.ilike(f"%{q}%"),
                AdImportBatch.operator_name.ilike(f"%{q}%"),
            )
        )
    if watched_from is not None:
        import_stmt = import_stmt.where(AdImportError.created_at >= watched_from)
    if watched_to is not None:
        import_stmt = import_stmt.where(AdImportError.created_at <= watched_to)
    for row in session.execute(import_stmt.order_by(AdImportError.created_at.desc()).limit(120)).all():
        message = str(row.message or "")
        severity = "high" if ("不能为空" in message or "已存在" in message) else "medium"
        alerts.append(
            make_ad_alert(
                alert_type="import_error",
                severity=severity,
                summary=message or "鐎电厧鍙嗘径杈Е",
                source_type="import_batch",
                source_id=int(row.batch_id or 0),
                created_at=row.created_at,
                request_id=str(row.request_id or ""),
                row_number=int(row.row_number or 0),
                file_name=str(row.file_name or ""),
                operator_name=str(row.operator_name or ""),
                source_label=f"导入批次 #{row.batch_id} / 行 {row.row_number}",
            )
        )

    return sorted(alerts, key=alert_sort_key, reverse=True)


def summarize_ad_alerts(alerts: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "total": len(alerts),
        "high": 0,
        "medium": 0,
        "low": 0,
    }
    type_counts = {key: 0 for key in AD_ALERT_TYPE_LABELS}
    source_counts = {"ad_record": 0, "import_batch": 0}
    for alert in alerts:
        severity = str(alert.get("severity") or "")
        alert_type = str(alert.get("alert_type") or "")
        source_type = str(alert.get("source_type") or "")
        if severity in summary:
            summary[severity] += 1
        if alert_type in type_counts:
            type_counts[alert_type] += 1
        if source_type in source_counts:
            source_counts[source_type] += 1
    return {
        "summary": summary,
        "type_breakdown": [
            {"alert_type": alert_type, "alert_type_label": ad_alert_title(alert_type), "count": count}
            for alert_type, count in type_counts.items()
            if count
        ],
        "source_breakdown": [
            {"source_type": source_type, "source_type_label": "楠炲灝鎲＄拋鏉跨秿" if source_type == "ad_record" else "鐎电厧鍙嗛幍瑙勵偧", "count": count}
            for source_type, count in source_counts.items()
            if count
        ],
    }


def serialize_withdrawal(item: Withdrawal) -> dict[str, Any]:
    with SessionLocal() as session:
        return payouts.withdrawal_payload(session, item)


def serialize_subsidy(item: Subsidy) -> dict[str, Any]:
    payload = serialize(item, list(item.__table__.columns.keys()))
    payload["target_status"] = 4 if item.status == 2 else item.status
    with SessionLocal() as session:
        payload['campaign'] = subsidy_campaigns.application_snapshot(session, item)
    return payload


def serialize_coinlog(item: CoinLog) -> dict[str, Any]:
    return serialize(item, list(item.__table__.columns.keys()))


def serialize_risk(item: RiskRecord) -> dict[str, Any]:
    return serialize(item, list(item.__table__.columns.keys()))


def serialize_kuaishou_risk(item: KuaishouRiskAssessment) -> dict[str, Any]:
    return serialize(item, list(item.__table__.columns.keys()))

def operator_display_name(admin: AdminUser) -> str:
    return (admin.display_name or admin.username or "").strip()[:128]


def mark_audit(item: Withdrawal | Subsidy, admin: AdminUser) -> None:
    item.audit_operator_id = admin.id
    item.audit_operator_name = operator_display_name(admin)
    item.audited_at = now()


def get_or_404(session: Session, model: Any, item_id: int, label: str) -> Any:
    item = session.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label}不存在")
    return item


def require_nonblank(changes: dict[str, Any], field: str, label: str) -> None:
    if field in changes and (changes[field] is None or not str(changes[field]).strip()):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"{label}不能为空")
    if field in changes:
        changes[field] = str(changes[field]).strip()


def require_not_none(changes: dict[str, Any], fields: list[str]) -> None:
    invalid = next((field for field in fields if field in changes and changes[field] is None), None)
    if invalid is not None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"{invalid} 不能为 null")


def validate_json_text(changes: dict[str, Any], field: str) -> None:
    if field not in changes:
        return
    require_not_none(changes, [field])
    try:
        value = json.loads(changes[field])
    except (TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"{field} 必须是有效的 JSON") from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"{field} 必须是 JSON 对象")


def hash_password(password: str) -> tuple[str, str]:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 390_000)
    return digest.hex(), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    try:
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 390_000)
    except ValueError:
        return False
    return hmac.compare_digest(digest.hex(), password_hash)

def prepare_member_passwords(changes: dict[str, Any]) -> None:
    for plain, hashed, salt in (("password", "password_hash", "password_salt"), ("pay_password", "pay_password_hash", "pay_password_salt")):
        value=changes.pop(plain, None)
        if value is not None:
            changes[hashed], changes[salt]=hash_password(str(value))


class LoginRequest(BaseModel):
    username: str
    password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class ProfileUpdate(BaseModel):
    display_name: str
    password: str = ""
    avatar: str | None = None


bearer_scheme = HTTPBearer(auto_error=False)


def serialize_admin(item: AdminUser) -> dict[str, Any]:
    return {
        "id": item.id,
        "username": item.username,
        "mobile": item.mobile,
        "avatar": item.avatar,
        "display_name": item.display_name,
        "role": item.role,
        "status": item.status,
        "last_login_at": stringify(item.last_login_at),
    }


def create_access_token(item: AdminUser) -> str:
    issued_at = now()
    return jwt.encode(
        {
            "sub": str(item.id),
            "typ": "admin",
            "username": item.username,
            "role": item.role,
            "iat": issued_at,
            "exp": issued_at + timedelta(minutes=JWT_EXPIRE_MINUTES),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def authentication_error(detail: str = "登录状态无效或已过期") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AdminUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise authentication_error("鐠囧嘲鍘涢惂璇茬秿")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("typ", "admin") != "admin":
            raise ValueError("not an admin token")
        admin_id = int(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise authentication_error() from exc

    with SessionLocal() as session:
        admin = session.get(AdminUser, admin_id)
        if admin is None or admin.status != 1:
            raise authentication_error("管理员不存在或已停用")
        session.expunge(admin)
        return admin


def allow_roles(*roles: str):
    def dependency(admin: AdminUser = Depends(require_admin)) -> AdminUser:
        if admin.role != "superadmin" and admin.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        return admin

    return dependency


def prepare_agent_password(changes: dict[str, Any]) -> None:
    if "password" not in changes or changes["password"] is None:
        changes.pop("password", None)
        return
    if changes["password"]:
        changes["password"], changes["salt"] = hash_password(str(changes["password"]))
    else:
        changes["password"] = ""
        changes["salt"] = ""


def validate_agent_parent(session: Session, parent_id: int, agent_id: int | None = None) -> None:
    if parent_id == 0:
        return

    current = get_or_404(session, Agent, parent_id, "上级主体")
    visited = {agent_id} if agent_id is not None else set()
    while current is not None:
        if current.id in visited:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="主体层级不能形成循环关系")
        visited.add(current.id)
        current = session.get(Agent, current.parent_id) if current.parent_id else None


def validate_game_agent(session: Session, agent_id: int) -> None:
    if agent_id:
        get_or_404(session, Agent, agent_id, "主体")


def validate_member_scope(session: Session, agent_id: int, game_id: int) -> None:
    if agent_id:
        get_or_404(session, Agent, agent_id, "主体")
    if game_id:
        game = get_or_404(session, Game, game_id, "游戏")
        if agent_id and game.agent_id != agent_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="游戏不属于所选主体")


def has_rows(session: Session, model: Any, condition: Any) -> bool:
    return bool(session.scalar(select(func.count()).select_from(model).where(condition)))


class AgentCreate(BaseModel):
    parent_id: int = Field(default=0, ge=0)
    name: str = Field(min_length=1, max_length=128)
    user_name: str | None = Field(default=None, max_length=128)
    avatar: str = Field(default="", max_length=255)
    password: str = Field(default="", max_length=128)
    user_id: int | None = Field(default=None, ge=0)
    role_id: int | None = Field(default=None, ge=0)
    security_key: str = Field(default="", max_length=255)
    status: Literal[0, 1] = 1
    game_ad_status: Literal[0, 1] = 0
    ht_status: Literal[0, 1] = 0
    is_gx: Literal[0, 1] = 0


class AgentUpdate(BaseModel):
    parent_id: int | None = Field(default=None, ge=0)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    user_name: str | None = Field(default=None, max_length=128)
    avatar: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=128)
    user_id: int | None = Field(default=None, ge=0)
    role_id: int | None = Field(default=None, ge=0)
    security_key: str | None = Field(default=None, max_length=255)
    status: Literal[0, 1] | None = None
    game_ad_status: Literal[0, 1] | None = None
    ht_status: Literal[0, 1] | None = None
    is_gx: Literal[0, 1] | None = None


class AgentOssConfig(BaseModel):
    ossKey: str = ""
    ossKeySecret: str = ""
    endPoint: str = ""
    bucket: str = ""


class GameCreate(BaseModel):
    agent_id: int = 0
    name: str
    game_icon: str = ""
    game_key: str = ""
    game_url: str = ""
    game_type: int = 0
    status: int = 1
    ad_status: int = 1
    lucky_enable: int = 1
    is_landscape: int = 0
    is_game: int = 1
    is_mobile: int = 0
    is_imei: int = 0
    raffle_num: int = 500
    star_countdown: float = 30.0
    over_countdown: float = 50.0
    star_coin: float = 0.01
    over_coin: float = 0.01
    coin_get: float = 1000000.0
    exchange_num: int = 10
    commission_status: int = 0
    commission_source: int = 0
    commission_rate: float = 0.0
    tixian_price: str = ""
    tixian_coin: str = ""
    tixian_wx: int = 0
    wx_appid: str = ""
    wx_secert: str = ""
    other_url: str = ""
    settings_json: str = "{}"
    ad_provider: str = Field(default="internal", max_length=64)
    ad_app_id: str = Field(default="", max_length=128)
    ad_app_key: str = Field(default="", max_length=255)
    ad_rewarded_unit_id: str = Field(default="", max_length=255)
    ad_interstitial_unit_id: str = Field(default="", max_length=255)
    ad_banner_unit_id: str = Field(default="", max_length=255)
    ad_splash_unit_id: str = Field(default="", max_length=255)
    ad_native_unit_id: str = Field(default="", max_length=255)
    ad_reward_coin: float = Field(default=0.01, ge=0, allow_inf_nan=False)
    ad_cooldown_seconds: int = Field(default=0, ge=0, le=86400)
    ad_config_enabled: Literal[0, 1] = 1


class GameUpdate(BaseModel):
    agent_id: int | None = None
    name: str | None = None
    game_icon: str | None = None
    game_key: str | None = None
    game_url: str | None = None
    game_type: int | None = None
    status: int | None = None
    ad_status: int | None = None
    lucky_enable: int | None = None
    is_landscape: int | None = None
    is_game: int | None = None
    is_mobile: int | None = None
    is_imei: int | None = None
    raffle_num: int | None = None
    star_countdown: float | None = None
    over_countdown: float | None = None
    star_coin: float | None = None
    over_coin: float | None = None
    coin_get: float | None = None
    exchange_num: int | None = None
    commission_status: int | None = None
    commission_source: int | None = None
    commission_rate: float | None = None
    tixian_price: str | None = None
    tixian_coin: str | None = None
    tixian_wx: int | None = None
    wx_appid: str | None = None
    wx_secert: str | None = None
    other_url: str | None = None
    settings_json: str | None = None
    ad_provider: str | None = Field(default=None, max_length=64)
    ad_app_id: str | None = Field(default=None, max_length=128)
    ad_app_key: str | None = Field(default=None, max_length=255)
    ad_rewarded_unit_id: str | None = Field(default=None, max_length=255)
    ad_interstitial_unit_id: str | None = Field(default=None, max_length=255)
    ad_banner_unit_id: str | None = Field(default=None, max_length=255)
    ad_splash_unit_id: str | None = Field(default=None, max_length=255)
    ad_native_unit_id: str | None = Field(default=None, max_length=255)
    ad_reward_coin: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    ad_cooldown_seconds: int | None = Field(default=None, ge=0, le=86400)
    ad_config_enabled: Literal[0, 1] | None = None


class MemberCreate(BaseModel):
    password: str | None = Field(default=None, min_length=6, max_length=128)
    pay_password: str | None = Field(default=None, min_length=6, max_length=128)
    raffle_open: Literal[0, 1] | None = None
    raffle_num: int | None = Field(default=None, ge=0)
    star_countdown: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    over_countdown: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    down_load: str = Field(default="", max_length=255)
    raffle_num2: int | None = Field(default=None, ge=0)
    star_countdown2: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    over_countdown2: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    realname_enable: Literal[0, 1] | None = None
    is_true: Literal[0, 1] | None = None
    receive_name: str = Field(default="", max_length=64)
    ip: str = ""
    agent_id: int = 0
    game_id: int = 0
    parent_id: int = 0
    username: str
    name: str = ""
    image_url: str = Field(default="", max_length=255)
    otherlevel: str = ""
    device_id: str = ""
    sex: int = 0
    real_name: str = ""
    card_no: str = ""
    address: str = ""
    coin: float = 0.0
    freeze_coin: float = 0.0
    coin_user: float = 0.0
    coin_user_month: float = 0.0
    coin_user_day: float = 0.0
    vip: int = 0
    status: int = 1
    exchange_enable: int = 1
    game_addiction_enable: int = 0
    game_addiction_time: str = Field(default="", max_length=64)
    is_white: int = 0
    ht_status: int = 0
    ht_id: int = 0
    ht_top_id: int = 0
    beishu: float = 0.0
    percent_zhi: float = 0.0
    percent_jian: float = 0.0
    percent_dai: float = 0.0
    percent_dai_two: float = 0.0
    last_login_ip: str = ""
    last_login_time: str = ""
    last_login_device_id: str = ""


class MemberUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=6, max_length=128)
    pay_password: str | None = Field(default=None, min_length=6, max_length=128)
    raffle_open: Literal[0, 1] | None = None
    raffle_num: int | None = Field(default=None, ge=0)
    star_countdown: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    over_countdown: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    down_load: str | None = Field(default=None, max_length=255)
    raffle_num2: int | None = Field(default=None, ge=0)
    star_countdown2: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    over_countdown2: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    realname_enable: Literal[0, 1] | None = None
    is_true: Literal[0, 1] | None = None
    receive_name: str | None = Field(default=None, max_length=64)
    ip: str | None = None
    agent_id: int | None = None
    game_id: int | None = None
    parent_id: int | None = None
    username: str | None = None
    name: str | None = None
    image_url: str | None = Field(default=None, max_length=255)
    otherlevel: str | None = None
    device_id: str | None = None
    sex: int | None = None
    real_name: str | None = None
    card_no: str | None = None
    address: str | None = None
    coin: float | None = Field(default=None, allow_inf_nan=False)
    freeze_coin: float | None = Field(default=None, allow_inf_nan=False)
    coin_user: float | None = None
    coin_user_month: float | None = None
    coin_user_day: float | None = None
    vip: int | None = None
    status: Literal[0, 1] | None = None
    exchange_enable: Literal[0, 1] | None = None
    game_addiction_enable: int | None = None
    game_addiction_time: str | None = Field(default=None, max_length=64)
    is_white: Literal[0, 1] | None = None
    ht_status: int | None = None
    ht_id: int | None = None
    ht_top_id: int | None = None
    beishu: float | None = None
    percent_zhi: float | None = None
    percent_jian: float | None = None
    percent_dai: float | None = None
    percent_dai_two: float | None = None
    last_login_ip: str | None = None
    last_login_time: str | None = None
    last_login_device_id: str | None = None


class WithdrawalUpdate(BaseModel):
    status: int | None = None
    plan_status: int | None = None
    sub_msg: str | None = None
    reason: str | None = None
    good_name: str | None = Field(default=None, max_length=255)
    device_manufacturer: str | None = Field(default=None, max_length=128)
    delivery_name: str | None = Field(default=None, max_length=128)
    delivery_no: str | None = Field(default=None, max_length=128)
    remark: str | None = Field(default=None, max_length=4096)
    receive_name: str | None = Field(default=None, max_length=64)
    receive_tel: str | None = Field(default=None, max_length=64)
    receive_address: str | None = Field(default=None, max_length=255)
    exchange_value: float | None = Field(default=None, allow_inf_nan=False)
    exchange_type: int | None = None


class WithdrawalAction(BaseModel):
    reason: str = ""


class SubsidyUpdate(BaseModel):
    status: int | None = None
    tx_price: float | None = Field(default=None, allow_inf_nan=False)
    price: float | None = Field(default=None, allow_inf_nan=False)
    pics: str | None = Field(default=None, max_length=4096)
    receive_name: str | None = Field(default=None, max_length=64)
    receive_tel: str | None = Field(default=None, max_length=64)
    sub_msg: str | None = Field(default=None, max_length=255)


class SubsidyAction(BaseModel):
    message: str = ""


class KuaishouRiskAssessmentCreate(BaseModel):
    assessment_date: date
    agent_id: int = Field(default=0, ge=0)
    game_id: int = Field(default=0, ge=0)
    pay_rate: float = Field(ge=0, le=100, allow_inf_nan=False)
    retain_1: float = Field(ge=0, le=1, allow_inf_nan=False)
    ctr: float = Field(ge=0, le=100, allow_inf_nan=False)
    flow_growth: float = Field(ge=-100, le=1000, allow_inf_nan=False)
    device_repeat: float = Field(ge=0, le=1, allow_inf_nan=False)


KUAISHOU_RISK_MODEL_VERSION = "v1-revised"


def calculate_kuaishou_risk(payload: KuaishouRiskAssessmentCreate) -> dict[str, Any]:
    """Calculate the corrected manual warning rule from the supplied TXT.

    Inputs use percent values for pay_rate/ctr/flow_growth and decimal values
    for retain_1/device_repeat. Each component is clamped to its declared
    weight so an invalid direction or outlier cannot overflow the total.
    """

    pay_score = min(35.0, max(0.0, payload.pay_rate / 12.0 * 35.0))
    retain_score = min(25.0, max(0.0, (1.0 - payload.retain_1 / 0.35) * 25.0))
    ctr_score = min(20.0, max(0.0, abs(payload.ctr - 3.5) / 3.5 * 20.0))
    flow_score = min(12.0, max(0.0, payload.flow_growth / 60.0 * 12.0))
    # device_repeat is a decimal ratio, so its maximum contribution is 8.
    device_score = min(8.0, max(0.0, payload.device_repeat * 8.0))
    risk_score = round(min(100.0, max(0.0, pay_score + retain_score + ctr_score + flow_score + device_score)), 2)
    if risk_score <= 30:
        risk_level = "safe"
        suggestion = "指标整体健康，按原定节奏运行并保持每日监控。"
    elif risk_score <= 55:
        risk_level = "attention"
        suggestion = "指标出现轻微异常，逐步核查流量渠道质量并观察转化与留存变化。"
    elif risk_score <= 80:
        risk_level = "warning"
        suggestion = "风险偏高，建议降低高风险流量占比并排查重复设备和异常广告行为。"
    else:
        risk_level = "high"
        suggestion = "风险较高，建议暂停扩大投放，进入人工复核并连续观察 3-5 天。"
    return {
        "pay_score": round(pay_score, 2),
        "retain_score": round(retain_score, 2),
        "ctr_score": round(ctr_score, 2),
        "flow_score": round(flow_score, 2),
        "device_score": round(device_score, 2),
        "risk_score": risk_score,
        "risk_level": risk_level,
        "suggestion": suggestion,
        "model_version": KUAISHOU_RISK_MODEL_VERSION,
    }


def ad_group_backfill_sql() -> str:
    secondary_checks = [
        "is_fu = 1",
        f"ad_type = '{SECONDARY_AD_LABEL}'",
        f"sub_ad_type = '{SECONDARY_AD_LABEL}'",
        *[f"ad_type LIKE '%{keyword}%'" for keyword in SECONDARY_AD_TYPES],
        *[f"sub_ad_type LIKE '%{keyword}%'" for keyword in SECONDARY_AD_TYPES],
    ]
    return f"""
        UPDATE ad_records
        SET ad_group = CASE
            WHEN {' OR '.join(secondary_checks)} THEN '{SECONDARY_AD_LABEL}'
            ELSE '{MAIN_AD_LABEL}'
        END
    """


def ensure_development_schema() -> None:
    if APP_ENV == "production":
        return
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "risk_records" in table_names and "network_status" not in {column["name"] for column in inspector.get_columns("risk_records")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE risk_records ADD COLUMN network_status INTEGER"))
    if "games" in table_names:
        columns={column["name"] for column in inspector.get_columns("games")}
        with engine.begin() as connection:
            for column,definition in [("game_ad_status","INTEGER"),("game_lottery_num","FLOAT")]:
                if column not in columns:connection.execute(text(f"ALTER TABLE games ADD COLUMN {column} {definition}"))
    if "agents" in table_names and "oss_config" not in {column["name"] for column in inspector.get_columns("agents")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE agents ADD COLUMN oss_config TEXT NOT NULL DEFAULT '{}'"))
    if "admin_users" in table_names:
        admin_columns = {column["name"] for column in inspector.get_columns("admin_users")}
        if "mobile" not in admin_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE admin_users ADD COLUMN mobile VARCHAR(32) NOT NULL DEFAULT ''"))
        if "avatar" not in admin_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE admin_users ADD COLUMN avatar VARCHAR(1024) NOT NULL DEFAULT '/assets/img/avatar.png'"))
    if "members" in table_names:
        member_columns = {column["name"] for column in inspector.get_columns("members")}
        if "realname_enable" not in member_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE members ADD COLUMN realname_enable INTEGER"))
        additions={"raffle_open":"INTEGER","raffle_num":"INTEGER","star_countdown":"FLOAT","over_countdown":"FLOAT","down_load":"VARCHAR(255) NOT NULL DEFAULT ''"}
        additions.update({"raffle_num2":"INTEGER","star_countdown2":"FLOAT","over_countdown2":"FLOAT"})
        additions["otherlevel"] = "TEXT NOT NULL DEFAULT ''"
        additions.update({"password_hash":"VARCHAR(255) NOT NULL DEFAULT ''","password_salt":"VARCHAR(64) NOT NULL DEFAULT ''","pay_password_hash":"VARCHAR(255) NOT NULL DEFAULT ''","pay_password_salt":"VARCHAR(64) NOT NULL DEFAULT ''"})
        for column, definition in additions.items():
            if column not in member_columns:
                with engine.begin() as connection:
                    connection.execute(text(f"ALTER TABLE members ADD COLUMN {column} {definition}"))
        if "receive_name" not in member_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE members ADD COLUMN receive_name VARCHAR(64) NOT NULL DEFAULT ''"))
        if "is_true" not in member_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE members ADD COLUMN is_true INTEGER"))
        if "ip" not in member_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE members ADD COLUMN ip VARCHAR(64) NOT NULL DEFAULT ''"))
    if "ad_records" not in table_names:
        return
    with engine.begin() as connection:
        ad_columns = {column["name"] for column in inspector.get_columns("ad_records")}
        if "ad_group" not in ad_columns:
            connection.execute(text(f"ALTER TABLE ad_records ADD COLUMN ad_group VARCHAR(32) NOT NULL DEFAULT '{MAIN_AD_LABEL}'"))
            connection.execute(text(ad_group_backfill_sql()))

        if "withdrawals" in table_names:
            withdrawal_columns = {column["name"] for column in inspector.get_columns("withdrawals")}
            withdrawal_additions = {
                "delivery_name": "VARCHAR(128) NOT NULL DEFAULT ''",
                "delivery_no": "VARCHAR(128) NOT NULL DEFAULT ''",
                "remark": "TEXT NOT NULL DEFAULT ''",
                "good_name": "VARCHAR(255) NOT NULL DEFAULT ''",
                "device_manufacturer": "VARCHAR(128) NOT NULL DEFAULT ''",
                "check_status_txt": "VARCHAR(255) NOT NULL DEFAULT ''",
                "audit_operator_id": "INTEGER NOT NULL DEFAULT 0",
                "audit_operator_name": "VARCHAR(128) NOT NULL DEFAULT ''",
                "audited_at": "DATETIME",
                "transfer_operator_id": "INTEGER NOT NULL DEFAULT 0",
                "transfer_operator_name": "VARCHAR(128) NOT NULL DEFAULT ''",
                "transferred_at": "DATETIME",
            }
            for column, definition in withdrawal_additions.items():
                if column not in withdrawal_columns:
                    connection.execute(text(f"ALTER TABLE withdrawals ADD COLUMN {column} {definition}"))

        if "subsidies" in table_names:
            subsidy_columns = {column["name"] for column in inspector.get_columns("subsidies")}
            subsidy_additions = {
                "receive_name": "VARCHAR(64) NOT NULL DEFAULT ''",
                "receive_tel": "VARCHAR(64) NOT NULL DEFAULT ''",
                "audit_operator_id": "INTEGER NOT NULL DEFAULT 0",
                "audit_operator_name": "VARCHAR(128) NOT NULL DEFAULT ''",
                "audited_at": "DATETIME",
            }
            for column, definition in subsidy_additions.items():
                if column not in subsidy_columns:
                    connection.execute(text(f"ALTER TABLE subsidies ADD COLUMN {column} {definition}"))


def seed_data() -> None:
    Base.metadata.create_all(engine)
    ensure_development_schema()

    with SessionLocal() as session:
        admin = session.scalar(select(AdminUser).where(AdminUser.username == ADMIN_USERNAME))
        if admin is None:
            password_hash, password_salt = hash_password(ADMIN_PASSWORD)
            session.add(
                AdminUser(
                    username=ADMIN_USERNAME,
                    password_hash=password_hash,
                    password_salt=password_salt,
                    display_name="系统管理员",
                    role="superadmin",
                    status=1,
                )
            )

        phone_admin = session.scalar(select(AdminUser).where(AdminUser.username == "18532306918"))
        if phone_admin is None:
            phone_hash, phone_salt = hash_password("123456")
            session.add(AdminUser(username="18532306918", password_hash=phone_hash, password_salt=phone_salt, display_name="涓夋渤甯傛懇缇骇缃戠粶绉戞妧鏈夐檺鍏徃", role="superadmin", status=1))
        session.commit()
        if session.scalar(select(Agent.id).limit(1)) is not None:
            return

        agent = Agent(
            id=133,
            name="默认主体",
            parent_id=0,
            status=1,
            game_ad_status=0,
            ht_status=0,
            is_gx=0,
            user_name="admin",
        )
        game = Game(
            id=237,
            agent_id=133,
            name="默认游戏",
            game_icon="https://ad.leadink.cn/uploads/20260625/3de844eace16e2fb5ac4293ac7a3be5b.jpg",
            game_key="com.hanhai.hksc",
            game_url="",
            status=1,
            ad_status=1,
            lucky_enable=1,
            game_type=0,
            raffle_num=500,
            star_countdown=30.0,
            over_countdown=50.0,
            coin_get=1000000.0,
            exchange_num=10,
            tixian_price="3,5,10,20,50,100,150,200",
            tixian_coin="10,20,30,60,150,300,450,600",
            settings_json=json.dumps(
                {
                    "vip_up": 2,
                    "coin_get_once": 100000,
                    "risk_select": "1,2,3,4,5,6,7",
                    "wx_share_url": "",
                },
                ensure_ascii=False,
            ),
        )
        member = Member(
            id=695016,
            agent_id=133,
            game_id=237,
            username="测试用户",
            name="测试用户",
            image_url="https://thirdwx.qlogo.cn/mmopen/vi_32/JZxvFJ5qOCh85snVpG4MolSia5jSZ3CbX1lbuPJT91D0gCadEkSTvUXiccfiaHS9JwtMgo5l3zZEib9JkY5U7gI6eA/132",
            device_id="4A24005C-D751-4FD5-B6E0-CC6C89B5AC5A",
            coin=0.0,
            freeze_coin=0.0,
            coin_user=0.0,
            coin_user_month=0.0,
            coin_user_day=0.0,
            vip=0,
            status=1,
            exchange_enable=1,
            game_addiction_enable=0,
            is_white=0,
            last_login_ip="183.34.194.167",
            last_login_time="2026-08-20 20:37:34",
            last_login_device_id="4A24005C-D751-4FD5-B6E0-CC6C89B5AC5A",
        )
        ad = AdRecord(
            parent_id=675155,
            parent_payment_name="",
            user_id=695016,
            user_account="19999999998",
            agent_id=133,
            game_id=237,
            receive_name="",
            game_name="欢快消除",
            ecpm=38.1597,
            coin=0.27,
            estimate_income=0.0,
            is_lottery=1,
            ad_network_platform_name="广告平台",
            reward_type="领取",
            ad_type="激励",
            is_type=0,
            is_fu=0,
            fu_type=1,
            is_look=1,
            status="成功",
            watched_at=datetime(2026, 8, 23, 10, 35, 26, tzinfo=UTC),
            ad_code="b1hf1pndqdpu2r",
            request_id="9e65107c2026e1645d24495ac6d0d893",
            trans_id="9e65107c2026e1645d24495ac6d0d893_14556460_1785724502342",
        )
        withdrawal = Withdrawal(
            user_id=695016,
            agent_id=133,
            game_id=237,
            receive_name="",
            receive_tel="",
            exchange_value=0.0,
            exchange_type=0,
            status=0,
            plan_status=0,
        )
        subsidy = Subsidy(user_id=695016, agent_id=133, game_id=237, tx_price=0.0, price=0.0, status=0)
        coinlog = CoinLog(user_id=695016, agent_id=133, game_id=237, coin_before=0.0, coin=0.0, coin_after=0.0, type=100, remark="初始化")
        risk = RiskRecord(user_id=695016, agent_id=133, game_id=237, tagcode="login", tags="", hardware_main_id="4A24005C-D751-4FD5-B6E0-CC6C89B5AC5A", ip="183.34.194.167", action="login", risk_score=0, risk_level="low")
        coinlog = CoinLog(user_id=695016, agent_id=133, game_id=237, coin_before=0.0, coin=0.0, coin_after=0.0, type=100, remark="初始化")
        risk = RiskRecord(user_id=695016, agent_id=133, game_id=237, tagcode="login", tags="", hardware_main_id="4A24005C-D751-4FD5-B6E0-CC6C89B5AC5A", ip="183.34.194.167", action="login", risk_score=0, risk_level="low")
        session.add_all([agent, game, member, ad, withdrawal, subsidy, coinlog, risk])
        session.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    seed_data()
    yield


app = FastAPI(title="广告会员后台", version="0.1.0", lifespan=lifespan, docs_url=None)
from .request_audit import AppRequestAudit
app.add_middleware(AppRequestAudit)


@app.get("/docs", include_in_schema=False)
def api_documentation():
    from fastapi.openapi.docs import get_swagger_ui_html
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title="广告会员后台 - API 文档",
        swagger_js_url="/vendor/swagger-ui/swagger-ui-bundle.js",
        swagger_css_url="/vendor/swagger-ui/swagger-ui.css",
        swagger_favicon_url="/vendor/swagger-ui/favicon-32x32.png",
    )

# ---------------------------------------------------------------------------
# Public user APP API
# ---------------------------------------------------------------------------

app_api = APIRouter(prefix="/api/app/v1", tags=["User APP"])
app_bearer_scheme = HTTPBearer(auto_error=False)
APP_ACCESS_MINUTES = int(os.getenv("APP_ACCESS_MINUTES", "120"))
APP_REFRESH_DAYS = int(os.getenv("APP_REFRESH_DAYS", "30"))
APP_AD_SESSION_MINUTES = int(os.getenv("APP_AD_SESSION_MINUTES", "5"))


class AppClient(BaseModel):
    app_id: str = Field(default="ad-member", min_length=1, max_length=64)
    app_version: str = Field(default="", max_length=32)
    platform: str = Field(default="", max_length=32)
    device_id: str = Field(min_length=1, max_length=128)


class AppRegisterRequest(AppClient):
    username: str = Field(min_length=4, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    invite_code: str = Field(default="", max_length=128)
    agent_id: int | None = Field(default=None, ge=1)
    game_id: int | None = Field(default=None, ge=1)


class AppLoginRequest(AppClient):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class AppWechatLoginRequest(AppClient):
    code: str = Field(min_length=1, max_length=1024)
    game_id: int | None = Field(default=None, ge=1)
    provider: Literal["mini_program", "app"] = "mini_program"
    nickname: str = Field(default="", max_length=128)
    avatar_url: str = Field(default="", max_length=512)


class AppRefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=512)
    device_id: str = Field(min_length=1, max_length=128)


class AppLogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=20, max_length=512)


class AppProfileUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    image_url: str | None = Field(default=None, max_length=255)
    sex: int | None = Field(default=None, ge=0, le=2)
    real_name: str | None = Field(default=None, max_length=64)
    receive_name: str | None = Field(default=None, max_length=64)
    address: str | None = Field(default=None, max_length=255)


class AppSubsidyCreate(BaseModel):
    """Client submits the withdrawal condition; the reviewer sets price."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    game_id: int | None = Field(default=None, ge=1)
    tx_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    pics: list[str] = Field(default_factory=list, max_length=9)
    receive_name: str = Field(min_length=1, max_length=64)
    receive_tel: str = Field(min_length=1, max_length=64)


class AppPasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class AppAdRequest(AppClient):
    game_id: int = Field(ge=1)
    risk_check_id: str = Field(default="", max_length=64)
    placement: str = Field(default="rewarded", min_length=1, max_length=64)
    ad_type: str = Field(default="rewarded", min_length=1, max_length=64)
    client_request_id: str = Field(default="", max_length=128)


class AppAdEventRequest(BaseModel):
    event_id: str = Field(min_length=1, max_length=128)
    session_token: str = Field(min_length=20, max_length=512)
    occurred_at: datetime | None = None
    provider_event_id: str = Field(default="", max_length=128)
    watched_seconds: float = Field(default=0, ge=0, le=86400)
    reason: str = Field(default="", max_length=128)


def _app_member_payload(member: Member, device: str = "") -> dict[str, Any]:
    return {
        "id": member.id,
        "username": member.username,
        "name": member.name,
        "image_url": member.image_url,
        "sex": member.sex,
        "real_name": member.real_name,
        "receive_name": member.receive_name,
        "address": member.address,
        "agent_id": member.agent_id,
        "game_id": member.game_id,
        "vip": member.vip,
        "status": member.status,
        "coin": member.coin,
        "freeze_coin": member.freeze_coin,
        "coin_user": member.coin_user,
        "device_id": device or member.last_login_device_id or member.device_id,
    }


def _token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _create_app_access_token(member: Member) -> str:
    issued_at = now()
    return jwt.encode({
        "sub": str(member.id),
        "typ": "app_user",
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=APP_ACCESS_MINUTES),
    }, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _new_refresh_session(session: Session, member: Member, device_id: str) -> str:
    raw = secrets.token_urlsafe(48)
    session.add(AppRefreshSession(
        member_id=member.id,
        token_hash=_token_hash(raw),
        device_id=device_id,
        expires_at=now() + timedelta(days=APP_REFRESH_DAYS),
    ))
    return raw


def _app_tokens(session: Session, member: Member, device_id: str) -> dict[str, Any]:
    refresh = _new_refresh_session(session, member, device_id)
    return {
        "access_token": _create_app_access_token(member),
        "refresh_token": refresh,
        "expires_in": APP_ACCESS_MINUTES * 60,
        "token_type": "bearer",
    }


def _app_auth_error(detail: str = "Invalid or expired user token") -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def require_app_member(credentials: HTTPAuthorizationCredentials | None = Depends(app_bearer_scheme)) -> Member:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _app_auth_error()
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("typ") != "app_user":
            raise ValueError("wrong token type")
        member_id = int(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise _app_auth_error() from exc
    with SessionLocal() as session:
        member = session.get(Member, member_id)
        if member is None or member.status != 1:
            raise _app_auth_error("Account is disabled or does not exist")
        session.expunge(member)
        return member


def _app_validate_password(password: str) -> None:
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise HTTPException(status_code=422, detail="Password must contain at least 8 characters, letters and numbers")


def _app_game_for_member(session: Session, member: Member, game_id: int | None = None) -> Game:
    selected_id = game_id or member.game_id
    game = session.get(Game, selected_id) if selected_id else None
    if game is None or game.status != 1 or game.ad_status != 1:
        raise HTTPException(status_code=404, detail="Game is unavailable")
    if game.agent_id != member.agent_id:
        raise HTTPException(status_code=403, detail="Game does not belong to this account")
    return game


def _app_device(session: Session, member: Member, device_id: str, request: Request, app_version: str = "") -> None:
    device = session.get(MemberDevice, member.id)
    if device is None:
        device = MemberDevice(user_id=member.id)
        session.add(device)
    device.device_id = device_id
    device.app_version = app_version
    device.ip_address = request.client.host if request.client else ""
    member.device_id = device_id
    member.last_login_device_id = device_id
    member.last_login_ip = request.client.host if request.client else ""
    member.last_login_time = now().isoformat()


def _app_ad_result(item: AppAdSession, member: Member) -> dict[str, Any]:
    return {
        "ad_session_id": item.id,
        "request_id": item.request_id,
        "placement": item.placement,
        "provider": item.provider,
        "ad_unit_id": item.ad_unit_id,
        "ad_type": item.ad_type,
        "reward": {"enabled": item.reward_coin > 0, "coin": item.reward_coin, "currency": "coin"},
        "session_token": "",
        "expires_at": stringify(item.expires_at),
        "status": item.status,
        "reward_verification": "server_callback" if item.provider.lower() == "taku" else "client",
        "taku_user_id": str(member.id) if item.provider.lower() == "taku" else None,
        "taku_extra_data": _taku_extra_data(item) if item.provider.lower() == "taku" else None,
    }


def _app_subsidy_payload(item: Subsidy) -> dict[str, Any]:
    """Return the user-safe view of a subsidy application."""
    with SessionLocal() as session:
        campaign = subsidy_campaigns.application_snapshot(session, item)
    return {
        "campaign": campaign,
        "id": item.id,
        "user_id": item.user_id,
        "agent_id": item.agent_id,
        "game_id": item.game_id,
        "tx_price": item.tx_price,
        "price": item.price,
        "pics": item.pics,
        "receive_name": item.receive_name,
        "receive_tel": item.receive_tel,
        "status": item.status,
        "target_status": 4 if item.status == 2 else item.status,
        "sub_msg": item.sub_msg,
        "created_at": stringify(item.created_at),
        "updated_at": stringify(item.updated_at),
        "audited_at": stringify(item.audited_at),
    }


@app_api.post("/auth/register", status_code=201)
def app_register(payload: AppRegisterRequest, request: Request) -> dict[str, Any]:
    _app_validate_password(payload.password)
    username = payload.username.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{4,64}", username):
        raise HTTPException(status_code=422, detail="Username may contain letters, numbers, dot, underscore and hyphen")
    with SessionLocal() as session:
        if session.scalar(select(Member.id).where(Member.username == username)) is not None:
            raise HTTPException(status_code=409, detail="Username already exists")
        agent_id = payload.agent_id
        game_id = payload.game_id
        if game_id:
            game = session.get(Game, game_id)
            if game is None or game.status != 1:
                raise HTTPException(status_code=422, detail="Game is unavailable")
            if agent_id and game.agent_id != agent_id:
                raise HTTPException(status_code=422, detail="Game does not belong to agent")
            agent_id = game.agent_id
        if not agent_id:
            agent_id = session.scalar(select(Agent.id).where(Agent.status == 1).order_by(Agent.id).limit(1))
        if not agent_id:
            raise HTTPException(status_code=503, detail="No active registration channel")
        if not game_id:
            game_id = session.scalar(select(Game.id).where(Game.agent_id == agent_id, Game.status == 1).order_by(Game.id).limit(1))
        if not game_id:
            raise HTTPException(status_code=503, detail="No active game is available")
        password_hash, password_salt = hash_password(payload.password)
        member = Member(agent_id=agent_id, game_id=game_id, username=username, name=username,
                        password_hash=password_hash, password_salt=password_salt, status=1)
        session.add(member)
        session.flush()
        _app_device(session, member, payload.device_id, request, payload.app_version)
        tokens = _app_tokens(session, member, payload.device_id)
        session.commit()
        session.refresh(member)
        return {"data": {"user": _app_member_payload(member, payload.device_id), **tokens}, "request_id": secrets.token_urlsafe(12)}


def _wechat_game(session: Session, game_id: int | None) -> Game:
    game = session.get(Game, game_id) if game_id else session.scalar(select(Game).where(Game.status == 1).order_by(Game.id).limit(1))
    if game is None or game.status != 1:
        raise HTTPException(status_code=404, detail="Game is unavailable")
    return game


def _wechat_exchange_code(provider: str, code: str, app_id: str, secret: str) -> dict[str, str]:
    if not app_id or not secret:
        raise HTTPException(status_code=503, detail="WeChat login is not configured for this game")
    if provider == "mini_program":
        endpoint = "https://api.weixin.qq.com/sns/jscode2session"
        params = {"appid": app_id, "secret": secret, "js_code": code, "grant_type": "authorization_code"}
    else:
        endpoint = "https://api.weixin.qq.com/sns/oauth2/access_token"
        params = {"appid": app_id, "secret": secret, "code": code, "grant_type": "authorization_code"}
    try:
        request = UrlRequest(endpoint + "?" + urlencode(params), headers={"Accept": "application/json"})
        with urlopen(request, timeout=float(os.getenv("WECHAT_HTTP_TIMEOUT", "8"))) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="WeChat authorization service is unavailable") from exc
    if not isinstance(result, dict) or result.get("errcode") not in (None, 0):
        raise HTTPException(status_code=401, detail="Invalid WeChat authorization code")
    openid = str(result.get("openid") or "").strip()
    if not openid:
        raise HTTPException(status_code=401, detail="WeChat authorization did not return an openid")
    return {"openid": openid, "unionid": str(result.get("unionid") or "").strip()}


def _wechat_username(session: Session, openid: str) -> str:
    prefix = "wx_" + hashlib.sha256(openid.encode("utf-8")).hexdigest()[:20]
    username = prefix
    suffix = 1
    while session.scalar(select(Member.id).where(Member.username == username)) is not None:
        username = f"{prefix}_{suffix}"
        suffix += 1
    return username


@app_api.post("/auth/wechat-login")
@app_api.post("/auth/wechat")
def app_wechat_login(payload: AppWechatLoginRequest, request: Request) -> dict[str, Any]:
    with SessionLocal() as session:
        game = _wechat_game(session, payload.game_id)
        app_id = game.wx_appid.strip()
        identity = _wechat_exchange_code(payload.provider, payload.code.strip(), app_id, game.wx_secert.strip())
        stored = session.scalar(select(WechatIdentity).where(
            WechatIdentity.provider == payload.provider,
            WechatIdentity.app_id == app_id,
            WechatIdentity.openid == identity["openid"],
        ))
        if stored is None and identity["unionid"]:
            stored = session.scalar(select(WechatIdentity).where(
                WechatIdentity.provider == payload.provider,
                WechatIdentity.app_id == app_id,
                WechatIdentity.unionid == identity["unionid"],
            ))
        member = session.get(Member, stored.member_id) if stored else None
        if member is None:
            password, salt = hash_password(secrets.token_urlsafe(32))
            member = Member(agent_id=game.agent_id, game_id=game.id, username=_wechat_username(session, identity["openid"]),
                            name=payload.nickname.strip(), image_url=payload.avatar_url.strip(), password_hash=password,
                            password_salt=salt, status=1)
            session.add(member)
            session.flush()
            stored = WechatIdentity(member_id=member.id, provider=payload.provider, app_id=app_id,
                                    openid=identity["openid"], unionid=identity["unionid"],
                                    nickname=payload.nickname.strip(), avatar_url=payload.avatar_url.strip())
            session.add(stored)
        elif member.status != 1:
            raise HTTPException(status_code=403, detail="Account is disabled")
        if stored.unionid == "" and identity["unionid"]:
            stored.unionid = identity["unionid"]
        if payload.nickname.strip() and not member.name:
            member.name = payload.nickname.strip()
        if payload.avatar_url.strip() and not member.image_url:
            member.image_url = payload.avatar_url.strip()
        device = session.get(MemberDevice, member.id)
        if device and device.device_id and device.device_id != payload.device_id and device.device_id_ban:
            raise HTTPException(status_code=403, detail="Device is blocked")
        _app_device(session, member, payload.device_id, request, payload.app_version)
        session.add(MemberLoginLog(user_id=member.id, game_id=member.game_id, device_id=payload.device_id, ip=request.client.host if request.client else ""))
        tokens = _app_tokens(session, member, payload.device_id)
        session.commit()
        session.refresh(member)
        return {"data": {"user": _app_member_payload(member, payload.device_id), **tokens}, "request_id": secrets.token_urlsafe(12)}


@app_api.post("/auth/login")
def app_login(payload: AppLoginRequest, request: Request) -> dict[str, Any]:
    with SessionLocal() as session:
        member = session.scalar(select(Member).where(Member.username == payload.username.strip()))
        if member is None or member.status != 1 or not member.password_hash or not verify_password(payload.password, member.password_hash, member.password_salt):
            raise _app_auth_error("Invalid username or password")
        device = session.get(MemberDevice, member.id)
        if device and device.device_id and device.device_id != payload.device_id and device.device_id_ban:
            raise HTTPException(status_code=403, detail="Device is blocked")
        _app_device(session, member, payload.device_id, request, payload.app_version)
        session.add(MemberLoginLog(user_id=member.id, game_id=member.game_id, device_id=payload.device_id, ip=request.client.host if request.client else ""))
        tokens = _app_tokens(session, member, payload.device_id)
        session.commit()
        session.refresh(member)
        return {"data": {"user": _app_member_payload(member, payload.device_id), **tokens}, "request_id": secrets.token_urlsafe(12)}


@app_api.post("/auth/refresh")
def app_refresh(payload: AppRefreshRequest) -> dict[str, Any]:
    with SessionLocal() as session:
        stored = session.scalar(select(AppRefreshSession).where(AppRefreshSession.token_hash == _token_hash(payload.refresh_token)))
        if stored is None or stored.revoked_at is not None or stored.expires_at.replace(tzinfo=UTC) <= now() or stored.device_id != payload.device_id:
            raise _app_auth_error("Refresh token is invalid or expired")
        member = session.get(Member, stored.member_id)
        if member is None or member.status != 1:
            raise _app_auth_error("Account is disabled or does not exist")
        stored.revoked_at = now(); stored.last_used_at = now()
        result = _app_tokens(session, member, payload.device_id)
        session.commit()
        return {"data": {"user": _app_member_payload(member, payload.device_id), **result}, "request_id": secrets.token_urlsafe(12)}


@app_api.post("/auth/logout", status_code=204)
def app_logout(payload: AppLogoutRequest | None = None, member: Member = Depends(require_app_member)) -> Response:
    if payload is not None and payload.refresh_token:
        with SessionLocal() as session:
            item = session.scalar(select(AppRefreshSession).where(AppRefreshSession.member_id == member.id, AppRefreshSession.token_hash == _token_hash(payload.refresh_token)))
            if item: item.revoked_at = now(); session.commit()
    return Response(status_code=204)


@app_api.get("/me")
def app_me(member: Member = Depends(require_app_member)) -> dict[str, Any]:
    return {"data": _app_member_payload(member), "request_id": secrets.token_urlsafe(12)}


@app_api.patch("/me")
def app_update_me(payload: AppProfileUpdate, member: Member = Depends(require_app_member)) -> dict[str, Any]:
    changes = payload.model_dump(exclude_unset=True)
    with SessionLocal() as session:
        stored = get_or_404(session, Member, member.id, "User")
        for key, value in changes.items(): setattr(stored, key, value.strip() if isinstance(value, str) else value)
        session.commit(); session.refresh(stored)
        return {"data": _app_member_payload(stored), "request_id": secrets.token_urlsafe(12)}


@app_api.post("/auth/change-password", status_code=204)
def app_change_password(payload: AppPasswordChange, member: Member = Depends(require_app_member)) -> Response:
    _app_validate_password(payload.new_password)
    with SessionLocal() as session:
        stored = get_or_404(session, Member, member.id, "User")
        if not verify_password(payload.current_password, stored.password_hash, stored.password_salt):
            raise _app_auth_error("Current password is incorrect")
        stored.password_hash, stored.password_salt = hash_password(payload.new_password)
        session.commit()
    return Response(status_code=204)


@app_api.get("/games")
def app_games(member: Member = Depends(require_app_member)) -> dict[str, Any]:
    with SessionLocal() as session:
        rows = session.scalars(select(Game).where(Game.agent_id == member.agent_id, Game.status == 1, Game.ad_status == 1).order_by(Game.id)).all()
        return {"data": {"items": [{"id": g.id, "name": g.name, "game_icon": g.game_icon, "game_key": g.game_key, "status": g.status, "ad_status": g.ad_status} for g in rows], "total": len(rows)}, "request_id": secrets.token_urlsafe(12)}


@app_api.get("/bootstrap")
def app_bootstrap(game_id: int | None = Query(None, ge=1), member: Member = Depends(require_app_member)) -> dict[str, Any]:
    with SessionLocal() as session:
        game = _app_game_for_member(session, member, game_id)
        config = game_ad_config(game)
        placements = [{"placement": name, "ad_type": name, "ad_unit_id": value["unit_id"], "cooldown_seconds": value["cooldown_seconds"], "reward_coin": value["reward_coin"]} for name, value in config["placements"].items() if value["unit_id"] or name == "rewarded"]
        return {"data": {"user": _app_member_payload(member), "game": {"id": game.id, "name": game.name, "status": game.status, "ad_status": game.ad_status}, "ad_config": {"enabled": config["enabled"], "provider": config["provider"], "app_id": config["app_id"], "app_key": config["app_key"], "placements": placements}, "server_time": now().isoformat()}, "request_id": secrets.token_urlsafe(12)}


@app_api.post("/ads/request", status_code=201)
def app_ad_request(payload: AppAdRequest, request: Request, member: Member = Depends(require_app_member)) -> dict[str, Any]:
    with SessionLocal() as session:
        device_risk.game_lock(session, payload.game_id)
        game = _app_game_for_member(session, member, payload.game_id)
        config = game_ad_config(game)
        placement = config["placements"].get(payload.placement) or config["placements"]["rewarded"]
        if config["provider"].lower() == "taku":
            callback_enabled, callback_key = taku_credentials(session, game.id)
            if not callback_enabled or not callback_key or not placement["unit_id"]:
                raise HTTPException(status_code=503, detail="TAKU reward callback is not configured")
            if payload.placement != "rewarded" or payload.ad_type != "rewarded":
                raise HTTPException(status_code=422, detail="TAKU reward sessions require rewarded placement and type")
        elif APP_ENV == "production":
            raise HTTPException(status_code=503, detail="Ad provider is unavailable")
        if not config["enabled"] or (payload.placement != "rewarded" and not placement["unit_id"]):
            raise HTTPException(status_code=503, detail="Ad placement is not configured")
        if payload.client_request_id:
            existing = session.scalar(select(AppAdSession).where(AppAdSession.member_id == member.id, AppAdSession.game_id == game.id, AppAdSession.client_request_id == payload.client_request_id, AppAdSession.status == "issued"))
            if existing:
                if existing.expires_at.replace(tzinfo=UTC) <= now():
                    raise HTTPException(409, "Ad session expired; use a new client_request_id")
                device_risk.authorize_retry(session, payload, existing)
                token = secrets.token_urlsafe(32)
                existing.session_token_hash = _token_hash(token); session.commit()
                result = _app_ad_result(existing, member); result["session_token"] = token
                return {"data": result, "request_id": existing.request_id}
        session_id = "ads_" + secrets.token_urlsafe(18)
        request_id = "req_ad_" + secrets.token_urlsafe(14)
        session_token = secrets.token_urlsafe(32)
        device_risk.authorize_ad(session, payload, member, session_id)
        item = AppAdSession(id=session_id, member_id=member.id, agent_id=member.agent_id, game_id=game.id, device_id=payload.device_id,
                            client_request_id=payload.client_request_id, request_id=request_id, placement=payload.placement, ad_type=payload.ad_type,
                            provider=config["provider"], ad_unit_id=placement["unit_id"] or game.game_key or str(game.id), reward_coin=placement["reward_coin"],
                            status="issued", session_token_hash=_token_hash(session_token), expires_at=now() + timedelta(minutes=APP_AD_SESSION_MINUTES))
        session.add(item); session.commit()
        with SessionLocal() as audit:
            stored = audit.get(AppAdSession, item.id)
            _ad_flow_log(audit, stored, "ad_requested", detail={"placement": payload.placement, "client_request_id": payload.client_request_id})
            audit.commit()
        result = _app_ad_result(item, member); result["session_token"] = session_token
        return {"data": result, "request_id": request_id}


def _app_session(session: Session, session_id: str, member: Member, token: str) -> AppAdSession:
    if session.bind.dialect.name == "sqlite":
        session.execute(text("BEGIN IMMEDIATE"))
    session.scalar(select(Member).where(Member.id == member.id).with_for_update())
    item = session.scalar(select(AppAdSession).where(AppAdSession.id == session_id).with_for_update())
    if item is None or item.member_id != member.id or not hmac.compare_digest(item.session_token_hash, _token_hash(token)):
        raise HTTPException(status_code=404, detail="Ad session not found")
    if item.expires_at.replace(tzinfo=UTC) <= now() and item.status not in ("rewarded", "failed", "expired"):
        item.status = "expired"
        raise HTTPException(status_code=409, detail="Ad session expired")
    return item


@app_api.post("/ads/{ad_session_id}/impression", status_code=202)
def app_ad_impression(ad_session_id: str, payload: AppAdEventRequest, member: Member = Depends(require_app_member)) -> dict[str, Any]:
    with SessionLocal() as session:
        item = _app_session(session, ad_session_id, member, payload.session_token)
        prior = session.scalar(select(AppAdEvent).where(AppAdEvent.event_id == payload.event_id))
        if prior:
            if prior.ad_session_id != item.id or prior.event_type != "impression":
                raise HTTPException(status_code=409, detail="Event ID belongs to another operation")
            return {"data": json.loads(prior.result_json or "{}"), "request_id": item.request_id}
        if item.status != "issued": raise HTTPException(status_code=409, detail="Ad session cannot be impressed")
        item.status = "impressed"; item.impressed_at = now()
        result = {"ad_session_id": item.id, "status": item.status}
        session.add(AppAdEvent(event_id=payload.event_id, ad_session_id=item.id, member_id=member.id, event_type="impression", result_json=json.dumps(result)))
        _ad_flow_log(session, item, "impression", detail={"event_id": payload.event_id})
        session.commit(); return {"data": result, "request_id": item.request_id}


@app_api.post("/ads/{ad_session_id}/complete")
def app_ad_complete(ad_session_id: str, payload: AppAdEventRequest, member: Member = Depends(require_app_member)) -> dict[str, Any]:
    with SessionLocal() as session:
        item = _app_session(session, ad_session_id, member, payload.session_token)
        if item.provider.lower() == "taku":
            if item.status == "rewarded":
                _ad_flow_log(session, item, "client_complete", detail={"event_id": payload.event_id, "already_rewarded": True})
                session.commit()
                return {"data": {"ad_session_id": item.id, "status": "rewarded", "rewarded": True, "coin_added": item.reward_coin, "coin_log_id": item.coin_log_id}, "request_id": item.request_id}
            if item.status not in ("issued", "impressed"):
                raise HTTPException(status_code=409, detail="Ad session has already been closed")
            # Client completion is advisory; only the verified provider callback settles.
            _ad_flow_log(session, item, "client_complete", status="pending", detail={"event_id": payload.event_id, "awaiting": "taku_reward"})
            session.commit()
            return {"data": {"ad_session_id": item.id, "status": "pending_verification", "rewarded": False,
                              "message": "奖励确认中"}, "request_id": item.request_id}
        prior = session.scalar(select(AppAdEvent).where(AppAdEvent.event_id == payload.event_id))
        if prior:
            if prior.ad_session_id != item.id or prior.event_type != "complete":
                raise HTTPException(status_code=409, detail="Event ID belongs to another operation")
            return {"data": json.loads(prior.result_json or "{}"), "request_id": item.request_id}
        if item.status not in ("issued", "impressed"): raise HTTPException(status_code=409, detail="Ad session has already been closed")
        stored = get_or_404(session, Member, member.id, "User")
        before = float(stored.coin or 0); reward = float(item.reward_coin or 0)
        stored.coin = before + reward; stored.coin_user = float(stored.coin_user or 0) + reward
        item.status = "rewarded"; item.completed_at = now()
        log = CoinLog(user_id=stored.id, agent_id=stored.agent_id, game_id=item.game_id, coin_before=before, coin=reward, coin_after=stored.coin, type=1, remark="APP ad reward")
        session.add(log); session.flush(); item.coin_log_id = log.id
        game = session.get(Game, item.game_id)
        session.add(AdRecord(
            user_id=stored.id, user_account=stored.username, parent_id=stored.parent_id,
            agent_id=stored.agent_id, game_id=item.game_id, game_name=game.name if game else "",
            receive_name=stored.receive_name or "", coin=reward, estimate_income=reward,
            ad_network_platform_name=item.provider.upper(), ad_type="激励", status="成功",
            watched_at=item.completed_at, ad_code=item.ad_unit_id, request_id=item.request_id,
        ))
        result = {"ad_session_id": item.id, "status": "rewarded", "rewarded": True, "coin_added": reward, "coin_balance": stored.coin, "coin_log_id": log.id}
        session.add(AppAdEvent(event_id=payload.event_id, ad_session_id=item.id, member_id=member.id, event_type="complete", result_json=json.dumps(result)))
        _ad_flow_log(session, item, "client_complete", detail={"event_id": payload.event_id, "coin_added": reward})
        session.commit(); return {"data": result, "request_id": item.request_id}


@app_api.post("/ads/{ad_session_id}/fail", status_code=202)
def app_ad_fail(ad_session_id: str, payload: AppAdEventRequest, member: Member = Depends(require_app_member)) -> dict[str, Any]:
    with SessionLocal() as session:
        item = _app_session(session, ad_session_id, member, payload.session_token)
        prior = session.scalar(select(AppAdEvent).where(AppAdEvent.event_id == payload.event_id))
        if prior:
            if prior.ad_session_id != item.id or prior.event_type != "fail":
                raise HTTPException(status_code=409, detail="Event ID belongs to another operation")
            return {"data": json.loads(prior.result_json or "{}"), "request_id": item.request_id}
        if item.status in ("rewarded", "failed"): raise HTTPException(status_code=409, detail="Ad session has already been closed")
        item.status = "failed"; item.failed_at = now()
        result = {"ad_session_id": item.id, "status": "failed", "rewarded": False}
        session.add(AppAdEvent(event_id=payload.event_id, ad_session_id=item.id, member_id=member.id, event_type="fail", result_json=json.dumps(result)))
        _ad_flow_log(session, item, "client_fail", status="failed", detail={"event_id": payload.event_id})
        session.commit(); return {"data": result, "request_id": item.request_id}


@app_api.get("/ads/history")
def app_ad_history(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), game_id: int | None = Query(None, ge=1), member: Member = Depends(require_app_member)) -> dict[str, Any]:
    with SessionLocal() as session:
        conditions = [AppAdSession.member_id == member.id]
        if game_id: conditions.append(AppAdSession.game_id == game_id)
        stmt = select(AppAdSession).where(*conditions).order_by(AppAdSession.created_at.desc()).offset(offset).limit(limit)
        items = session.scalars(stmt).all(); total = session.scalar(select(func.count()).select_from(AppAdSession).where(*conditions)) or 0
        return {"data": {"items": [{"id": x.id, "game_id": x.game_id, "placement": x.placement, "ad_type": x.ad_type, "provider": x.provider, "status": x.status, "coin_added": x.reward_coin if x.status == "rewarded" else 0, "request_id": x.request_id, "watched_at": stringify(x.completed_at or x.impressed_at), "created_at": stringify(x.created_at)} for x in items], "total": int(total), "limit": limit, "offset": offset}, "request_id": secrets.token_urlsafe(12)}


def _taku_extra_data(item: AppAdSession) -> str:
    message = f"taku:{item.id}:{item.member_id}:{item.ad_unit_id}"
    proof = hmac.new(JWT_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
    return item.id + "." + proof


@app.get("/api/callbacks/taku/reward")
def taku_reward_callback(
    request: Request,
    user_id: str = "",
    trans_id: str = "",
    reward_amount: str = "",
    reward_name: str = "",
    placement_id: str = "",
    extra_data: str = "",
    network_firm_id: str = "",
    adsource_id: str = "",
    scenario_id: str = "",
    sign: str = "",
    ilrd: str = "",
    is_test: str = "",
) -> Response:
    """Taku S2S reward callback. Taku calls this endpoint with GET parameters."""
    def reply(code: int, message: str = "ok") -> Response:
        return Response(status_code=code, content=message, headers={"Cache-Control": "no-store"})
    if is_test == "1":
        # Console probes contain literal placeholders and never write anything.
        return reply(200)
    required = ("user_id", "trans_id", "placement_id", "adsource_id", "reward_amount", "reward_name", "extra_data", "sign")
    if any(not request.query_params.get(k) for k in required) or any(len(request.query_params.getlist(k)) != 1 for k in required):
        return reply(602, "missing or duplicate parameters")
    if any(len(request.query_params.getlist(k)) != 1 for k in request.query_params):
        return reply(602, "duplicate parameters")
    if len(trans_id) > 128 or len(placement_id) > 128 or any(len(v) > 512 for k, v in request.query_params.items() if k != "ilrd") or len(ilrd) > 65536:
        return reply(602, "parameters too long")
    # Resolve the server-issued session before selecting the game's private key.
    with SessionLocal() as lookup:
        target = lookup.get(AppAdSession, extra_data.split(".", 1)[0])
        if target is None:
            return reply(602, "ad session not found")
        _ad_flow_log(lookup, target, "callback_received", detail={"trans_id": trans_id, "placement_id": placement_id, "adsource_id": adsource_id})
        lookup.commit()
        callback_enabled, callback_key = taku_credentials(lookup, target.game_id)
        if not callback_enabled or not callback_key:
            return reply(503, "TAKU callback is not configured for this game")
    parts = [f"trans_id={trans_id}", f"placement_id={placement_id}", f"adsource_id={adsource_id}", f"reward_amount={reward_amount}", f"reward_name={reward_name}", f"sec_key={callback_key}"]
    if "ilrd" in request.query_params:
        parts.append(f"ilrd={ilrd}")
    expected = hashlib.md5("&".join(parts).encode("utf-8")).hexdigest()
    if not hmac.compare_digest(expected.lower().encode(), sign.lower().encode()):
        with SessionLocal() as audit:
            target = audit.get(AppAdSession, extra_data.split(".", 1)[0])
            if target:
                _ad_flow_log(audit, target, "callback_rejected", status="failed", error_code="invalid_sign", detail={"trans_id": trans_id})
                audit.commit()
        return reply(601, "invalid sign")
    try:
        member_id = int(user_id)
    except (TypeError, ValueError):
        return reply(602, "invalid user_id")
    try:
        # TAKU sends the provider ECPM in reward_amount. Convert ECPM to
        # member coins using the configured rule: ECPM / 1000.
        ecpm_value = float(reward_amount)
        if not math.isfinite(ecpm_value) or ecpm_value < 0:
            raise ValueError
        reward_from_ecpm = ecpm_value / 1000.0
    except (TypeError, ValueError):
        return reply(602, "invalid reward_amount")
    with SessionLocal() as session:
        # SQLite has no row locks. Acquire its write reservation before reading;
        # PostgreSQL serializes a user's settlements with a row lock instead.
        if session.bind.dialect.name == "sqlite":
            session.execute(text("BEGIN IMMEDIATE"))
        item = session.scalar(select(Member).where(Member.id == member_id).with_for_update())
        if item is None:
            return reply(602, "user not found")
        session_id = extra_data.split(".", 1)[0]
        ad_session = session.scalar(select(AppAdSession).where(AppAdSession.id == session_id).with_for_update())
        if (ad_session is None or ad_session.member_id != item.id or ad_session.provider.lower() != "taku"
                or ad_session.ad_unit_id != placement_id or not hmac.compare_digest(_taku_extra_data(ad_session).encode(), extra_data.encode())):
            return reply(602, "invalid ad session binding")
        _ad_flow_log(session, ad_session, "callback_verified", detail={"trans_id": trans_id, "placement_id": placement_id})
        if taku_credentials(session, ad_session.game_id) != (True, callback_key):
            return reply(503, "TAKU configuration changed; retry")
        event_key = "taku:" + hashlib.sha256(trans_id.encode()).hexdigest()
        prior = session.scalar(select(AppAdEvent).where(AppAdEvent.event_id == event_key))
        if prior:
            return reply(200) if prior.ad_session_id == ad_session.id and prior.event_type == "taku_reward" else reply(602, "transaction already used")
        if ad_session.status == "rewarded" or ad_session.coin_log_id is not None:
            return reply(602, "session already rewarded by another transaction")
        # Provider delivery can arrive after the short client session timeout.
        if ad_session.status not in ("issued", "impressed", "expired") or ad_session.created_at.replace(tzinfo=UTC) < now() - timedelta(hours=24):
            return reply(602, "session is closed or too old")
        before = float(item.coin or 0); reward = reward_from_ecpm
        item.coin = before + reward; item.coin_user = float(item.coin_user or 0) + reward
        ad_session.status = "rewarded"; ad_session.completed_at = now()
        log = CoinLog(user_id=item.id, agent_id=item.agent_id, game_id=ad_session.game_id, coin_before=before, coin=reward, coin_after=item.coin, type=1, remark="TAKU ad reward")
        session.add(log)
        # Reserve the globally unique provider transaction in the same transaction.
        session.add(AppAdEvent(event_id=event_key, ad_session_id=ad_session.id, member_id=item.id, event_type="taku_reward", result_json=json.dumps({"trans_id": trans_id, "placement_id": placement_id, "network_firm_id": network_firm_id, "adsource_id": adsource_id, "scenario_id": scenario_id, "reward_amount": reward_amount, "reward_name": reward_name, "ilrd": ilrd}, ensure_ascii=False)))
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            prior = session.scalar(select(AppAdEvent).where(AppAdEvent.event_id == event_key))
            if prior is None:
                raise
            return reply(200) if prior.ad_session_id == session_id and prior.event_type == "taku_reward" else reply(602, "transaction already used")
        ad_session.coin_log_id = log.id
        game = session.get(Game, ad_session.game_id)
        session.add(AdRecord(user_id=item.id, user_account=item.username, parent_id=item.parent_id, agent_id=item.agent_id, game_id=ad_session.game_id, game_name=game.name if game else "", receive_name=item.receive_name or "", ecpm=ecpm_value, coin=reward, estimate_income=reward, ad_network_platform_name="TAKU", ad_type="激励", status="成功", watched_at=ad_session.completed_at, ad_code=placement_id, request_id=ad_session.request_id, trans_id=trans_id))
        _ad_flow_log(session, ad_session, "reward_granted", detail={"coin_added": reward, "coin_log_id": log.id}, trans_id=trans_id)
        session.commit()
    return reply(200)


@app_api.post("/subsidies", status_code=201)
def app_create_subsidy(payload: AppSubsidyCreate, member: Member = Depends(require_app_member)) -> dict[str, Any]:
    for picture in payload.pics:
        match = re.fullmatch(r"/api/member-images/([a-f0-9]{48}\.png)", picture)
        if match is None or not (image_directory() / match.group(1)).is_file():
            raise HTTPException(status_code=422, detail="请先上传申请图片，再提交返回的图片地址")
    with SessionLocal() as session:
        # SQLite ignores FOR UPDATE; reserve its write transaction before
        # checking pending applications. PostgreSQL uses the member row lock.
        if session.get_bind().dialect.name == "sqlite":
            session.execute(text("BEGIN IMMEDIATE"))
        stored = session.scalar(select(Member).where(Member.id == member.id).with_for_update())
        if stored is None or stored.status != 1:
            raise _app_auth_error("Account is disabled or does not exist")
        game = session.get(Game, payload.game_id or stored.game_id)
        if game is None or game.status != 1:
            raise HTTPException(status_code=404, detail="游戏不可用")
        if game.agent_id != stored.agent_id:
            raise HTTPException(status_code=403, detail="游戏不属于当前用户主体")
        agent = session.get(Agent, stored.agent_id)
        if agent is None or agent.status != 1:
            raise HTTPException(status_code=403, detail="当前用户主体不可用")
        if session.scalar(select(subsidy_campaigns.SubsidyCampaign.id).where(
            subsidy_campaigns.SubsidyCampaign.game_id == game.id)) is not None:
            raise HTTPException(409, '该游戏已配置补贴活动，请通过活动申请接口提交')
        pending = session.scalar(select(Subsidy).where(
            Subsidy.user_id == stored.id, Subsidy.game_id == game.id, Subsidy.status == 0,
        ).order_by(Subsidy.id.desc()).limit(1))
        if pending is not None:
            raise HTTPException(status_code=409, detail="该游戏已有待审核的补贴申请，请勿重复提交")
        item = Subsidy(user_id=stored.id, agent_id=stored.agent_id, game_id=game.id,
                       tx_price=float(payload.tx_price), price=0, pics=",".join(payload.pics),
                       receive_name=payload.receive_name, receive_tel=payload.receive_tel, sub_msg="", status=0)
        session.add(item)
        session.commit()
        session.refresh(item)
        return {"data": _app_subsidy_payload(item), "request_id": secrets.token_urlsafe(12)}


@app_api.post("/subsidies/images", status_code=201)
async def app_upload_subsidy_image(request: Request, member: Member = Depends(require_app_member)) -> dict[str, Any]:
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="图片不能超过 2MB")
        content.extend(chunk)
    url = await run_in_threadpool(save_image, bytes(content))
    return {"data": {"url": url}, "request_id": secrets.token_urlsafe(12)}


@app_api.get("/subsidies")
def app_list_subsidies(
    game_id: int | None = Query(None, ge=1),
    status: int | None = Query(None, ge=0, le=2),
    limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
    member: Member = Depends(require_app_member),
) -> dict[str, Any]:
    with SessionLocal() as session:
        conditions = [Subsidy.user_id == member.id]
        if game_id is not None:
            conditions.append(Subsidy.game_id == game_id)
        if status is not None:
            conditions.append(Subsidy.status == status)
        rows = session.scalars(select(Subsidy).where(*conditions).order_by(Subsidy.id.desc()).offset(offset).limit(limit)).all()
        total = session.scalar(select(func.count()).select_from(Subsidy).where(*conditions)) or 0
        return {"data": {"items": [_app_subsidy_payload(x) for x in rows], "total": int(total),
                         "limit": limit, "offset": offset}, "request_id": secrets.token_urlsafe(12)}


@app_api.get("/subsidies/{subsidy_id}")
def app_get_subsidy(subsidy_id: int, member: Member = Depends(require_app_member)) -> dict[str, Any]:
    with SessionLocal() as session:
        item = session.scalar(select(Subsidy).where(Subsidy.id == subsidy_id, Subsidy.user_id == member.id))
        if item is None:
            raise HTTPException(status_code=404, detail="补贴申请不存在")
        return {"data": _app_subsidy_payload(item), "request_id": secrets.token_urlsafe(12)}


@app_api.get("/wallet")
def app_wallet(member: Member = Depends(require_app_member)) -> dict[str, Any]:
    with SessionLocal() as session:
        item = get_or_404(session, Member, member.id, "User")
        return {"data": {"coin": item.coin, "freeze_coin": item.freeze_coin, "coin_user": item.coin_user, "updated_at": stringify(item.updated_at)}, "request_id": secrets.token_urlsafe(12)}


@app_api.get("/wallet/coin-logs")
def app_coin_logs(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), member: Member = Depends(require_app_member)) -> dict[str, Any]:
    with SessionLocal() as session:
        conditions = [CoinLog.user_id == member.id]
        items = session.scalars(select(CoinLog).where(*conditions).order_by(CoinLog.created_at.desc()).offset(offset).limit(limit)).all()
        total = session.scalar(select(func.count()).select_from(CoinLog).where(*conditions)) or 0
        return {"data": {"items": [{"id": x.id, "type": x.type, "coin_before": x.coin_before, "coin": x.coin, "coin_after": x.coin_after, "remark": x.remark, "source_id": 0, "created_at": stringify(x.created_at)} for x in items], "total": int(total), "limit": limit, "offset": offset}, "request_id": secrets.token_urlsafe(12)}


api = APIRouter(prefix="/api/v1", dependencies=[Depends(require_admin)])


@api.post('/member-images', status_code=201)
async def upload_member_image(request: Request, admin: AdminUser = Depends(allow_roles('operator'))) -> dict[str, str]:
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, '图片不能超过 2MB')
        content.extend(chunk)
    return {'url': await run_in_threadpool(save_image, bytes(content))}


@app.get('/api/member-images/{filename}')
def read_member_image(filename: str) -> FileResponse:
    # Public avatar URLs contain random names and only serve normalized images.
    if not re.fullmatch(r'[0-9a-f]{48}\.png', filename):
        raise HTTPException(404, '图片不存在')
    path = image_directory() / filename
    if not path.is_file():
        raise HTTPException(404, '图片不存在')
    return FileResponse(path, media_type='image/png', headers={'X-Content-Type-Options': 'nosniff'})


@app.get("/", response_class=FileResponse)
def read_index() -> FileResponse:
    return FileResponse(PUBLIC_DIR / "index.html")


@app.get("/styles.css")
def read_styles() -> FileResponse:
    return FileResponse(PUBLIC_DIR / "styles.css", media_type="text/css")


@app.get("/app.js")
def read_app_js() -> FileResponse:
    return FileResponse(PUBLIC_DIR / "app.js", media_type="application/javascript")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/login")
def login(payload: LoginRequest, request: Request) -> dict[str, Any]:
    username = payload.username.strip()
    with SessionLocal() as session:
        admin = session.scalar(select(AdminUser).where(AdminUser.username == username))
        if admin is None or admin.status != 1 or not verify_password(
            payload.password, admin.password_hash, admin.password_salt
        ):
            raise authentication_error("账号或密码错误")
        admin.last_login_at = now()
        session.add(AdminOperation(admin_id=admin.id, title="登录", path=request.url.path, ip=request.client.host if request.client else ""))
        session.commit()
        session.refresh(admin)
        return {
            "access_token": create_access_token(admin),
            "token_type": "bearer",
            "expires_in": JWT_EXPIRE_MINUTES * 60,
            "user": serialize_admin(admin),
        }


@app.get("/api/auth/me")
def current_admin(admin: AdminUser = Depends(require_admin)) -> dict[str, Any]:
    return serialize_admin(admin)


@app.post('/api/auth/avatar', status_code=201)
async def upload_profile_avatar(request: Request, admin: AdminUser = Depends(require_admin)) -> dict[str, str]:
    return await upload_member_image(request, admin)


@app.patch("/api/auth/me")
def update_profile(payload: ProfileUpdate, request: Request, admin: AdminUser = Depends(require_admin)) -> dict[str, Any]:
    name = payload.display_name.strip()
    if not name or len(name) > 128:
        raise HTTPException(status_code=422, detail="昵称长度必须为 1 至 128 个字符")
    if payload.password and len(payload.password) < 10:
        raise HTTPException(status_code=422, detail="新密码至少需要 10 个字符")
    if payload.avatar is not None and payload.avatar != '/assets/img/avatar.png':
        match = re.fullmatch(r'/api/member-images/([0-9a-f]{48}\.png)', payload.avatar)
        if not match or not (image_directory() / match[1]).is_file():
            raise HTTPException(status_code=422, detail="请先上传有效的头像图片")
    with SessionLocal() as session:
        stored = get_or_404(session, AdminUser, admin.id, "管理员")
        stored.display_name = name
        if payload.avatar is not None:
            stored.avatar = payload.avatar
        if payload.password:
            stored.password_hash, stored.password_salt = hash_password(payload.password)
        session.add(AdminOperation(admin_id=admin.id, title="修改个人资料", path=request.url.path, ip=request.client.host if request.client else ""))
        session.commit()
        session.refresh(stored)
        return serialize_admin(stored)


@app.get("/api/auth/operations")
def profile_operations(q: str = "", limit: int = Query(10, ge=1, le=200), offset: int = Query(0, ge=0),
                       sort: Literal['id', 'created_at'] = 'id', order: Literal['asc', 'desc'] = 'desc',
                       admin: AdminUser = Depends(require_admin)) -> dict[str, Any]:
    with SessionLocal() as session:
        return list_payload(session, AdminOperation, ["title", "path", "ip"],
                            lambda item: serialize(item, ["id", "title", "path", "ip", "created_at"]),
                            q, limit, offset, [AdminOperation.admin_id == admin.id],
                            [getattr(getattr(AdminOperation, sort), order)(), AdminOperation.id.desc()])


def tutorial_catalog() -> list[dict[str, Any]]:
    try:
        data = json.loads((PUBLIC_DIR / 'target-book.json').read_text(encoding='utf-8-sig'))
        if not isinstance(data, dict): raise ValueError('Invalid catalog')
        rows = data.get('items', data.get('rows'))
        if not isinstance(rows, list): raise ValueError('Invalid catalog')
        result = []
        for row in rows:
            item = {'id': int(row['id']), 'name': str(row['name']), 'content': str(row.get('content', ''))}
            for source, target in [('create_time', 'created_at'), ('update_time', 'updated_at')]:
                value = row.get(source)
                item[target] = datetime.fromtimestamp(float(value), UTC) if value else None
            result.append(item)
        if len({row['id'] for row in result}) != len(result): raise ValueError('Duplicate tutorial')
        return result
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        raise HTTPException(503, '教程加载失败，请稍后重试') from None


@api.get('/tutorials')
def list_tutorials(limit: int = Query(10, ge=1, le=200), offset: int = Query(0, ge=0),
                   sort: Literal['id', 'created_at', 'updated_at'] = 'id', order: Literal['asc', 'desc'] = 'desc',
                   created_from: datetime | None = None, created_to: datetime | None = None,
                   updated_from: datetime | None = None, updated_to: datetime | None = None) -> dict[str, Any]:
    rows = tutorial_catalog()
    for key, start, end in [('created_at', created_from, created_to), ('updated_at', updated_from, updated_to)]:
        start = (start.replace(tzinfo=UTC) if start.tzinfo is None else start.astimezone(UTC)) if start else None
        end = (end.replace(tzinfo=UTC) if end.tzinfo is None else end.astimezone(UTC)) if end else None
        if start and end and start > end: raise HTTPException(422, '时间范围无效')
        if start: rows = [row for row in rows if row[key] is not None and row[key] >= start]
        if end: rows = [row for row in rows if row[key] is not None and row[key] <= end]
    rows.sort(key=lambda row: row['id'], reverse=True)
    rows.sort(key=lambda row: (row[sort] is not None, row[sort]), reverse=order == 'desc')
    return {'total': len(rows), 'items': [{key: value for key, value in row.items() if key != 'content'} for row in rows[offset:offset+limit]], 'limit': limit, 'offset': offset}


@api.get('/tutorials/{tutorial_id}')
def tutorial_detail(tutorial_id: int) -> dict[str, Any]:
    row = next((row for row in tutorial_catalog() if row['id'] == tutorial_id), None)
    if row is None: raise HTTPException(404, '教程不存在')
    return row


@app.post("/api/auth/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(payload: PasswordChangeRequest, admin: AdminUser = Depends(require_admin)) -> Response:
    if len(payload.new_password) < 10:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="新密码至少需要 10 个字符")
    with SessionLocal() as session:
        stored_admin = get_or_404(session, AdminUser, admin.id, "管理员")
        if not verify_password(payload.current_password, stored_admin.password_hash, stored_admin.password_salt):
            raise authentication_error("瑜版挸澧犵€靛棛鐖滈柨娆掝嚖")
        stored_admin.password_hash, stored_admin.password_salt = hash_password(payload.new_password)
        session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)


@api.get("/dashboard/summary")
def dashboard_summary() -> dict[str, Any]:
    today = (now().astimezone(UTC) + timedelta(hours=8)).date()
    lower = datetime.combine(today, datetime.min.time(), tzinfo=UTC) - timedelta(hours=8)
    upper = lower + timedelta(days=1)
    with SessionLocal() as session:
        today_login = 0
        for value in session.scalars(select(Member.last_login_time).where(Member.last_login_time != '')):
            try:
                timestamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=UTC)
                if lower <= timestamp.astimezone(UTC) < upper:
                    today_login += 1
            except (ValueError, TypeError):
                continue
        return {
            "today_new": session.scalar(select(func.count(Member.id)).where(Member.created_at >= lower, Member.created_at < upper)) or 0,
            "today_login": today_login,
            "agents": session.scalar(select(func.count()).select_from(Agent)) or 0,
            "games": session.scalar(select(func.count()).select_from(Game)) or 0,
            "members": session.scalar(select(func.count()).select_from(Member)) or 0,
            "pending_withdrawals": session.scalar(select(func.count()).select_from(Withdrawal).where(Withdrawal.status == 0)) or 0,
            "pending_subsidies": session.scalar(select(func.count()).select_from(Subsidy).where(Subsidy.status == 0)) or 0,
            "risk_rows": session.scalar(select(func.count()).select_from(RiskRecord)) or 0,
        }


@api.get("/dashboard/registrations")
def dashboard_registrations(days: int = Query(7, ge=1, le=31)) -> dict[str, Any]:
    """Return daily member registration counts for the dashboard trend chart."""
    end = (now().astimezone(UTC) + timedelta(hours=8)).date()
    start = end - timedelta(days=days - 1)
    lower = datetime.combine(start, datetime.min.time(), tzinfo=UTC) - timedelta(hours=8)
    upper = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=UTC) - timedelta(hours=8)
    with SessionLocal() as session:
        rows = session.scalars(select(Member.created_at).where(Member.created_at >= lower, Member.created_at < upper))
        counts: dict[str, int] = {}
        for timestamp in rows:
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
            day = (timestamp.astimezone(UTC) + timedelta(hours=8)).date().isoformat()
            counts[day] = counts.get(day, 0) + 1
        items = [{"date": (start + timedelta(days=index)).isoformat(), "count": counts.get((start + timedelta(days=index)).isoformat(), 0)} for index in range(days)]
        return {"days": days, "items": items}


@api.get("/dashboard/activity")
def dashboard_activity() -> dict[str, Any]:
    with SessionLocal() as session:
        game = session.get(Game, 237)
        member = session.get(Member, 695016)
        withdrawal = session.scalar(select(Withdrawal).order_by(Withdrawal.id.desc()))
        pending_withdrawals = session.scalar(
            select(func.count()).select_from(Withdrawal).where(Withdrawal.status == 0)
        ) or 0

        rows = []
        if game is not None:
            rows.append(
                {
                    "subject": game.name,
                    "module": "game",
                    "action": "更新游戏",
                    "status": "完成",
                    "time": stringify(game.updated_at),
                }
            )
        if member is not None:
            rows.append(
                {
                    "subject": member.name,
                    "module": "member",
                    "action": "新增会员",
                    "status": "完成",
                    "time": member.last_login_time or stringify(member.updated_at),
                }
            )
        if withdrawal is not None:
            rows.append(
                {
                    "subject": "閹绘劗骞囬梼鐔峰灙",
                    "module": "withdrawal",
                    "action": f"閺?{pending_withdrawals} 閺夆€崇窡鐎光剝鐗崇拋鏉跨秿" if pending_withdrawals else "瑜版挸澧犻弮鐘茬窡鐎光€冲礋",
                    "status": "待处理" if pending_withdrawals else "清空",
                    "time": stringify(withdrawal.updated_at),
                }
            )

        return {"items": rows}


@api.get("/member-filter-options/{kind}")
def member_filter_options(
    kind: Literal["games", "agents"],
    q: str = "",
    agent_id: int | None = None,
    id: int | None = None,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Minimal lookup data for member filters; explicit scope is never inferred from names."""
    model = Game if kind == "games" else Agent
    conditions = []
    if q:
        conditions.append(model.name.contains(q, autoescape=True))
    if id is not None:
        conditions.append(model.id == id)
    if agent_id is not None:
        conditions.append(Game.agent_id == agent_id if kind == "games" else Agent.id == agent_id)
    with SessionLocal() as session:
        total = session.scalar(select(func.count()).select_from(model).where(*conditions))
        rows = session.execute(select(model.id, model.name).where(*conditions).order_by(model.name.asc(), model.id.asc()).limit(limit).offset(offset)).all()
        return {"items": [{"id": row.id, "name": row.name} for row in rows], "total": total, "limit": limit, "offset": offset}


@api.get("/agents")
def list_agents(
    q: str | None = None,
    name: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    updated_from: datetime | None = None,
    updated_to: datetime | None = None,
    sort: Literal["id", "created_at", "updated_at"] = "id",
    order: Literal["asc", "desc"] = "desc",
    parent_id: int | None = None,
    status_filter: int | None = Query(None, alias="status"),
    game_ad_status: int | None = None,
    ht_status: int | None = None,
    is_gx: int | None = None,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_admin),
) -> dict[str, Any]:
    conditions: list[Any] = []
    if name:
        conditions.append(Agent.name.contains(name, autoescape=True))
    for column,start,end in [(Agent.created_at,created_from,created_to),(Agent.updated_at,updated_from,updated_to)]:
        if start is not None and start.tzinfo: start=start.astimezone(UTC).replace(tzinfo=None)
        if end is not None and end.tzinfo: end=end.astimezone(UTC).replace(tzinfo=None)
        if start is not None and end is not None and start>end:
            raise HTTPException(status_code=422,detail="时间范围无效")
        if start is not None: conditions.append(column>=start)
        if end is not None: conditions.append(column<=end)
    if parent_id is not None:
        conditions.append(Agent.parent_id == parent_id)
    if status_filter is not None:
        conditions.append(Agent.status == status_filter)
    if game_ad_status is not None:
        conditions.append(Agent.game_ad_status == game_ad_status)
    if ht_status is not None:
        conditions.append(Agent.ht_status == ht_status)
    if is_gx is not None:
        conditions.append(Agent.is_gx == is_gx)
    with SessionLocal() as session:
        payload = list_payload(session, Agent, ["name", "user_name", "security_key"], serialize_agent, q, limit, offset, conditions, [getattr(getattr(Agent,sort),order)(),Agent.id.desc()])
        can_manage = admin.role in ("superadmin", "operator")
        payload["permissions"] = {key: can_manage for key in ("create", "edit", "delete", "oss", "batch_status")}
        payload["permissions"]["dashboard"] = True
        payload["summary"] = summarize_flags(
            session,
            Agent,
            conditions,
            [
                ("enabled", Agent.status == 1),
                ("ad_enabled", Agent.game_ad_status == 1),
                ("ht_enabled", Agent.ht_status == 1),
                ("gx_enabled", Agent.is_gx == 1),
            ],
        )
        return payload


@api.get("/games")
def list_games(
    q: str | None = None,
    game_key: str | None = None,
    is_landscape: int | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    name: str | None = None,
    game_type: int | None = None,
    game_ad_status: int | None = None,
    sort: Literal["id", "created_at", "game_lottery_num"] = "id",
    order: Literal["asc", "desc"] = "desc",
    agent_id: int | None = None,
    status_filter: int | None = Query(None, alias="status"),
    ad_status: int | None = None,
    lucky_enable: int | None = None,
    is_mobile: int | None = None,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    conditions: list[Any] = []
    if name:conditions.append(Game.name.contains(name,autoescape=True))
    if game_key:conditions.append(Game.game_key.contains(game_key,autoescape=True))
    if is_landscape is not None:conditions.append(Game.is_landscape==is_landscape)
    if created_from is not None and created_from.tzinfo:created_from=created_from.astimezone(UTC).replace(tzinfo=None)
    if created_to is not None and created_to.tzinfo:created_to=created_to.astimezone(UTC).replace(tzinfo=None)
    if created_from is not None and created_to is not None and created_from>created_to:
        raise HTTPException(status_code=422,detail="时间范围无效")
    if created_from is not None:conditions.append(Game.created_at>=created_from)
    if created_to is not None:conditions.append(Game.created_at<=created_to)
    if game_type is not None:conditions.append(Game.game_type==game_type)
    if game_ad_status is not None:conditions.append(Game.game_ad_status==game_ad_status)
    if agent_id is not None:
        conditions.append(Game.agent_id == agent_id)
    if status_filter is not None:
        conditions.append(Game.status == status_filter)
    if ad_status is not None:
        conditions.append(Game.ad_status == ad_status)
    if lucky_enable is not None:
        conditions.append(Game.lucky_enable == lucky_enable)
    if is_mobile is not None:
        conditions.append(Game.is_mobile == is_mobile)
    with SessionLocal() as session:
        payload = list_payload(session, Game, ["name", "game_key", "game_url", "other_url"], serialize_game, q, limit, offset, conditions, [getattr(getattr(Game,sort),order)(),Game.id.desc()])
        payload["summary"] = summarize_flags(
            session,
            Game,
            conditions,
            [
                ("enabled", Game.status == 1),
                ("ad_enabled", Game.ad_status == 1),
                ("lucky_enabled", Game.lucky_enable == 1),
                ("mobile_enabled", Game.is_mobile == 1),
            ],
        )
        return payload


@api.get("/members")
def list_members(
    is_true: int | None = Query(None, ge=0, le=1),
    game_addiction_enable: int | None = Query(None, ge=0, le=1),
    game_addiction_time: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort: Literal["id", "coin_user", "coin", "freeze_coin", "created_at", "game_addiction_time"] = "id",
    order: Literal["asc", "desc"] = "desc",
    ip: str | None = None,
    create_time: str | None = None,
    q: str | None = None,
    member_id: int | None = Query(None, alias="id"),
    agent_name: str | None = None,
    username: str | None = None,
    name: str | None = None,
    parent_id: int | None = None,
    game_name: str | None = None,
    game_name_contains: str | None = None,
    agent_id: int | None = None,
    game_id: int | None = None,
    status_filter: int | None = Query(None, alias="status"),
    is_white: int | None = Query(None, alias="is_white"),
    exchange_enable: int | None = Query(None, alias="exchange_enable"),
    vip: int | None = None,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_admin),
) -> dict[str, Any]:
    conditions: list[Any] = []
    if created_from is not None and created_from.tzinfo:
        created_from = created_from.astimezone(UTC).replace(tzinfo=None)
    if created_to is not None and created_to.tzinfo:
        created_to = created_to.astimezone(UTC).replace(tzinfo=None)
    if created_from is not None and created_to is not None and created_from > created_to:
        raise HTTPException(status_code=422, detail="创建时间范围无效")
    if created_from is not None: conditions.append(Member.created_at >= created_from)
    if created_to is not None: conditions.append(Member.created_at <= created_to)
    if is_true is not None: conditions.append(Member.is_true == is_true)
    if game_addiction_enable is not None: conditions.append(Member.game_addiction_enable == game_addiction_enable)
    if game_addiction_time:
        try:
            parts = game_addiction_time.split(' - ')
            if len(parts) != 2 or any(not re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', part) for part in parts):
                raise ValueError
            start, end = [datetime.strptime(part, '%Y-%m-%d %H:%M:%S') for part in parts]
            if start > end:
                raise ValueError
        except ValueError:
            raise HTTPException(status_code=422, detail='达标时间范围无效')
        # Achievement timestamps are stored as wall-clock strings, without UTC conversion.
        conditions.extend([Member.game_addiction_time >= parts[0], Member.game_addiction_time <= parts[1]])
    if member_id is not None: conditions.append(Member.id == member_id)
    if ip:
        conditions.append(Member.ip == ip)
    if create_time:
        try:
            dates = create_time.split(" - ")
            if len(dates) > 2:
                raise ValueError
            date_only = all(len(value) == 10 for value in dates)
            if date_only:
                start = datetime.combine(date.fromisoformat(dates[0]), datetime.min.time())
                end = datetime.combine(date.fromisoformat(dates[-1]), datetime.min.time()) + timedelta(days=1)
                if end <= start:
                    raise ValueError
            else:
                # The reference calendar emits Beijing wall-clock seconds.
                if len(dates) != 2 or any(len(value) != 19 for value in dates):
                    raise ValueError
                start, end = [datetime.strptime(value, "%Y-%m-%d %H:%M:%S") for value in dates]
                if end < start:
                    raise ValueError
            # Both calendar and date-only input are Beijing time; storage is UTC.
            start -= timedelta(hours=8)
            end -= timedelta(hours=8)
        except (ValueError, OverflowError):
            raise HTTPException(status_code=422, detail="创建时间请使用日期或 YYYY-MM-DD HH:mm:ss - YYYY-MM-DD HH:mm:ss 范围")
        conditions.extend([Member.created_at >= start, Member.created_at < end if date_only else Member.created_at <= end])
    if agent_name:
        conditions.append(Member.agent_id.in_(select(Agent.id).where(Agent.name.contains(agent_name, autoescape=True))))
    if username:
        conditions.append(Member.username.contains(username, autoescape=True))
    if name:
        conditions.append(Member.name.contains(name, autoescape=True))
    if game_name:
        conditions.append(Member.game_id.in_(select(Game.id).where(Game.name == game_name)))
    if game_name_contains:
        conditions.append(Member.game_id.in_(select(Game.id).where(Game.name.contains(game_name_contains, autoescape=True))))
    if parent_id is not None: conditions.append(Member.parent_id == parent_id)
    if agent_id is not None:
        conditions.append(Member.agent_id == agent_id)
    if game_id is not None:
        conditions.append(Member.game_id == game_id)
    if status_filter is not None:
        conditions.append(Member.status == status_filter)
    if is_white is not None:
        conditions.append(Member.is_white == is_white)
    if exchange_enable is not None:
        conditions.append(Member.exchange_enable == exchange_enable)
    if vip is not None:
        conditions.append(Member.vip == vip)
    with SessionLocal() as session:
        payload = list_payload(
            session,
            Member,
            ["username", "name", "device_id", "real_name", "card_no", "last_login_ip"],
            serialize_member,
            q,
            limit,
            offset,
            conditions,
            [getattr(getattr(Member, sort), order)(), Member.id.desc()],
        )
        # Resolve display names from related records, never substitute numeric IDs.
        rows = payload.get("items", [])
        game_ids = {row["game_id"] for row in rows if row.get("game_id")}
        agent_ids = {row["agent_id"] for row in rows if row.get("agent_id")}
        parent_ids = {row["parent_id"] for row in rows if row.get("parent_id")}
        games = dict(session.execute(select(Game.id, Game.name).where(Game.id.in_(game_ids))).all())
        agents = dict(session.execute(select(Agent.id, Agent.name).where(Agent.id.in_(agent_ids))).all())
        parents = dict(session.execute(select(Member.id, Member.name).where(Member.id.in_(parent_ids))).all())
        parent_accounts = dict(session.execute(select(Member.id, Member.username).where(Member.id.in_(parent_ids))).all())
        for row in payload.get("items", []):
            row["parent_name"] = parents.get(row.get("parent_id"), "")
            row["parent_username"] = parent_accounts.get(row.get("parent_id"), "")
            row["game_name"] = games.get(row.get("game_id"), "")
            row["agent_name"] = agents.get(row.get("agent_id"), "")
        payload["summary"] = summarize_flags(
            session,
            Member,
            conditions,
            [
                ("enabled", Member.status == 1),
                ("white", Member.is_white == 1),
                ("exchange_enabled", Member.exchange_enable == 1),
                ("vip_enabled", Member.vip > 0),
            ],
        )
        if admin.username == "18532306918":
            payload["permissions"] = {
                "create": False,
                "edit": True,
                "delete": False,
                "batch_status": False,
                "rebind": True,
                "behavior": True,
                "coin": True,
            }
        else:
            can_manage = admin.role in ("superadmin", "operator")
            payload["permissions"] = {
                "create": can_manage,
                "edit": can_manage,
                "delete": admin.role == "superadmin",
                "batch_status": can_manage,
                "rebind": can_manage,
                "behavior": True,
                "coin": can_manage,
            }
        return payload


@api.get("/ads/flow-logs")
def list_ad_flow_logs(
    ad_session_id: str | None = None,
    request_id: str | None = None,
    event_type: str | None = None,
    status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Inspect the complete APP rewarded-ad lifecycle as an admin."""
    with SessionLocal() as session:
        conditions = []
        if ad_session_id: conditions.append(AdFlowLog.ad_session_id == ad_session_id)
        if request_id: conditions.append(AdFlowLog.request_id == request_id)
        if event_type: conditions.append(AdFlowLog.event_type == event_type)
        if status: conditions.append(AdFlowLog.status == status)
        stmt = select(AdFlowLog).where(*conditions).order_by(AdFlowLog.created_at.desc()).offset(offset).limit(limit)
        items = session.scalars(stmt).all()
        total = session.scalar(select(func.count()).select_from(AdFlowLog).where(*conditions)) or 0
        return {"items": [{"id": x.id, "ad_session_id": x.ad_session_id, "request_id": x.request_id,
                           "member_id": x.member_id, "game_id": x.game_id, "event_type": x.event_type,
                           "status": x.status, "provider": x.provider, "trans_id": x.trans_id,
                           "error_code": x.error_code, "detail": json.loads(x.detail_json or "{}"),
                           "created_at": stringify(x.created_at)} for x in items],
                "total": int(total), "limit": limit, "offset": offset}


@api.get("/ads")
def list_ads(
    q: str | None = None,
    sort: Literal['id', 'pre_ecpm', 'estimate_income', 'ad_network_platform_name', 'create_time', 'request_id'] = 'id',
    order: Literal['asc', 'desc'] = 'desc',
    parent_id: int | None = None,
    member_id: int | None = Query(None, alias="user_id"),
    game_name: str | None = None,
    agent_name: str | None = None,
    game_id: int | None = None,
    agent_id: int | None = None,
    coin_min: float | None = None,
    coin_max: float | None = None,
    estimate_income_min: float | None = None,
    estimate_income_max: float | None = None,
    ad_platform: str | None = None,
    ad_type_filter: str | None = Query(None, alias="ad_type"),
    sub_ad_type_filter: str | None = Query(None, alias="sub_ad_type"),
    is_fu_filter: int | None = Query(None, alias="is_fu"),
    fu_type_filter: int | None = Query(None, alias="fu_type"),
    is_look_filter: int | None = Query(None, alias="is_look"),
    ad_group_filter: str | None = Query(None, alias="ad_group"),
    status_filter: str | None = Query(None, alias="status"),
    watched_from: datetime | None = None,
    watched_to: datetime | None = None,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    conditions = build_ad_conditions(
        parent_id=parent_id,
        member_id=member_id,
        game_name=game_name,
        agent_name=agent_name,
        game_id=game_id,
        agent_id=agent_id,
        coin_min=coin_min,
        coin_max=coin_max,
        estimate_income_min=estimate_income_min,
        estimate_income_max=estimate_income_max,
        ad_platform=ad_platform,
        ad_type_filter=ad_type_filter,
        sub_ad_type_filter=sub_ad_type_filter,
        is_fu_filter=is_fu_filter,
        fu_type_filter=fu_type_filter,
        is_look_filter=is_look_filter,
        ad_group_filter=ad_group_filter,
        status_filter=status_filter,
        watched_from=watched_from,
        watched_to=watched_to,
    )

    with SessionLocal() as session:
        sort_column = {'id': AdRecord.id, 'pre_ecpm': AdRecord.ecpm,
                       'estimate_income': AdRecord.estimate_income,
                       'ad_network_platform_name': AdRecord.ad_network_platform_name,
                       'create_time': func.coalesce(AdRecord.watched_at, AdRecord.created_at),
                       'request_id': AdRecord.request_id}[sort]
        payload = list_payload(session, AdRecord, AD_SEARCH_FIELDS, serialize_ad, q, limit, offset, conditions,
                               [getattr(sort_column, order)(), AdRecord.id.desc()])
        games = dict(session.execute(select(Game.id, Game.name).where(Game.id.in_({row['game_id'] for row in payload['items']}))).all())
        agents = dict(session.execute(select(Agent.id, Agent.name).where(Agent.id.in_({row['agent_id'] for row in payload['items']}))).all())
        for row in payload['items']:
            row['game_name'] = games.get(row['game_id'], row['game_name'])
            row['agent_name'] = agents.get(row['agent_id'], '')
        summary_stmt = filter_stmt(AdRecord, q, AD_SEARCH_FIELDS)
        if conditions:
            summary_stmt = summary_stmt.where(*conditions)
        summary_stmt = summary_stmt.with_only_columns(
            func.coalesce(func.sum(AdRecord.ecpm), 0.0).label("ecpm"),
            func.coalesce(func.sum(AdRecord.estimate_income), 0.0).label("coin"),
        )
        summary = session.execute(summary_stmt).one()
        payload["summary"] = {
            "ecpm": round(float(summary.ecpm or 0.0), 4),
            "coin": round(float(summary.coin or 0.0), 2),
            "withdrawn": 0.0,
            "pending_withdrawal": 0.0,
            "money1": round(float(summary.ecpm or 0.0), 4),
            "money2": round(float(summary.coin or 0.0), 2),
            "tixian1": 0.0,
            "tixian2": 0.0,
        }
        return payload


@api.get("/ads/statistics")
def ad_statistics(
    q: str | None = None,
    parent_id: int | None = None,
    member_id: int | None = Query(None, alias="user_id"),
    game_id: int | None = None,
    agent_id: int | None = None,
    coin_min: float | None = None,
    coin_max: float | None = None,
    estimate_income_min: float | None = None,
    estimate_income_max: float | None = None,
    ad_platform: str | None = None,
    ad_type_filter: str | None = Query(None, alias="ad_type"),
    sub_ad_type_filter: str | None = Query(None, alias="sub_ad_type"),
    is_fu_filter: int | None = Query(None, alias="is_fu"),
    fu_type_filter: int | None = Query(None, alias="fu_type"),
    is_look_filter: int | None = Query(None, alias="is_look"),
    ad_group_filter: str | None = Query(None, alias="ad_group"),
    status_filter: str | None = Query(None, alias="status"),
    watched_from: datetime | None = None,
    watched_to: datetime | None = None,
    group_by: str = Query("day"),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    if group_by not in AD_STATS_GROUP_LABELS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="统计维度无效")

    conditions = build_ad_conditions(
        parent_id=parent_id,
        member_id=member_id,
        game_id=game_id,
        agent_id=agent_id,
        coin_min=coin_min,
        coin_max=coin_max,
        estimate_income_min=estimate_income_min,
        estimate_income_max=estimate_income_max,
        ad_platform=ad_platform,
        ad_type_filter=ad_type_filter,
        sub_ad_type_filter=sub_ad_type_filter,
        is_fu_filter=is_fu_filter,
        fu_type_filter=fu_type_filter,
        is_look_filter=is_look_filter,
        ad_group_filter=ad_group_filter,
        status_filter=status_filter,
        watched_from=watched_from,
        watched_to=watched_to,
    )

    dimension_expr: Any
    label_expr: Any
    order_expr: Any
    needs_agent_join = False
    if group_by == "day":
        dimension_expr = func.date(AdRecord.watched_at)
        label_expr = dimension_expr
        order_expr = dimension_expr.asc()
    elif group_by == "ad_group":
        dimension_expr = ad_group_sql_expression()
        label_expr = dimension_expr
        order_expr = dimension_expr.asc()
    elif group_by == "game":
        dimension_expr = AdRecord.game_id
        label_expr = func.max(AdRecord.game_name)
        order_expr = func.count(AdRecord.id).desc()
    else:
        dimension_expr = AdRecord.agent_id
        label_expr = func.max(Agent.name)
        order_expr = func.count(AdRecord.id).desc()
        needs_agent_join = True

    with SessionLocal() as session:
        summary_stmt = apply_ad_filters(select(*ad_stats_columns()), q, conditions)
        summary = session.execute(summary_stmt).one()

        stats_stmt = select(
            dimension_expr.label("dimension_key"),
            label_expr.label("dimension_label"),
            *ad_stats_columns(),
        )
        if needs_agent_join:
            stats_stmt = stats_stmt.select_from(AdRecord).outerjoin(Agent, Agent.id == AdRecord.agent_id)
        stats_stmt = apply_ad_filters(stats_stmt, q, conditions)
        stats_stmt = stats_stmt.group_by(dimension_expr).order_by(order_expr).limit(limit)
        rows = session.execute(stats_stmt).all()

        return {
            "group_by": group_by,
            "group_label": AD_STATS_GROUP_LABELS[group_by],
            "summary": ad_stats_summary(summary),
            "items": [serialize_ad_stats_row(row, group_by) for row in rows],
            "limit": limit,
        }


@api.post("/ads/import")
async def import_ads(request: Request, admin: AdminUser = Depends(allow_roles("operator"))) -> dict[str, Any]:
    raw_rows = parse_ad_import_rows(await request.body())
    seen_request_ids: set[str] = set()
    valid_rows: list[tuple[int, dict[str, Any]]] = []
    errors: list[dict[str, Any]] = []

    for index, raw_row in enumerate(raw_rows, start=2):
        payload, row_errors = normalize_ad_import_row(raw_row, index, seen_request_ids)
        if row_errors:
            error = ad_import_error(index, row_errors)
            error["request_id"] = next((str(value or "").strip() for key, value in raw_row.items()
                                        if key is not None and AD_IMPORT_FIELD_ALIASES.get(key.strip().lstrip("\ufeff")) == "request_id"), "")
            error["raw_data"] = json.dumps(raw_row, ensure_ascii=False)
            errors.append(error)
            continue
        if payload is not None:
            valid_rows.append((index, payload))

    request_ids = [payload["request_id"] for _row_number, payload in valid_rows]
    file_name = unquote(request.headers.get("x-file-name", "")).strip() or "未命名.csv"
    with SessionLocal() as session:
        batch = AdImportBatch(
            file_name=file_name[:255],
            operator_id=admin.id,
            operator_name=(admin.display_name or admin.username)[:128],
            total=len(raw_rows),
            status="处理中",
        )
        session.add(batch)
        session.flush()

        existing_ids = set()
        if request_ids:
            existing_ids = set(session.execute(select(AdRecord.request_id).where(AdRecord.request_id.in_(request_ids))).scalars().all())

        insert_rows = []
        for row_number, payload in valid_rows:
            if payload["request_id"] in existing_ids:
                error = ad_import_error(row_number, ["request_id 已存在"])
                error["request_id"] = payload["request_id"]
                error["raw_data"] = json.dumps(payload, ensure_ascii=False, default=str)
                errors.append(error)
                continue
            insert_rows.append(AdRecord(**payload))

        if insert_rows:
            session.add_all(insert_rows)

        error_rows = [
            AdImportError(
                batch_id=batch.id,
                row_number=int(error.get("row") or 0),
                request_id=str(error.get("request_id") or "")[:128],
                        message="; ".join(error.get("errors") or [])[:255],
                raw_data=str(error.get("raw_data") or ""),
            )
            for error in errors
        ]
        if error_rows:
            session.add_all(error_rows)

        batch.accepted = len(insert_rows)
        batch.rejected = len(errors)
        batch.status = "完成" if batch.rejected == 0 else ("部分失败" if batch.accepted else "失败")
        session.commit()
        batch_id = batch.id

    return {
        "batch_id": batch_id,
        "total": len(raw_rows),
        "accepted": len(insert_rows),
        "rejected": len(errors),
        "errors": errors[:50],
    }


@api.get("/ads/imports")
def list_ad_imports(q: str | None = None, limit: int = Query(20, ge=1, le=200), offset: int = Query(0, ge=0)) -> dict[str, Any]:
    with SessionLocal() as session:
        return list_payload(
            session,
            AdImportBatch,
            ["file_name", "operator_name", "status"],
            serialize_ad_import_batch,
            q,
            limit,
            offset,
        )


@api.get("/ads/imports/{batch_id}/errors")
def list_ad_import_errors(
    batch_id: int,
    q: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    with SessionLocal() as session:
        batch = get_or_404(session, AdImportBatch, batch_id, "导入批次")
        stmt = select(AdImportError).where(AdImportError.batch_id == batch_id)
        if q:
            stmt = stmt.where(
                or_(
                    AdImportError.request_id.ilike(f"%{q}%"),
                    AdImportError.message.ilike(f"%{q}%"),
                    AdImportError.raw_data.ilike(f"%{q}%"),
                )
            )
        total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = session.execute(stmt.order_by(AdImportError.row_number.asc()).offset(offset).limit(limit)).scalars().all()
        return {
            "batch": serialize_ad_import_batch(batch),
            "total": total,
            "items": [serialize_ad_import_error(row) for row in rows],
            "limit": limit,
            "offset": offset,
        }


@api.get("/ads/alerts")
def list_ad_alerts(
    q: str | None = None,
    alert_type: str | None = Query(None, alias="alert_type"),
    severity: str | None = Query(None, alias="severity"),
    source_type: str | None = Query(None, alias="source_type"),
    ad_group_filter: str | None = Query(None, alias="ad_group"),
    watched_from: datetime | None = None,
    watched_to: datetime | None = None,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    alerts: list[dict[str, Any]]
    with SessionLocal() as session:
        alerts = build_ad_alerts(
            session,
            q=q,
            ad_group_filter=ad_group_filter,
            watched_from=watched_from,
            watched_to=watched_to,
        )

    filtered = [
        alert
        for alert in alerts
        if alert_matches_filters(
            alert,
            alert_type_filter=alert_type,
            severity_filter=severity,
            source_type_filter=source_type,
            ad_group_filter=ad_group_filter,
            watched_from=watched_from,
            watched_to=watched_to,
        )
    ]
    summary_payload = summarize_ad_alerts(filtered)
    paged_items = [serialize_ad_alert_item(item) for item in filtered[offset : offset + limit]]
    return {
        "total": len(filtered),
        "items": paged_items,
        "summary": summary_payload["summary"],
        "type_breakdown": summary_payload["type_breakdown"],
        "source_breakdown": summary_payload["source_breakdown"],
        "limit": limit,
        "offset": offset,
    }


@api.get("/ads/export")
def export_ads(
    q: str | None = None,
    parent_id: int | None = None,
    member_id: int | None = Query(None, alias="user_id"),
    game_name: str | None = None,
    agent_name: str | None = None,
    game_id: int | None = None,
    agent_id: int | None = None,
    coin_min: float | None = None,
    coin_max: float | None = None,
    estimate_income_min: float | None = None,
    estimate_income_max: float | None = None,
    ad_platform: str | None = None,
    ad_type_filter: str | None = Query(None, alias="ad_type"),
    sub_ad_type_filter: str | None = Query(None, alias="sub_ad_type"),
    is_fu_filter: int | None = Query(None, alias="is_fu"),
    fu_type_filter: int | None = Query(None, alias="fu_type"),
    is_look_filter: int | None = Query(None, alias="is_look"),
    ad_group_filter: str | None = Query(None, alias="ad_group"),
    status_filter: str | None = Query(None, alias="status"),
    watched_from: datetime | None = None,
    watched_to: datetime | None = None,
    limit: int = Query(5000, ge=1, le=50000),
    offset: int = Query(0, ge=0),
) -> Response:
    conditions = build_ad_conditions(
        parent_id=parent_id,
        member_id=member_id,
        game_name=game_name,
        agent_name=agent_name,
        game_id=game_id,
        agent_id=agent_id,
        coin_min=coin_min,
        coin_max=coin_max,
        estimate_income_min=estimate_income_min,
        estimate_income_max=estimate_income_max,
        ad_platform=ad_platform,
        ad_type_filter=ad_type_filter,
        sub_ad_type_filter=sub_ad_type_filter,
        is_fu_filter=is_fu_filter,
        fu_type_filter=fu_type_filter,
        is_look_filter=is_look_filter,
        ad_group_filter=ad_group_filter,
        status_filter=status_filter,
        watched_from=watched_from,
        watched_to=watched_to,
    )
    with SessionLocal() as session:
        stmt = filter_stmt(AdRecord, q, AD_SEARCH_FIELDS)
        if conditions:
            stmt = stmt.where(*conditions)
        rows = session.execute(stmt.order_by(AdRecord.id.desc()).offset(offset).limit(limit)).scalars().all()
        return export_ads_csv(rows)


def enrich_review_members(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload["items"]
    members = {member.id: member for member in session.scalars(select(Member).where(Member.id.in_({row["user_id"] for row in rows})))}
    parents = {parent.id: parent for parent in session.scalars(select(Member).where(Member.id.in_({member.parent_id for member in members.values()})))}
    games = dict(session.execute(select(Game.id, Game.name).where(Game.id.in_({row["game_id"] for row in rows}))).all())
    agents = dict(session.execute(select(Agent.id, Agent.name).where(Agent.id.in_({row["agent_id"] for row in rows}))).all())
    for row in rows:
        member = members.get(row["user_id"])
        parent = parents.get(member.parent_id) if member else None
        row.update(username=member.username if member else "", vip=member.vip if member else None,
                   is_true=member.is_true if member else None,
                   parent_id=member.parent_id if member else None, parent_username=parent.username if parent else "",
                   name=member.name if member else "", agent_name=agents.get(row["agent_id"], ""),
                   parent_name=parent.name if parent else "", game_name=games.get(row["game_id"], ""))
    return payload


def review_conditions(model, user_id, username, name, vip, parent_id, game_id, agent_id, created_from, created_to, updated_from, updated_to):
    conditions = []
    for field, value in [(model.user_id, user_id), (model.game_id, game_id), (model.agent_id, agent_id)]:
        if value is not None: conditions.append(field == value)
    members = []
    if username: members.append(Member.username.contains(username, autoescape=True))
    if name: members.append(Member.name.contains(name, autoescape=True))
    if vip is not None: members.append(Member.vip == vip)
    if parent_id is not None: members.append(Member.parent_id == parent_id)
    if members: conditions.append(model.user_id.in_(select(Member.id).where(*members)))
    for column, start, end in [(model.created_at, created_from, created_to), (model.updated_at, updated_from, updated_to)]:
        if start is not None and start.tzinfo: start = start.astimezone(UTC).replace(tzinfo=None)
        if end is not None and end.tzinfo: end = end.astimezone(UTC).replace(tzinfo=None)
        if start is not None and end is not None and start > end:
            raise HTTPException(status_code=422, detail="时间范围无效")
        if start is not None: conditions.append(column >= start)
        if end is not None: conditions.append(column <= end)
    return conditions


@api.get("/withdrawals")
def list_withdrawals(
    q: str | None = None,
    good_name: str | None = None,
    sort: Literal["id", "exchange_value", "created_at", "updated_at"] = "id",
    order: Literal["asc", "desc"] = "desc",
    user_id: int | None = None,
    filter_user_id: int | None = None,
    game_name: str | None = None,
    username: str | None = None,
    name: str | None = None,
    vip: int | None = None,
    parent_id: int | None = None,
    is_true: int | None = Query(None, ge=0, le=1),
    game_id: int | None = None,
    agent_id: int | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    updated_from: datetime | None = None,
    updated_to: datetime | None = None,
    receive_name: str | None = None,
    receive_tel: str | None = None,
    exchange_type: int | None = None,
    plan_status: int | None = None,
    status_filter: int | None = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_admin),
) -> dict[str, Any]:
    with SessionLocal() as session:
        internal_status = 2 if status_filter == 4 else status_filter
        conditions = review_conditions(Withdrawal, user_id, username, name, vip, parent_id, game_id, agent_id, created_from, created_to, updated_from, updated_to)
        conditions.extend(behavior_filter_conditions(Withdrawal, filter_user_id, game_name))
        if is_true is not None:
            conditions.append(Withdrawal.user_id.in_(select(Member.id).where(Member.is_true == is_true)))
        if good_name:
            conditions.append(Withdrawal.good_name.contains(good_name, autoescape=True))
        for field, value in [(Withdrawal.receive_name, receive_name), (Withdrawal.receive_tel, receive_tel), (Withdrawal.exchange_type, exchange_type), (Withdrawal.plan_status, plan_status)]:
            if value is not None: conditions.append(field == value)
        if internal_status is not None: conditions.append(Withdrawal.status == internal_status)
        payload = list_payload(
            session,
            Withdrawal,
            ["receive_name", "receive_tel", "reason", "sub_msg"],
            serialize_withdrawal,
            q,
            limit,
            offset,
            conditions,
            [getattr(getattr(Withdrawal, sort), order)(), Withdrawal.id.desc()],
        )
        enrich_review_members(session, payload)
        base = select(func.coalesce(func.sum(Withdrawal.exchange_value), 0.0)).select_from(Withdrawal)
        # Historical imported values use the reference UI's amount scale.
        # New Alipay orders are counted separately in integer cents.
        base = base.where(~Withdrawal.id.in_(select(payouts.Payout.withdrawal_id)))
        if game_id is not None:
            base = base.where(Withdrawal.game_id == game_id)
        if agent_id is not None:
            base = base.where(Withdrawal.agent_id == agent_id)
        if user_id is not None:
            base = base.where(Withdrawal.user_id == user_id)
        payload["summary"] = {
            "withdrawn": float(session.scalar(base.where(Withdrawal.status == 1)) or 0),
            "pending": float(session.scalar(base.where(Withdrawal.status == 0)) or 0),
            # is_true identifies an internal account, not blacklist membership.
            # Recipient matching and the reference amount basis are unverified.
            # Unknown must not be represented as a fabricated amount, including zero.
            "blacklisted": None,
        }
        payload["summary_unavailable"] = {"blacklisted": "blacklist_source_unverified"}
        payout_base = select(func.coalesce(func.sum(payouts.Payout.amount_cents), 0)).join(
            Withdrawal, Withdrawal.id == payouts.Payout.withdrawal_id)
        for field, value in [('game_id', game_id), ('agent_id', agent_id), ('user_id', user_id)]:
            if value is not None: payout_base = payout_base.where(getattr(Withdrawal, field) == value)
        payload['summary']['alipay_paid_cents'] = int(session.scalar(payout_base.where(payouts.Payout.state == 'succeeded')) or 0)
        payload['summary']['alipay_pending_cents'] = int(session.scalar(payout_base.where(
            payouts.Payout.state.in_(['pending_review', 'queued', 'processing']))) or 0)
        payload["permissions"] = {
            "edit": admin.role in ("superadmin", "reviewer"),
            "review": admin.role in ("superadmin", "reviewer"),
            "row_review": admin.role == "reviewer",
            "transfer": admin.role in ("superadmin", "reviewer"),
            "blacklist": admin.role in ("superadmin", "reviewer"),
        }
        return payload


BLACKLIST_FIELDS = ['id', 'receive_name', 'receive_tel', 'status', 'created_at', 'updated_at']


class WithdrawalBlacklistStatus(BaseModel):
    status: Literal[0, 1]


class WithdrawalBlacklistSource(BaseModel):
    receive_name: str = Field(max_length=64)
    receive_tel: str = Field(max_length=64)


@api.get('/withdrawal-blacklist')
def list_withdrawal_blacklist(receive_name: str | None = None, receive_tel: str | None = None,
                             status_filter: int | None = Query(None, alias='status', ge=0, le=1),
                             created_from: datetime | None = None, created_to: datetime | None = None,
                             updated_from: datetime | None = None, updated_to: datetime | None = None,
                             sort: Literal['id', 'created_at', 'updated_at'] = 'id', order: Literal['asc', 'desc'] = 'desc',
                             limit: int = Query(20, ge=1, le=200), offset: int = Query(0, ge=0)) -> dict[str, Any]:
    conditions = []
    for field, value in [(WithdrawalBlacklist.receive_name, receive_name), (WithdrawalBlacklist.receive_tel, receive_tel),
                         (WithdrawalBlacklist.status, status_filter)]:
        if value is not None: conditions.append(field == value)
    for column, start, end in [(WithdrawalBlacklist.created_at, created_from, created_to),
                               (WithdrawalBlacklist.updated_at, updated_from, updated_to)]:
        if start is not None and start.tzinfo: start = start.astimezone(UTC).replace(tzinfo=None)
        if end is not None and end.tzinfo: end = end.astimezone(UTC).replace(tzinfo=None)
        if start is not None and end is not None and start > end:
            raise HTTPException(status_code=422, detail='时间范围无效')
        if start is not None: conditions.append(column >= start)
        if end is not None: conditions.append(column <= end)
    with SessionLocal() as session:
        return list_payload(session, WithdrawalBlacklist, [], lambda row: serialize(row, BLACKLIST_FIELDS), None,
                            limit, offset, conditions, [getattr(getattr(WithdrawalBlacklist, sort), order)(), WithdrawalBlacklist.id.desc()])


@api.patch('/withdrawal-blacklist/{entry_id}')
def update_withdrawal_blacklist(entry_id: int, payload: WithdrawalBlacklistStatus, request: Request,
                               admin: AdminUser = Depends(allow_roles('reviewer', 'risk'))) -> dict[str, Any]:
    with SessionLocal() as session:
        item = get_or_404(session, WithdrawalBlacklist, entry_id, '提现黑名单')
        if item.status != payload.status:
            item.status = payload.status
            session.add(AdminOperation(admin_id=admin.id, title=f'{"启用" if item.status else "禁用"}提现黑名单（{entry_id}）',
                                       path=request.url.path, ip=request.client.host if request.client else ''))
            session.commit()
        return serialize(item, BLACKLIST_FIELDS)


@api.post('/withdrawals/{withdrawal_id}/blacklist')
def blacklist_withdrawal(withdrawal_id: int, payload: WithdrawalBlacklistSource, request: Request,
                         admin: AdminUser = Depends(allow_roles('reviewer', 'risk'))) -> dict[str, Any]:
    with SessionLocal() as session:
        source = get_or_404(session, Withdrawal, withdrawal_id, '提现记录')
        if (payload.receive_name, payload.receive_tel) != (source.receive_name, source.receive_tel):
            raise HTTPException(status_code=409, detail='收款信息已变化，请刷新后重试')
        if not (source.receive_name.strip() or source.receive_tel.strip()):
            raise HTTPException(status_code=422, detail='收款信息为空，无法拉黑')
        query = select(WithdrawalBlacklist).where(WithdrawalBlacklist.receive_name == source.receive_name,
                                                WithdrawalBlacklist.receive_tel == source.receive_tel)
        item = session.scalar(query)
        created = False
        if item is None:
            try:
                with session.begin_nested():
                    item = WithdrawalBlacklist(receive_name=source.receive_name, receive_tel=source.receive_tel,
                                               status=1, source_withdrawal_id=source.id)
                    session.add(item)
                    session.flush()
                created = True
            except IntegrityError:
                item = session.scalar(query)
                if item is None: raise
        if created or item.status != 1:
            item.status = 1
            session.add(AdminOperation(admin_id=admin.id, title=f'拉黑提现收款信息（提现 {withdrawal_id}）',
                                       path=request.url.path, ip=request.client.host if request.client else ''))
        session.commit()
        return serialize(item, BLACKLIST_FIELDS)


class WithdrawalBatch(BaseModel):
    ids: list[int]
    reason: str = ""


def require_payment_integration() -> None:
    if not configured_provider().available:
        raise HTTPException(status_code=503, detail="支付渠道尚未接通，未执行转账，提现记录保持原状态")


def _batch_withdrawal_update(ids: list[int], target_status: int | None = None, plan_status: int | None = None, reason: str = "", admin: AdminUser | None = None, allow_reasonless: bool = False) -> dict[str, Any]:
    if plan_status is not None:
        return payouts.batch_transfer(ids, admin, scheduled=plan_status == 2)
    if not ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="至少需要一条提现记录")
    if target_status == 2 and not allow_reasonless and not reason.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="拒绝提现时必须填写原因")
    with SessionLocal() as session:
        payouts.lock(session)
        rows = session.scalars(select(Withdrawal).where(Withdrawal.id.in_(ids)).order_by(Withdrawal.id).with_for_update()).all()
        if len(rows) != len(set(ids)):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="提现记录不存在")
        for item in rows:
            if target_status is not None:
                if item.status != 0:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只能处理申请中的提现记录")
                item.status = target_status
                if target_status == 2:
                    payouts.release_funds(session, item)
                    item.reason = reason.strip()
                if admin:
                    mark_audit(item, admin)
        session.commit()
        return {"updated": len(rows), "items": [serialize_withdrawal(item) for item in rows]}


@api.post("/withdrawals/batch-approve")
def batch_approve_withdrawals(payload: WithdrawalBatch, admin: AdminUser = Depends(allow_roles("reviewer"))) -> dict[str, Any]:
    return _batch_withdrawal_update(payload.ids, target_status=1, admin=admin)


@api.post("/withdrawals/batch-reject")
def batch_reject_withdrawals(payload: WithdrawalBatch, admin: AdminUser = Depends(allow_roles("reviewer"))) -> dict[str, Any]:
    return _batch_withdrawal_update(payload.ids, target_status=2, reason=payload.reason, admin=admin)


@api.post("/withdrawals/batch-refuse")
def batch_refuse_withdrawals(payload: WithdrawalBatch, admin: AdminUser = Depends(allow_roles("reviewer"))) -> dict[str, Any]:
    return _batch_withdrawal_update(payload.ids, target_status=2, admin=admin, allow_reasonless=True)


@api.post("/withdrawals/{withdrawal_id}/refuse")
def refuse_withdrawal(withdrawal_id: int, admin: AdminUser = Depends(allow_roles("reviewer"))) -> dict[str, Any]:
    return _batch_withdrawal_update([withdrawal_id], target_status=2, admin=admin, allow_reasonless=True)["items"][0]


@api.post("/withdrawals/batch-transfer")
def batch_transfer_withdrawals(payload: WithdrawalBatch, admin: AdminUser = Depends(allow_roles("reviewer"))) -> dict[str, Any]:
    return payouts.batch_transfer(payload.ids, admin)


@api.post("/withdrawals/batch-transfer-scheduled")
def batch_transfer_withdrawals_scheduled(payload: WithdrawalBatch, admin: AdminUser = Depends(allow_roles("reviewer"))) -> dict[str, Any]:
    return payouts.batch_transfer(payload.ids, admin, scheduled=True)


@api.get("/subsidies")
def list_subsidies(
    q: str | None = None,
    receive_name: str | None = None,
    receive_tel: str | None = None,
    sort: Literal["id", "tx_price", "price", "created_at", "updated_at"] = "id",
    order: Literal["asc", "desc"] = "desc",
    user_id: int | None = None,
    username: str | None = None,
    name: str | None = None,
    vip: int | None = None,
    parent_id: int | None = None,
    game_id: int | None = None,
    agent_id: int | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    updated_from: datetime | None = None,
    updated_to: datetime | None = None,
    pics: str | None = None,
    status_filter: int | None = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_admin),
) -> dict[str, Any]:
    with SessionLocal() as session:
        internal_status = 2 if status_filter == 4 else status_filter
        conditions = review_conditions(Subsidy, user_id, username, name, vip, parent_id, game_id, agent_id, created_from, created_to, updated_from, updated_to)
        if receive_name is not None: conditions.append(Subsidy.receive_name == receive_name)
        if receive_tel is not None: conditions.append(Subsidy.receive_tel == receive_tel)
        if pics is not None: conditions.append(Subsidy.pics == pics)
        if internal_status is not None: conditions.append(Subsidy.status == internal_status)
        payload = list_payload(session, Subsidy, ["sub_msg", "pics"], serialize_subsidy, q, limit, offset, conditions, [getattr(getattr(Subsidy, sort), order)(), Subsidy.id.desc()])
        summary_stmt = filter_stmt(Subsidy, q, ["sub_msg", "pics"])
        if conditions:
            summary_stmt = summary_stmt.where(*conditions)
        summary_stmt = summary_stmt.with_only_columns(
            func.coalesce(func.sum(case((Subsidy.status == 1, Subsidy.price), else_=0.0)), 0.0).label("paid"),
            func.coalesce(func.sum(case((Subsidy.status == 0, Subsidy.price), else_=0.0)), 0.0).label("pending"),
        )
        summary = session.execute(summary_stmt).one()
        payload["summary"] = {"paid": round(float(summary.paid or 0.0), 2), "pending": round(float(summary.pending or 0.0), 2)}
        payload["permissions"] = {key: admin.role in ("superadmin", "reviewer") for key in ("edit", "delete", "review")}
        return enrich_review_members(session, payload)


class SubsidyBatch(BaseModel):
    ids: list[int]
    message: str = ""


class SubsidyDeleteBatch(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=10000)


def remove_subsidies(ids: list[int], request: Request, admin: AdminUser) -> int:
    unique_ids = set(ids)
    with SessionLocal() as session:
        rows = session.scalars(select(Subsidy).where(Subsidy.id.in_(unique_ids)).with_for_update()).all()
        if len(rows) != len(unique_ids):
            raise HTTPException(status_code=404, detail="补贴记录不存在")
        for row in rows:
            session.add(AdminOperation(admin_id=admin.id, title=f"删除补贴记录（{row.id}）", path=request.url.path,
                                       ip=request.client.host if request.client else ""))
            session.delete(row)
        session.commit()
        return len(rows)


@api.post("/subsidies/batch-delete")
def delete_subsidies(payload: SubsidyDeleteBatch, request: Request,
                     admin: AdminUser = Depends(allow_roles("reviewer"))) -> dict[str, int]:
    if any(item <= 0 for item in payload.ids):
        raise HTTPException(status_code=422, detail="补贴 ID 无效")
    return {"deleted": remove_subsidies(payload.ids, request, admin)}


def _batch_subsidy_update(ids: list[int], target_status: int, message: str, admin: AdminUser, allow_reasonless: bool = False) -> dict[str, Any]:
    if not ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="至少需要一条补贴申请")
    if target_status == 2 and not allow_reasonless and not message.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="拒绝原因不能为空")
    with SessionLocal() as session:
        rows = session.scalars(select(Subsidy).where(Subsidy.id.in_(ids))).all()
        if len(rows) != len(set(ids)):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="补贴申请不存在")
        for item in rows:
            if item.status != 0:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只能处理申请中的补贴")
            item.status = target_status
            if message.strip():
                item.sub_msg = message.strip()
            mark_audit(item, admin)
        session.commit()
        return {"updated": len(rows), "items": [serialize_subsidy(item) for item in rows]}


@api.post("/subsidies/batch-approve")
def batch_approve_subsidies(payload: SubsidyBatch, admin: AdminUser = Depends(allow_roles("reviewer"))) -> dict[str, Any]:
    return _batch_subsidy_update(payload.ids, 1, payload.message, admin)


@api.post("/subsidies/batch-reject")
def batch_reject_subsidies(payload: SubsidyBatch, admin: AdminUser = Depends(allow_roles("reviewer"))) -> dict[str, Any]:
    return _batch_subsidy_update(payload.ids, 2, payload.message, admin)


@api.post("/subsidies/batch-refuse")
def batch_refuse_subsidies(payload: SubsidyBatch, admin: AdminUser = Depends(allow_roles("reviewer"))) -> dict[str, Any]:
    return _batch_subsidy_update(payload.ids, 2, "", admin, allow_reasonless=True)


@api.get("/coin-logs")
def list_coin_logs(
    q: str | None = None,
    username: str | None = None,
    remark: str | None = None,
    agent_name: str | None = None,
    game_name_exact: str | None = None,
    game_ad_status: int | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    user_id: int | None = None,
    filter_user_id: int | None = None,
    game_name: str | None = None,
    agent_id: int | None = None,
    game_id: int | None = None,
    type: int | None = None,
    sort: Literal["id", "coin", "coin_before", "coin_after", "created_at"] = "id",
    order: Literal["asc", "desc"] = "desc",
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    if created_from is not None and created_from.tzinfo:
        created_from = created_from.astimezone(UTC).replace(tzinfo=None)
    if created_to is not None and created_to.tzinfo:
        created_to = created_to.astimezone(UTC).replace(tzinfo=None)
    with SessionLocal() as session:
        conditions: list[Any] = []
        if user_id is not None: conditions.append(CoinLog.user_id == user_id)
        conditions.extend(behavior_filter_conditions(CoinLog, filter_user_id, game_name))
        if game_name_exact is not None:
            conditions.append(CoinLog.game_id.in_(select(Game.id).where(Game.name == game_name_exact)))
        if agent_name:
            conditions.append(CoinLog.agent_id.in_(select(Agent.id).where(Agent.name.contains(agent_name, autoescape=True))))
        if agent_id is not None: conditions.append(CoinLog.agent_id == agent_id)
        if game_id is not None: conditions.append(CoinLog.game_id == game_id)
        if type is not None: conditions.append(CoinLog.type == type)
        if username:
            conditions.append(CoinLog.user_id.in_(select(Member.id).where(Member.username.contains(username, autoescape=True))))
        if remark:
            conditions.append(CoinLog.remark.contains(remark, autoescape=True))
        if game_ad_status is not None:
            conditions.append(CoinLog.agent_id.in_(select(Agent.id).where(Agent.game_ad_status == game_ad_status)))
        if created_from is not None: conditions.append(CoinLog.created_at >= created_from)
        if created_to is not None: conditions.append(CoinLog.created_at <= created_to)
        if created_from is not None and created_to is not None and created_from > created_to:
            raise HTTPException(status_code=422, detail="创建时间范围无效")
        payload = list_payload(session, CoinLog, ["remark"], serialize_coinlog, q, limit, offset, conditions,
                                [getattr(getattr(CoinLog, sort), order)(), CoinLog.id.desc()])
        summary = filter_stmt(CoinLog, q, ["remark"]).where(*conditions).with_only_columns(func.coalesce(func.sum(CoinLog.coin), 0.0))
        payload["summary"] = {"change": float(session.scalar(summary) or 0)}
        if user_id is not None:
            member = session.get(Member, user_id)
            if member is not None and (game_id is None or member.game_id == game_id):
                payload["member_summary"] = {"coin_user": member.coin_user, "coin": member.coin, "freeze_coin": member.freeze_coin}
        rows = payload["items"]
        users = dict(session.execute(select(Member.id, Member.username).where(Member.id.in_({row["user_id"] for row in rows}))).all())
        games = dict(session.execute(select(Game.id, Game.name).where(Game.id.in_({row["game_id"] for row in rows}))).all())
        agents = {item.id:item for item in session.scalars(select(Agent).where(Agent.id.in_({row["agent_id"] for row in rows})))}
        for row in rows:
            agent = agents.get(row["agent_id"])
            row.update(username=users.get(row["user_id"], ""), game_name=games.get(row["game_id"], ""),
                       agent_name=agent.name if agent else "", game_ad_status=agent.game_ad_status if agent else None)
        return payload


@api.get("/risk/history")
def list_risk_history(q: str | None = None, risk_level: str | None = None, action: str | None = None,
                      network_status: int | None = Query(None, ge=0, le=1), tags: str | None = None,
                      sort: Literal["id", "created_at"] = "id", order: Literal["asc", "desc"] = "desc",
                      user_id: str | None = None, member_id: int | None = Query(None, ge=1), username: str | None = None, parent_id: int | None = None,
                      game_id: int | None = None, game_name: str | None = None, agent_id: int | None = None, tagcode: str | None = None,
                      game_name_exact: str | None = None, agent_name: str | None = None,
                      hardware_main_id: str | None = None, ip: str | None = None,
                      created_from: datetime | None = None, created_to: datetime | None = None,
                      limit: int = Query(20, ge=1, le=200), offset: int = Query(0, ge=0)) -> dict[str, Any]:
    if created_from is not None and created_from.tzinfo:
        created_from = created_from.astimezone(UTC).replace(tzinfo=None)
    if created_to is not None and created_to.tzinfo:
        created_to = created_to.astimezone(UTC).replace(tzinfo=None)
    if created_from is not None and created_to is not None and created_from > created_to:
        raise HTTPException(status_code=422, detail="创建时间范围无效")
    with SessionLocal() as session:
        conditions: list[Any] = []
        if risk_level: conditions.append(RiskRecord.risk_level == risk_level)
        if network_status is not None: conditions.append(RiskRecord.network_status == network_status)
        if tags is not None: conditions.append(RiskRecord.tags == tags)
        if action: conditions.append(RiskRecord.action == action)
        if user_id: conditions.append(cast(RiskRecord.user_id, String).contains(user_id, autoescape=True))
        if member_id is not None: conditions.append(RiskRecord.user_id == member_id)
        conditions.extend(behavior_filter_conditions(RiskRecord, None, game_name))
        if game_name_exact is not None:
            conditions.append(RiskRecord.game_id.in_(select(Game.id).where(Game.name == game_name_exact)))
        if agent_name:
            conditions.append(RiskRecord.agent_id.in_(select(Agent.id).where(Agent.name.contains(agent_name, autoescape=True))))
        if username: conditions.append(RiskRecord.user_id.in_(select(Member.id).where(Member.username.contains(username, autoescape=True))))
        if parent_id is not None: conditions.append(RiskRecord.user_id.in_(select(Member.id).where(Member.parent_id == parent_id)))
        if game_id is not None: conditions.append(RiskRecord.game_id == game_id)
        if agent_id is not None: conditions.append(RiskRecord.agent_id == agent_id)
        if tagcode: conditions.append(RiskRecord.tagcode.contains(tagcode, autoescape=True))
        if hardware_main_id: conditions.append(RiskRecord.hardware_main_id.contains(hardware_main_id, autoescape=True))
        if ip: conditions.append(RiskRecord.ip == ip)
        if created_from is not None: conditions.append(RiskRecord.created_at >= created_from)
        if created_to is not None: conditions.append(RiskRecord.created_at <= created_to)
        payload = list_payload(session, RiskRecord, ["tagcode", "tags", "hardware_main_id", "ip", "action"], serialize_risk, q, limit, offset, conditions,
                               [getattr(getattr(RiskRecord, sort), order)(), RiskRecord.id.desc()])
        rows = payload["items"]
        users = {member.id:member for member in session.scalars(select(Member).where(Member.id.in_({row["user_id"] for row in rows})))}
        games = dict(session.execute(select(Game.id, Game.name).where(Game.id.in_({row["game_id"] for row in rows}))).all())
        agents = dict(session.execute(select(Agent.id, Agent.name).where(Agent.id.in_({row["agent_id"] for row in rows}))).all())
        for row in rows:
            member = users.get(row["user_id"])
            row.update(username=member.username if member else "", parent_id=member.parent_id if member else None,
                       game_name=games.get(row["game_id"], ""), agent_name=agents.get(row["agent_id"], ""))
        return payload


@api.get("/risk/whitelist")
def list_whitelist(q: str | None = None, username: str | None = None, name: str | None = None,
                   parent_id: int | None = None, game_id: int | None = None, agent_id: int | None = None,
                   game_name: str | None = None, agent_name: str | None = None,
                   sort: Literal['id', 'coin_user', 'coin', 'freeze_coin', 'created_at', 'game_addiction_time'] = 'id',
                   order: Literal['asc', 'desc'] = 'desc',
                   created_from: datetime | None = None, created_to: datetime | None = None,
                   status_filter: int | None = Query(None, alias="status"), limit: int = Query(20, ge=1, le=200), offset: int = Query(0, ge=0),
                   admin: AdminUser = Depends(require_admin)) -> dict[str, Any]:
    return list_members(q=q, username=username, name=name, parent_id=parent_id, game_id=game_id, agent_id=agent_id,
                        game_name=game_name, agent_name=agent_name, sort=sort, order=order,
                        created_from=created_from, created_to=created_to, status_filter=status_filter,
                        is_white=1, is_true=None, game_addiction_enable=None, member_id=None, exchange_enable=None,
                        limit=limit, offset=offset, admin=admin)


@api.get("/risk/devices")
def list_device_risk(q: str | None = None, limit: int = Query(20, ge=1, le=200), offset: int = Query(0, ge=0)) -> dict[str, Any]:
    # A persisted device is not enough to establish the reference risk
    # selection rule. Do not expose device or risk rows as a guessed list.
    raise HTTPException(status_code=503, detail="设备风控名单暂不可用，请稍后重试")


def behavior_filter_conditions(model: type[Base], filter_user_id: int | None, game_name: str | None,
                               exact_game: bool = False) -> list[Any]:
    conditions = []
    if filter_user_id is not None:
        conditions.append(model.user_id == filter_user_id)
    if game_name:
        match = Game.name == game_name if exact_game else Game.name.contains(game_name, autoescape=True)
        conditions.append(model.game_id.in_(select(Game.id).where(match)))
    return conditions


def member_behavior_summary(session: Session, user_id: int, game_id: int | None) -> dict[str, Any] | None:
    member = session.get(Member, user_id)
    if member is None or game_id is not None and member.game_id != game_id:
        return None
    today = (now().astimezone(UTC) + timedelta(hours=8)).date()
    start = datetime.combine(today, datetime.min.time()) - timedelta(hours=8)
    conditions = [LotteryRecord.user_id == user_id, LotteryRecord.created_at >= start,
                  LotteryRecord.created_at < start + timedelta(days=1), LotteryRecord.status == 1]
    if game_id is not None:
        conditions.append(LotteryRecord.game_id == game_id)
    earned, count = session.execute(select(func.coalesce(func.sum(LotteryRecord.lottery_price), 0.0),
                                           func.count()).where(*conditions)).one()
    device = session.get(MemberDevice, user_id)
    device_data = serialize(device, ['device_id','imei','android_version','model','app_version','ip_address',
                                    'sim_info','risk_flag','usb_debugging','rooted','device_id_ban','imei_id_ban']) if device else {
        'device_id': member.last_login_device_id or member.device_id, 'imei': '',
        'device_id_ban': 0, 'imei_id_ban': 0}
    return {'coin': member.coin, 'today_lottery_coin': float(earned),
            'today_average_coin': float(earned) / count if count else 0,
            'total_clicks': device.total_clicks if device else None,
            'today_clicks': device.today_clicks if device and device.counter_date == today else None,
            'today_failed': device.today_failed if device and device.counter_date == today else None,
            'device': device_data}


class MemberDeviceBan(BaseModel):
    target: Literal['device', 'imei']
    banned: bool
    expected_identifier: str = Field(min_length=1, max_length=128)


@api.patch('/members/{member_id}/device-ban')
def update_member_device_ban(member_id: int, payload: MemberDeviceBan, request: Request,
                             admin: AdminUser = Depends(allow_roles('operator', 'risk'))) -> dict[str, Any]:
    with SessionLocal() as session:
        member = get_or_404(session, Member, member_id, '会员')
        device = session.get(MemberDevice, member_id)
        identifier = (device.imei if device else '') if payload.target == 'imei' else (
            device.device_id if device else member.last_login_device_id or member.device_id)
        if not identifier.strip():
            raise HTTPException(status_code=422, detail='设备标识为空')
        if payload.expected_identifier != identifier:
            raise HTTPException(status_code=409, detail='设备信息已变化，请刷新后重试')
        if device is None:
            device = MemberDevice(user_id=member_id, device_id=identifier)
            session.add(device)
        field = 'imei_id_ban' if payload.target == 'imei' else 'device_id_ban'
        changed = int(getattr(device, field) or 0) != int(payload.banned)
        setattr(device, field, int(payload.banned))
        if changed:
            label = 'IMEI' if payload.target == 'imei' else '设备ID'
            action = '封禁' if payload.banned else '解除封禁'
            session.add(AdminOperation(admin_id=admin.id, title=f'{action}{label}（会员 {member_id}）',
                                       path=request.url.path, ip=request.client.host if request.client else ''))
        session.commit()
        return member_behavior_summary(session, member_id, member.game_id)


@api.get('/members/{member_id}/app-usage')
def list_member_app_usage(member_id: int, game_id: int | None = None,
                          limit: int = Query(200, ge=1, le=200), offset: int = Query(0, ge=0)) -> dict[str, Any]:
    with SessionLocal() as session:
        get_or_404(session, Member, member_id, '会员')
        conditions = [MemberAppUsage.user_id == member_id]
        if game_id is not None:
            conditions.append(MemberAppUsage.game_id == game_id)
        return list_payload(session, MemberAppUsage, [],
                            lambda row: serialize(row, ['id','user_id','game_id','app_name','package_name','count',
                                                        'duration_seconds','first_used_at','last_used_at']),
                            None, limit, offset, conditions, [MemberAppUsage.last_used_at.desc(), MemberAppUsage.id.desc()])


@api.get("/lottery-records")
@api.get("/games/{game_id}/lottery-records")
def game_lottery_records(
    game_id: int | None = None,
    user_id: int | None = None,
    filter_user_id: int | None = None,
    game_name: str | None = None,
    username: str | None = None,
    adn_name: str | None = None,
    ip: str | None = None,
    network_status: int | None = Query(None, ge=0, le=1),
    is_white: int | None = Query(None, ge=0, le=1),
    status: int | None = Query(None, ge=0, le=1),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort: Literal["id", "lottery_price", "created_at"] = "id",
    order: Literal["asc", "desc"] = "desc",
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    if created_from is not None and created_from.tzinfo:
        created_from = created_from.astimezone(UTC).replace(tzinfo=None)
    if created_to is not None and created_to.tzinfo:
        created_to = created_to.astimezone(UTC).replace(tzinfo=None)
    if created_from is not None and created_to is not None and created_from > created_to:
        raise HTTPException(status_code=422, detail="时间范围无效")
    with SessionLocal() as session:
        if game_id is not None:
            get_or_404(session, Game, game_id, "游戏")
        conditions = [LotteryRecord.game_id == game_id] if game_id is not None else []
        conditions.extend(behavior_filter_conditions(LotteryRecord, filter_user_id, game_name))
        for field, value in [('user_id', user_id), ('adn_name', adn_name), ('ip', ip),
                             ('network_status', network_status), ('status', status)]:
            if value is not None:
                conditions.append(getattr(LotteryRecord, field) == value)
        if username:
            conditions.append(LotteryRecord.user_id.in_(select(Member.id).where(Member.username.contains(username, autoescape=True))))
        if is_white is not None:
            conditions.append(LotteryRecord.user_id.in_(select(Member.id).where(Member.is_white == is_white)))
        if created_from is not None:
            conditions.append(LotteryRecord.created_at >= created_from)
        if created_to is not None:
            conditions.append(LotteryRecord.created_at <= created_to)
        payload = list_payload(session, LotteryRecord, [],
                               lambda row: serialize(row, list(row.__table__.columns.keys())),
                               None, limit, offset, conditions,
                               [getattr(getattr(LotteryRecord, sort), order)(), LotteryRecord.id.desc()])
        users = {row.id: row for row in session.execute(select(Member.id, Member.username, Member.is_white).where(
            Member.id.in_({row['user_id'] for row in payload['items']}))).all()}
        game_names = dict(session.execute(select(Game.id, Game.name).where(Game.id.in_({row['game_id'] for row in payload['items']}))).all())
        for row in payload['items']:
            member = users.get(row['user_id'])
            row.update(username=member.username if member else '', is_white=member.is_white if member else None,
                       game_name=game_names.get(row['game_id'], ''))
        if user_id is not None:
            payload['member_summary'] = member_behavior_summary(session, user_id, game_id)
        return payload


@api.get("/member-daily-income")
def member_daily_income(user_id: int, game_id: int | None = None,
                        filter_user_id: int | None = None, game_name: str | None = None,
                        date_from: date | None = None, date_to: date | None = None,
                        sort: Literal["id", "coin", "date"] = "date", order: Literal["asc", "desc"] = "asc",
                        limit: int = Query(20, ge=1, le=200), offset: int = Query(0, ge=0)) -> dict[str, Any]:
    """Group stored coin changes by their game and Beijing calendar day."""
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=422, detail="日期范围无效")
    with SessionLocal() as session:
        member = get_or_404(session, Member, user_id, "会员")
        conditions = [CoinLog.user_id == user_id, *behavior_filter_conditions(CoinLog, filter_user_id, game_name)]
        if game_id is not None:
            conditions.append(CoinLog.game_id == game_id)
        if date_from is not None and date_from != date.min:
            conditions.append(CoinLog.created_at >= datetime.combine(date_from, datetime.min.time()) - timedelta(hours=8))
        if date_to is not None:
            # Use the day's final microsecond to also support date.max without overflow.
            conditions.append(CoinLog.created_at <= datetime.combine(date_to, datetime.max.time()) - timedelta(hours=8))
        rows = session.execute(select(CoinLog.id, CoinLog.game_id, CoinLog.created_at, CoinLog.coin).where(*conditions)).all()
        grouped: dict[tuple[int, str], dict[str, Any]] = {}
        for record_id, record_game_id, created_at, coin in rows:
            value = created_at.replace(tzinfo=UTC) if created_at.tzinfo is None else created_at.astimezone(UTC)
            day = (value + timedelta(hours=8)).date().isoformat()
            group = grouped.setdefault((record_game_id, day), {"id": record_id, "user_id": user_id,
                "game_id": record_game_id, "username": member.username, "date": day, "coin": 0.0})
            group['id'] = min(group['id'], record_id)
            group['coin'] += float(coin or 0)
        game_names = dict(session.execute(select(Game.id, Game.name).where(Game.id.in_({key[0] for key in grouped}))).all())
        items = [{**group, "game_name": game_names.get(group['game_id'], '')} for group in grouped.values()]
        items.sort(key=lambda row: (row[sort], row["id"]), reverse=order == "desc")
        return {"total": len(items), "items": items[offset:offset + limit], "limit": limit, "offset": offset}


@api.get("/games/{game_id}/daily-activity")
def game_daily_activity(game_id: int, date_from: date | None = None, date_to: date | None = None,
                        sort: Literal["id", "date", "num"] = "date", order: Literal["asc", "desc"] = "desc",
                        limit: int = Query(20, ge=1, le=200), offset: int = Query(0, ge=0)) -> dict[str, Any]:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=422, detail="日期范围无效")
    with SessionLocal() as session:
        game = get_or_404(session, Game, game_id, "游戏")
        conditions = [DailyActivity.game_id == game_id]
        if date_from is not None: conditions.append(DailyActivity.date >= date_from)
        if date_to is not None: conditions.append(DailyActivity.date <= date_to)
        return list_payload(session, DailyActivity, [], lambda row: {**serialize(row, ['id','game_id','date','num']), 'game_name': game.name}, None,
                            limit, offset, conditions, [getattr(getattr(DailyActivity, sort), order)(), DailyActivity.id.desc()])


@api.get("/games/{game_id}/statistics")
def game_statistics(game_id: int) -> dict[str, Any]:
    """Aggregate only persisted records; no synthetic history is generated."""
    with SessionLocal() as session:
        get_or_404(session, Game, game_id, "游戏")
        total_members = session.scalar(select(func.count()).select_from(Member).where(Member.game_id == game_id)) or 0
        total_income = session.scalar(select(func.coalesce(func.sum(AdRecord.estimate_income), 0.0)).where(AdRecord.game_id == game_id)) or 0
        current = now().astimezone(UTC)
        beijing_day = (current + timedelta(hours=8)).date()
        day_start = datetime.combine(beijing_day, datetime.min.time()) - timedelta(hours=8)
        day_end = day_start + timedelta(days=1)
        today_new = session.scalar(select(func.count()).select_from(Member).where(Member.game_id == game_id, Member.created_at >= day_start, Member.created_at < day_end)) or 0
        login_candidates = session.scalars(select(Member.last_login_time).where(Member.game_id == game_id)).all()
        today_login = 0
        for value in login_candidates:
            try:
                parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
                if parsed.tzinfo is None: parsed = parsed.replace(tzinfo=UTC)
                login_utc = parsed.astimezone(UTC).replace(tzinfo=None)
                if day_start <= login_utc < day_end: today_login += 1
            except (TypeError, ValueError):
                continue
        def income_between(start: datetime, end: datetime) -> float:
            return float(session.scalar(select(func.coalesce(func.sum(AdRecord.estimate_income), 0.0)).where(AdRecord.game_id == game_id, AdRecord.created_at >= start, AdRecord.created_at < end)) or 0)
        year_start = datetime(beijing_day.year, 1, 1) - timedelta(hours=8)
        month_start = datetime(beijing_day.year, beijing_day.month, 1) - timedelta(hours=8)
        previous_month = beijing_day.replace(day=1) - timedelta(days=1)
        previous_month_start = datetime(previous_month.year, previous_month.month, 1) - timedelta(hours=8)
        yesterday_start = day_start - timedelta(days=1)
        activity = session.execute(select(DailyActivity.date, DailyActivity.num).where(DailyActivity.game_id == game_id).order_by(DailyActivity.date.asc())).all()
        # Group in Beijing time on every supported database, including SQLite.
        income_by_day = {}
        coins_by_day = {}
        registrations_by_day = {}
        def beijing_date(value: datetime) -> str:
            utc = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
            return (utc + timedelta(hours=8)).date().isoformat()
        for created_at in session.scalars(select(Member.created_at).where(Member.game_id == game_id)):
            key = beijing_date(created_at)
            registrations_by_day[key] = registrations_by_day.get(key, 0) + 1
        for created_at, amount, coin in session.execute(select(AdRecord.created_at, AdRecord.estimate_income, AdRecord.coin).where(AdRecord.game_id == game_id)):
            day = (created_at.replace(tzinfo=UTC) if created_at.tzinfo is None else created_at.astimezone(UTC)) + timedelta(hours=8)
            key = day.date().isoformat()
            income_by_day[key] = income_by_day.get(key, 0.0) + float(amount or 0)
            coins_by_day[key] = coins_by_day.get(key, 0.0) + float(coin or 0)
        activity_by_day = {str(day): int(num) for day, num in activity}
        metric_dates = sorted(set(income_by_day) | set(activity_by_day))
        # Build regional aggregates from persisted member addresses when available.
        # Keep unknown/free-form addresses out of the ranking instead of inventing a region.
        region_counts: dict[str, int] = {}
        region_coins: dict[str, float] = {}
        member_rows = session.execute(select(Member.address, Member.coin_user).where(Member.game_id == game_id)).all()
        for address, coin_user in member_rows:
            text = str(address or '').strip()
            if not text:
                continue
            match = re.match(r'^(内蒙古|广西|宁夏|新疆|西藏)(?:壮族|回族|维吾尔)?自治区', text)
            if not match:
                match = re.match(r'^(.{2,3}?)(?:省|市|特别行政区)', text)
            region = match.group(1) if match else ''
            if region:
                region_counts[region] = region_counts.get(region, 0) + 1
                region_coins[region] = region_coins.get(region, 0.0) + float(coin_user or 0)
        regions = [{"name": name, "value": count} for name, count in sorted(region_counts.items(), key=lambda item: (-item[1], item[0]))]
        region_names = [row['name'] for row in regions]
        mapdata = [{"name": name, "value": count, "coin": region_coins.get(name, 0.0),
                    "rate": round(count * 100 / total_members, 2) if total_members else 0}
                   for name, count in sorted(region_counts.items())]
        metric_start = beijing_day - timedelta(days=30)
        series_dates = [(metric_start + timedelta(days=index)).isoformat() for index in range(31)]
        metric_series = [{"date": day, "income": income_by_day.get(day, 0.0),
                          "coin": coins_by_day.get(day, 0.0), "activity": activity_by_day.get(day),
                          "clicks": None} for day in series_dates]
        registration_series = [{"date": day, "count": registrations_by_day.get(day, 0)} for day in series_dates]
        latest_record = session.scalar(select(func.max(AdRecord.updated_at)).where(AdRecord.game_id == game_id))
        update_date = beijing_date(latest_record) if latest_record is not None else None
        return {"game_id": game_id, "total_members": int(total_members), "today_new": int(today_new), "today_login": int(today_login),
                "total_income": float(total_income), "year_income": income_between(year_start, day_end), "previous_month_income": income_between(previous_month_start, month_start), "month_income": income_between(month_start, day_end), "yesterday_income": income_between(yesterday_start, day_start),
                "activity": [{"date": str(day), "num": int(num)} for day, num in activity],
                "income": [{"date": day, "amount": income_by_day[day]} for day in sorted(income_by_day)],
                "registrations": [{"date": day, "count": registrations_by_day[day]} for day in sorted(registrations_by_day)],
                "metrics": [{"date": day, "income": income_by_day.get(day, 0), "coin": coins_by_day.get(day, 0),
                             "activity": activity_by_day.get(day), "clicks": None} for day in metric_dates],
                "series_dates": series_dates, "metric_series": metric_series, "registration_series": registration_series,
                "regions": regions, "mapdata": mapdata, "mapdata1": region_names,
                "mapdata2": [region_counts[name] for name in region_names], "update_date": update_date}


@api.get("/login-logs")
@api.get("/games/{game_id}/login-logs")
def game_login_logs(
    game_id: int | None = None,
    user_id: int | None = None,
    filter_user_id: int | None = None,
    game_name: str | None = None,
    username: str | None = None,
    ip: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort: Literal["id", "created_at"] = "id",
    order: Literal["asc", "desc"] = "desc",
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    if created_from is not None and created_from.tzinfo: created_from=created_from.astimezone(UTC).replace(tzinfo=None)
    if created_to is not None and created_to.tzinfo: created_to=created_to.astimezone(UTC).replace(tzinfo=None)
    if created_from is not None and created_to is not None and created_from>created_to:
        raise HTTPException(status_code=422,detail="时间范围无效")
    with SessionLocal() as session:
        if game_id is not None: get_or_404(session,Game,game_id,"游戏")
        conditions=[MemberLoginLog.game_id==game_id] if game_id is not None else []
        conditions.extend(behavior_filter_conditions(MemberLoginLog, filter_user_id, game_name, exact_game=True))
        if user_id is not None: conditions.append(MemberLoginLog.user_id==user_id)
        if username: conditions.append(MemberLoginLog.user_id.in_(select(Member.id).where(Member.username.contains(username,autoescape=True))))
        if ip is not None: conditions.append(MemberLoginLog.ip==ip)
        if created_from is not None: conditions.append(MemberLoginLog.created_at>=created_from)
        if created_to is not None: conditions.append(MemberLoginLog.created_at<=created_to)
        payload=list_payload(session,MemberLoginLog,[],lambda row:serialize(row,list(row.__table__.columns.keys())),None,limit,offset,conditions,[getattr(getattr(MemberLoginLog,sort),order)(),MemberLoginLog.id.desc()])
        users=dict(session.execute(select(Member.id,Member.username).where(Member.id.in_({row['user_id'] for row in payload['items']}))).all())
        game_names=dict(session.execute(select(Game.id,Game.name).where(Game.id.in_({row['game_id'] for row in payload['items']}))).all())
        for row in payload['items']:row.update(username=users.get(row['user_id'],''),game_name=game_names.get(row['game_id'],''))
        return payload


class AgentBatchStatus(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=10000)
    status: Literal[0, 1]


@api.post("/agents/batch-status", dependencies=[Depends(allow_roles("operator"))])
def agent_batch_status(payload: AgentBatchStatus) -> dict[str, int]:
    with SessionLocal() as session:
        ids = set(payload.ids)
        rows = session.scalars(select(Agent).where(Agent.id.in_(ids)).with_for_update()).all()
        if len(rows) != len(ids):
            raise HTTPException(404, "主体不存在")
        for row in rows:
            row.status = payload.status
        session.commit()
        return {"updated": len(rows)}


@api.get("/agents/{agent_id}/oss", dependencies=[Depends(allow_roles("operator"))])
def get_agent_oss(agent_id: int) -> dict[str, str]:
    with SessionLocal() as session:
        item = get_or_404(session, Agent, agent_id, "主体")
        return AgentOssConfig.model_validate(json.loads(item.oss_config or "{}")).model_dump()


class AnalysisBucket(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    minimum: float = Field(ge=0, allow_inf_nan=False)
    maximum: float = Field(ge=0, allow_inf_nan=False)


class AnalysisBuckets(BaseModel):
    coin: list[AnalysisBucket] = Field(default_factory=list, max_length=50)
    success: list[AnalysisBucket] = Field(default_factory=list, max_length=50)
    apps: list[AnalysisBucket] = Field(default_factory=list, max_length=50)


@api.get("/agents/{agent_id}/analysis-settings")
def get_agent_analysis_settings(agent_id: int) -> dict[str, Any]:
    with SessionLocal() as session:
        get_or_404(session, Agent, agent_id, "主体")
        config = session.get(AgentAnalysisConfig, agent_id)
        return AnalysisBuckets.model_validate(json.loads(config.buckets) if config else {}).model_dump()


@api.patch("/agents/{agent_id}/analysis-settings", dependencies=[Depends(allow_roles("operator"))])
def update_agent_analysis_settings(agent_id: int, payload: AnalysisBuckets) -> dict[str, Any]:
    for buckets in (payload.coin, payload.success, payload.apps):
        for index, bucket in enumerate(buckets):
            if not bucket.name.strip() or bucket.minimum > bucket.maximum:
                raise HTTPException(422, "分组名称或范围无效")
            if any(bucket.minimum <= previous.maximum and bucket.maximum >= previous.minimum for previous in buckets[:index]):
                raise HTTPException(422, "分组范围不能重叠")
    with SessionLocal() as session:
        get_or_404(session, Agent, agent_id, "主体")
        config = session.get(AgentAnalysisConfig, agent_id)
        if config is None:
            config = AgentAnalysisConfig(agent_id=agent_id)
            session.add(config)
        merged = AnalysisBuckets.model_validate(json.loads(config.buckets or "{}") if config.buckets else {}).model_dump()
        merged.update(payload.model_dump(exclude_unset=True))
        config.buckets = json.dumps(merged, ensure_ascii=False)
        session.commit()
        return merged


@api.get("/agents/{agent_id}/analysis")
def agent_analysis(
    agent_id: int,
    coin_user_total_min: float | None = Query(None, ge=0, allow_inf_nan=False),
    coin_user_total_max: float | None = Query(None, ge=0, allow_inf_nan=False),
    coin_every_min: float | None = Query(None, ge=0, allow_inf_nan=False),
    coin_every_max: float | None = Query(None, ge=0, allow_inf_nan=False),
    success_percent_min: float | None = Query(None, ge=0, le=100, allow_inf_nan=False),
    success_percent_max: float | None = Query(None, ge=0, le=100, allow_inf_nan=False),
    app_num_min: int | None = Query(None, ge=0),
    app_num_max: int | None = Query(None, ge=0),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort: Literal["id", "coin_user", "coin", "freeze_coin", "created_at"] = "id",
    order: Literal["asc", "desc"] = "desc",
    limit: int = Query(10, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_admin),
) -> dict[str, Any]:
    bounds = {"coin_user_total": (coin_user_total_min, coin_user_total_max), "coin_every": (coin_every_min, coin_every_max),
              "success_percent": (success_percent_min, success_percent_max), "app_num": (app_num_min, app_num_max)}
    if any(lower is not None and upper is not None and lower > upper for lower, upper in bounds.values()):
        raise HTTPException(422, "筛选范围无效")
    if created_from is not None and created_from.tzinfo:
        created_from = created_from.astimezone(UTC).replace(tzinfo=None)
    if created_to is not None and created_to.tzinfo:
        created_to = created_to.astimezone(UTC).replace(tzinfo=None)
    if created_from is not None and created_to is not None and created_from > created_to:
        raise HTTPException(422, "时间范围无效")
    with SessionLocal() as session:
        agent = get_or_404(session, Agent, agent_id, "主体")
        conditions = [Member.agent_id == agent_id, Game.agent_id == agent_id]
        if created_from is not None: conditions.append(LotteryRecord.created_at >= created_from)
        if created_to is not None: conditions.append(LotteryRecord.created_at <= created_to)
        aggregate = select(
            LotteryRecord.user_id.label("user_id"), func.sum(LotteryRecord.lottery_price).label("coin_user_total"),
            func.count().label("lottery_num"), func.sum(case((LotteryRecord.status == 1, 1), else_=0)).label("lottery_num_success"),
            func.count(func.distinct(LotteryRecord.game_id)).label("app_num"),
            func.sum(case((LotteryRecord.network_status == 0, 1), else_=0)).label("internal"),
            func.sum(case((LotteryRecord.network_status == 1, 1), else_=0)).label("public"),
        ).join(Member, Member.id == LotteryRecord.user_id).join(Game, Game.id == LotteryRecord.game_id).where(*conditions).group_by(LotteryRecord.user_id)
        members = []
        fields = ["id", "username", "game_id", "coin_user", "coin_user_month", "coin_user_day", "coin", "freeze_coin", "game_addiction_enable", "is_white", "status", "created_at"]
        aggregates = session.execute(aggregate).mappings().all()
        member_rows = {row.id: row for row in session.scalars(select(Member).where(Member.id.in_([row["user_id"] for row in aggregates])))}
        game_names = dict(session.execute(select(Game.id, Game.name).where(Game.agent_id == agent_id)).all())
        for row in aggregates:
            count = int(row["lottery_num"])
            values = {"coin_user_total": round(float(row["coin_user_total"] or 0), 2), "coin_every": round(float(row["coin_user_total"] or 0) / count, 2),
                      "success_percent": round(int(row["lottery_num_success"]) / count * 100, 2), "app_num": int(row["app_num"])}
            if any((lower is not None and values[key] < lower) or (upper is not None and values[key] > upper) for key, (lower, upper) in bounds.items()):
                continue
            member = member_rows[row["user_id"]]
            members.append({**serialize(member, fields), **values, "game_name": game_names.get(member.game_id, ""), "agent_name": agent.name,
                            "lottery_num": count, "lottery_num_success": int(row["lottery_num_success"]), "internal": int(row["internal"]), "public": int(row["public"])})
        members.sort(key=lambda row: row["id"], reverse=True)
        members.sort(key=lambda row: row[sort], reverse=order == "desc")
        config = session.get(AgentAnalysisConfig, agent_id)
        buckets = AnalysisBuckets.model_validate(json.loads(config.buckets) if config else {})
        def distribution(field: str, groups: list[AnalysisBucket]) -> list[dict[str, Any]]:
            counts = [0] * len(groups); other = 0
            for member in members:
                for index, group in enumerate(groups):
                    if group.minimum <= member[field] <= group.maximum:
                        counts[index] += 1; break
                else: other += 1
            return [{"name": group.name, "value": counts[index]} for index, group in enumerate(groups)] + [{"name": "其它", "value": other}]
        games: dict[str, int] = {}
        for member in members: games[member["game_name"]] = games.get(member["game_name"], 0) + 1
        chart_data = {
            "echart_coin_data": distribution("coin_user_total", buckets.coin),
            "echart_success_percent_data": distribution("success_percent", buckets.success),
            "echart_app_num_data": distribution("app_num", buckets.apps),
            "echart_ip_data": [{"name": "内网", "value": sum(row["internal"] for row in members)}, {"name": "公网", "value": sum(row["public"] for row in members)}],
            "echart_game_data": {"name": list(games), "value": list(games.values())},
            "echart_scatter_data": [[row["coin_user_total"], row["coin_every"]] for row in members],
        }
        return {"agent_id": agent_id, "agent_name": agent.name, "items": members[offset:offset+limit], "total": len(members),
                "limit": limit, "offset": offset, "echart_data": chart_data, "can_configure": admin.role in ("superadmin", "operator")}


@api.get("/agents/{agent_id}/dashboard")
def agent_dashboard(agent_id: int) -> dict[str, Any]:
    today=(now()+timedelta(hours=8)).date()
    start=today-timedelta(days=30)
    lower=datetime.combine(start,datetime.min.time())-timedelta(hours=8)
    upper=datetime.combine(today+timedelta(days=1),datetime.min.time())-timedelta(hours=8)
    with SessionLocal() as session:
        agent=get_or_404(session,Agent,agent_id,"主体")
        registrations=session.scalars(select(Member.created_at).where(Member.agent_id==agent_id,Member.created_at>=lower,Member.created_at<upper)).all()
        counts={}
        for timestamp in registrations:
            day=(timestamp+timedelta(hours=8)).date().isoformat()
            counts[day]=counts.get(day,0)+1
        member_ids=select(Member.id).where(Member.agent_id==agent_id)
        income_rows=session.execute(select(CoinLog.created_at, CoinLog.coin).where(CoinLog.user_id.in_(member_ids), CoinLog.created_at>=lower, CoinLog.created_at<upper)).all()
        incomes={}
        for timestamp, value in income_rows:
            day=(timestamp+timedelta(hours=8)).date().isoformat()
            incomes[day]=incomes.get(day,0.0)+float(value or 0)
        ad_rows=session.execute(select(AdRecord.created_at, AdRecord.estimate_income).where(AdRecord.agent_id==agent_id, AdRecord.created_at>=lower, AdRecord.created_at<upper)).all()
        ad_stats={}
        for timestamp, value in ad_rows:
            day=(timestamp+timedelta(hours=8)).date().isoformat()
            current=ad_stats.setdefault(day, {'clicks':0,'income':0.0}); current['clicks']+=1; current['income']+=float(value or 0)
        login_count=0
        for value in session.scalars(select(Member.last_login_time).where(Member.agent_id==agent_id,Member.last_login_time!='')):
            try:
                timestamp=datetime.fromisoformat(value.replace('Z','+00:00'))
                if timestamp.tzinfo:timestamp=timestamp.astimezone(UTC).replace(tzinfo=None)
                if (timestamp+timedelta(hours=8)).date()==today:login_count+=1
            except (ValueError,TypeError):
                continue
        member_ids=select(Member.id).where(Member.agent_id==agent_id)
        withdrawal_total=session.scalar(select(func.count(Withdrawal.id)).where(Withdrawal.user_id.in_(member_ids))) or 0
        withdrawal_amount=session.scalar(select(func.coalesce(func.sum(Withdrawal.exchange_value),0)).where(Withdrawal.user_id.in_(member_ids))) or 0
        regions_count={}
        for address in session.scalars(select(Member.address).where(Member.agent_id==agent_id)):
            text=str(address or '').strip(); match=re.match(r'^(.{2,3}?)(?:省|市|自治区|特别行政区)',text)
            if match: regions_count[match.group(1)]=regions_count.get(match.group(1),0)+1
        regions=[{"name":k,"value":v} for k,v in sorted(regions_count.items(),key=lambda x:(-x[1],x[0]))]
        return {"agent_id":agent.id,"agent_name":agent.name,"today_new":counts.get(today.isoformat(),0),"today_login":login_count,
                "withdrawal_total":int(withdrawal_total),"withdrawal_amount":float(withdrawal_amount),
                "items":[{"date":(start+timedelta(days=i)).isoformat(),"count":counts.get((start+timedelta(days=i)).isoformat(),0)} for i in range(31)],
                "income_items":[{"date":(start+timedelta(days=i)).isoformat(),"coin":round(incomes.get((start+timedelta(days=i)).isoformat(),0.0),2),"clicks":ad_stats.get((start+timedelta(days=i)).isoformat(),{}).get('clicks',0),"estimate_income":round(ad_stats.get((start+timedelta(days=i)).isoformat(),{}).get('income',0.0),2)} for i in range(31)],"regions":regions}


@api.patch("/agents/{agent_id}/oss", dependencies=[Depends(allow_roles("operator"))])
def update_agent_oss(agent_id: int, payload: AgentOssConfig) -> dict[str, bool]:
    with SessionLocal() as session:
        item = get_or_404(session, Agent, agent_id, "主体")
        item.oss_config = json.dumps(payload.model_dump(), ensure_ascii=False)
        session.commit()
        return {"saved": True}


@api.get("/agents/{agent_id}")
def get_agent(agent_id: int) -> dict[str, Any]:
    with SessionLocal() as session:
        return serialize(get_or_404(session, Agent, agent_id, "主体"), AGENT_EDITOR_FIELDS)


@api.post(
    "/agents",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(allow_roles("operator"))],
)
def create_agent(payload: AgentCreate) -> dict[str, Any]:
    changes = payload.model_dump()
    require_nonblank(changes, "name", "主体名称")
    with SessionLocal() as session:
        validate_agent_parent(session, changes["parent_id"])
        prepare_agent_password(changes)
        item = Agent(**changes)
        session.add(item)
        session.commit()
        session.refresh(item)
        return serialize_agent(item)


@api.patch("/agents/{agent_id}", dependencies=[Depends(allow_roles("operator"))])
def update_agent(agent_id: int, payload: AgentUpdate) -> dict[str, Any]:
    changes = payload.model_dump(exclude_unset=True)
    require_nonblank(changes, "name", "主体名称")
    require_not_none(changes, ["parent_id", "status", "game_ad_status", "ht_status", "is_gx"])
    with SessionLocal() as session:
        item = get_or_404(session, Agent, agent_id, "主体")
        if "parent_id" in changes:
            validate_agent_parent(session, changes["parent_id"], agent_id)
        prepare_agent_password(changes)
        for field, value in changes.items():
            setattr(item, field, value)
        session.commit()
        session.refresh(item)
        return serialize_agent(item)


@api.delete(
    "/agents/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(allow_roles("operator"))],
)
def delete_agent(agent_id: int) -> Response:
    with SessionLocal() as session:
        item = get_or_404(session, Agent, agent_id, "主体")
        dependencies = [
            (Agent, Agent.parent_id == agent_id),
            (Game, Game.agent_id == agent_id),
            (Member, Member.agent_id == agent_id),
            (AdRecord, AdRecord.agent_id == agent_id),
            (Withdrawal, Withdrawal.agent_id == agent_id),
            (Subsidy, Subsidy.agent_id == agent_id),
            (CoinLog, CoinLog.agent_id == agent_id),
            (RiskRecord, RiskRecord.agent_id == agent_id),
        ]
        if any(has_rows(session, model, condition) for model, condition in dependencies):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="主体存在关联数据，不能删除")
        analysis_config = session.get(AgentAnalysisConfig, agent_id)
        if analysis_config is not None:
            session.delete(analysis_config)
        session.delete(item)
        session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)


@api.get("/games/{game_id}")
def get_game(game_id: int) -> dict[str, Any]:
    with SessionLocal() as session:
        return serialize_game_editor(get_or_404(session, Game, game_id, "游戏"))


@api.post(
    "/games",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(allow_roles("operator"))],
)
def create_game(payload: GameCreate) -> dict[str, Any]:
    changes = payload.model_dump()
    require_nonblank(changes, "name", "游戏名称")
    merge_game_ad_config(changes)
    validate_json_text(changes, "settings_json")
    with SessionLocal() as session:
        validate_game_agent(session, changes["agent_id"])
        item = Game(**changes)
        session.add(item)
        session.commit()
        session.refresh(item)
        return serialize_game(item)


@api.patch("/games/{game_id}", dependencies=[Depends(allow_roles("operator"))])
def update_game(game_id: int, payload: GameUpdate) -> dict[str, Any]:
    changes = payload.model_dump(exclude_unset=True)
    require_nonblank(changes, "name", "游戏名称")
    require_not_none(
        changes,
        [
            "agent_id",
            "status",
            "ad_status",
            "lucky_enable",
            "is_landscape",
            "is_game",
            "is_mobile",
            "is_imei",
            "raffle_num",
            "star_countdown",
            "over_countdown",
            "star_coin",
            "over_coin",
            "coin_get",
            "exchange_num",
            "commission_status",
            "commission_source",
            "commission_rate",
            "tixian_wx",
        ],
    )
    with SessionLocal() as session:
        item = get_or_404(session, Game, game_id, "游戏")
        merge_game_ad_config(changes, item.settings_json)
        validate_json_text(changes, "settings_json")
        if "agent_id" in changes:
            validate_game_agent(session, changes["agent_id"])
        for field, value in changes.items():
            setattr(item, field, value)
        session.commit()
        session.refresh(item)
        return serialize_game(item)


class GameAdConfigUpdate(BaseModel):
    taku_callback_enabled: Literal[0, 1] | None = None
    taku_sec_key: str = Field(default="", max_length=512)
    taku_clear_sec_key: bool = False
    provider: str = Field(default="internal", max_length=64)
    app_id: str = Field(default="", max_length=128)
    app_key: str = Field(default="", max_length=255)
    enabled: Literal[0, 1] = 1
    rewarded_unit_id: str = Field(default="", max_length=255)
    interstitial_unit_id: str = Field(default="", max_length=255)
    banner_unit_id: str = Field(default="", max_length=255)
    splash_unit_id: str = Field(default="", max_length=255)
    native_unit_id: str = Field(default="", max_length=255)
    reward_coin: float = Field(default=0.01, ge=0, allow_inf_nan=False)
    cooldown_seconds: int = Field(default=0, ge=0, le=86400)


@api.get("/games/{game_id}/ad-config")
def get_game_ad_config(game_id: int) -> dict[str, Any]:
    with SessionLocal() as session:
        item = get_or_404(session, Game, game_id, "游戏")
        return {"game_id": item.id, **game_ad_config(item), **taku_admin_config(session, item.id)}


@api.patch("/games/{game_id}/ad-config", dependencies=[Depends(allow_roles("operator"))])
def update_game_ad_config(game_id: int, payload: GameAdConfigUpdate) -> dict[str, Any]:
    with SessionLocal() as session:
        item = get_or_404(session, Game, game_id, "游戏")
        changes = {
            "ad_provider": payload.provider,
            "ad_app_id": payload.app_id,
            "ad_app_key": payload.app_key,
            "ad_config_enabled": payload.enabled,
            "ad_rewarded_unit_id": payload.rewarded_unit_id,
            "ad_interstitial_unit_id": payload.interstitial_unit_id,
            "ad_banner_unit_id": payload.banner_unit_id,
            "ad_splash_unit_id": payload.splash_unit_id,
            "ad_native_unit_id": payload.native_unit_id,
            "ad_reward_coin": payload.reward_coin,
            "ad_cooldown_seconds": payload.cooldown_seconds,
        }
        merge_game_ad_config(changes, item.settings_json)
        item.settings_json = changes["settings_json"]
        if payload.taku_callback_enabled is not None or payload.taku_sec_key or payload.taku_clear_sec_key:
            callback = session.get(GameTakuConfig, game_id)
            if callback is None:
                enabled, key = taku_credentials(session, game_id)
                callback = GameTakuConfig(game_id=game_id, enabled=int(enabled), sec_key=key)
                session.add(callback)
            if payload.taku_sec_key and payload.taku_clear_sec_key:
                raise HTTPException(422, "Cannot set and clear TAKU key together")
            if payload.taku_sec_key:
                callback.sec_key = payload.taku_sec_key.strip()
            if payload.taku_clear_sec_key:
                callback.sec_key = ""
            if payload.taku_callback_enabled is not None:
                callback.enabled = payload.taku_callback_enabled
            if callback.enabled and (not callback.sec_key or payload.provider.strip().lower() != "taku" or not payload.rewarded_unit_id.strip()):
                raise HTTPException(422, "启用 TAKU 回调需要选择 taku、填写激励广告位及服务端密钥")
        session.commit()
        session.refresh(item)
        return {"game_id": item.id, **game_ad_config(item), **taku_admin_config(session, item.id)}


@api.delete(
    "/games/{game_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(allow_roles("operator"))],
)
def delete_game(game_id: int) -> Response:
    with SessionLocal() as session:
        item = get_or_404(session, Game, game_id, "游戏")
        dependencies = [
            (Member, Member.game_id == game_id),
            (AdRecord, AdRecord.game_id == game_id),
            (Withdrawal, Withdrawal.game_id == game_id),
            (Subsidy, Subsidy.game_id == game_id),
            (CoinLog, CoinLog.game_id == game_id),
            (RiskRecord, RiskRecord.game_id == game_id),
            (MemberLoginLog, MemberLoginLog.game_id == game_id),
            (LotteryRecord, LotteryRecord.game_id == game_id),
            (MemberAppUsage, MemberAppUsage.game_id == game_id),
        ]
        if any(has_rows(session, model, condition) for model, condition in dependencies):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="游戏存在关联数据，不能删除")
        session.delete(item)
        session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)


class GameMemberBatchStatus(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)
    status: Literal[0, 1]

class MemberClearCoins(BaseModel):
    reason: str = Field(default="管理员清空金币", max_length=255)


@api.post('/members/batch-status')
def member_batch_status(payload: GameMemberBatchStatus, agent_id: int | None = None,
                        admin: AdminUser = Depends(allow_roles('operator'))) -> dict[str, Any]:
    with SessionLocal() as session:
        ids=set(payload.ids)
        rows=session.scalars(select(Member).where(Member.id.in_(ids)).with_for_update()).all()
        if len(rows)!=len(ids):
            raise HTTPException(404,'会员不存在')
        if agent_id is not None and any(row.agent_id!=agent_id for row in rows):
            raise HTTPException(422,'所选会员不属于当前主体')
        for row in rows:
            row.status=payload.status
        session.commit()
        return {'updated':len(rows)}

@api.post("/members/{member_id}/clear-coins")
def clear_member_coins(member_id: int, payload: MemberClearCoins = MemberClearCoins(),
                       admin: AdminUser = Depends(allow_roles("operator"))) -> dict[str, Any]:
    with SessionLocal() as session:
        item = get_or_404(session, Member, member_id, "会员")
        before = float(item.coin or 0) + float(item.freeze_coin or 0)
        item.coin = 0.0
        item.freeze_coin = 0.0
        session.add(CoinLog(user_id=item.id, game_id=item.game_id, coin=-before,
                            coin_before=before, coin_after=0.0, type=9,
                            remark=payload.reason))
        session.commit()
        session.refresh(item)
        return serialize_member(item)


@api.post("/games/{game_id}/members/batch-status")
def game_member_batch_status(game_id: int, payload: GameMemberBatchStatus,
                             admin: AdminUser = Depends(allow_roles("operator"))) -> dict[str, Any]:
    with SessionLocal() as session:
        get_or_404(session, Game, game_id, "游戏")
        ids = set(payload.ids)
        rows = session.scalars(select(Member).where(Member.id.in_(ids)).with_for_update()).all()
        if len(rows) != len(ids):
            raise HTTPException(status_code=404, detail="会员不存在")
        if any(row.game_id != game_id for row in rows):
            raise HTTPException(status_code=422, detail="所选会员不属于当前游戏")
        for row in rows:
            row.status = payload.status
        session.commit()
        return {"updated": len(rows)}


@api.get("/members/{member_id}")
def get_member(member_id: int) -> dict[str, Any]:
    with SessionLocal() as session:
        return serialize_member(get_or_404(session, Member, member_id, "会员"))


@api.post(
    "/members",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(allow_roles("operator"))],
)
def create_member(payload: MemberCreate) -> dict[str, Any]:
    changes = payload.model_dump()
    require_nonblank(changes, "username", "会员账号")
    with SessionLocal() as session:
        validate_member_scope(session, changes["agent_id"], changes["game_id"])
        prepare_member_passwords(changes)
        item = Member(**changes)
        session.add(item)
        session.commit()
        session.refresh(item)
        return serialize_member(item)


@api.get("/member-addresses")
def list_member_addresses(user_id: int, game_id: int | None = None,
                          filter_user_id: int | None = None, game_name: str | None = None,
                          receive_name: str | None = None, receive_tel: str | None = None,
                          receive_postcode: str | None = None, receive_address: str | None = None,
                          created_from: datetime | None = None, created_to: datetime | None = None,
                          sort: Literal["id", "created_at"] = "id", order: Literal["asc", "desc"] = "desc",
                          limit: int = Query(20, ge=1, le=200), offset: int = Query(0, ge=0)) -> dict[str, Any]:
    """Expose only the address stored on the member; no synthetic address records."""
    if created_from is not None and created_from.tzinfo:
        created_from = created_from.astimezone(UTC).replace(tzinfo=None)
    if created_to is not None and created_to.tzinfo:
        created_to = created_to.astimezone(UTC).replace(tzinfo=None)
    if created_from is not None and created_to is not None and created_from > created_to:
        raise HTTPException(status_code=422, detail="创建时间范围无效")
    with SessionLocal() as session:
        member = get_or_404(session, Member, user_id, "会员")
        if filter_user_id is not None and filter_user_id != user_id:
            return {"total": 0, "items": [], "limit": limit, "offset": offset}
        if game_id is not None and member.game_id != game_id:
            return {"total": 0, "items": [], "limit": limit, "offset": offset}
        if not member.address.strip():
            return {"total": 0, "items": [], "limit": limit, "offset": offset}
        if (receive_name is not None and receive_name != member.name or
                receive_address is not None and receive_address != member.address or
                receive_tel or receive_postcode or
                created_from is not None and member.created_at < created_from or
                created_to is not None and member.created_at > created_to):
            return {"total": 0, "items": [], "limit": limit, "offset": offset}
        game = session.get(Game, member.game_id)
        if game_name and (game is None or game.name != game_name):
            return {"total": 0, "items": [], "limit": limit, "offset": offset}
        if offset > 0:
            return {"total": 1, "items": [], "limit": limit, "offset": offset}
        return {"total": 1, "items": [{"id": member.id, "user_id": member.id,
                 "username": member.username, "game_id": member.game_id,
                 "game_name": game.name if game else "",
                 "receive_name": member.name, "receive_tel": "", "receive_postcode": "",
                 "receive_address": member.address, "default_status": 1,
                 "created_at": member.created_at}], "limit": limit, "offset": offset}


class MemberAddressUpdate(BaseModel):
    receive_name: str | None = None
    receive_tel: str | None = None
    receive_address: str


@api.patch("/member-addresses/{user_id}", dependencies=[Depends(allow_roles("operator"))])
def update_member_address(user_id: int, payload: MemberAddressUpdate) -> dict[str, Any]:
    require_nonblank(payload.model_dump(), "receive_address", "收货地址")
    with SessionLocal() as session:
        member = get_or_404(session, Member, user_id, "会员")
        member.address = payload.receive_address.strip()
        if payload.receive_name is not None:
            member.name = payload.receive_name.strip()
        session.commit()
        session.refresh(member)
        return {"id": member.id, "user_id": member.id, "receive_name": member.name,
                "receive_tel": payload.receive_tel or "", "receive_address": member.address,
                "default_status": 1, "created_at": member.created_at}


@api.patch("/members/{member_id}")
def update_member(
    member_id: int,
    payload: MemberUpdate,
    admin: AdminUser = Depends(allow_roles("operator", "risk")),
) -> dict[str, Any]:
    changes = payload.model_dump(exclude_unset=True)
    if admin.role == "risk" and set(changes) - {"is_white"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="风控角色只能调整白名单状态")
    require_nonblank(changes, "username", "会员账号")
    require_not_none(changes, ["receive_name", "down_load", "image_url", "otherlevel", "game_addiction_time"])
    require_not_none(
        changes,
        [
            "agent_id",
            "game_id",
            "parent_id",
            "sex",
            "coin",
            "freeze_coin",
            "coin_user",
            "coin_user_month",
            "coin_user_day",
            "vip",
            "status",
            "exchange_enable",
            "game_addiction_enable",
            "is_white",
            "ht_status",
            "ht_id",
            "ht_top_id",
            "beishu",
            "percent_zhi",
            "percent_jian",
            "percent_dai",
            "percent_dai_two",
        ],
    )
    with SessionLocal() as session:
        item = get_or_404(session, Member, member_id, "会员")
        agent_id = changes.get("agent_id", item.agent_id)
        game_id = changes.get("game_id", item.game_id)
        validate_member_scope(session, agent_id, game_id)
        prepare_member_passwords(changes)
        for field, value in changes.items():
            setattr(item, field, value)
        session.commit()
        session.refresh(item)
        return serialize_member(item)


@api.delete(
    "/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(allow_roles("operator"))],
)
def delete_member(member_id: int) -> Response:
    with SessionLocal() as session:
        item = get_or_404(session, Member, member_id, "会员")
        dependencies = [
            (AdRecord, AdRecord.user_id == member_id),
            (Withdrawal, Withdrawal.user_id == member_id),
            (Subsidy, Subsidy.user_id == member_id),
            (CoinLog, CoinLog.user_id == member_id),
            (RiskRecord, RiskRecord.user_id == member_id),
            (MemberLoginLog, MemberLoginLog.user_id == member_id),
            (LotteryRecord, LotteryRecord.user_id == member_id),
            (MemberDevice, MemberDevice.user_id == member_id),
            (MemberAppUsage, MemberAppUsage.user_id == member_id),
        ]
        if any(has_rows(session, model, condition) for model, condition in dependencies):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="会员存在关联流水或审核记录，不能删除")
        session.delete(item)
        session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)


@api.get("/withdrawals/{withdrawal_id}")
def get_withdrawal(withdrawal_id: int, admin: AdminUser = Depends(require_admin)) -> dict[str, Any]:
    with SessionLocal() as session:
        item = get_or_404(session, Withdrawal, withdrawal_id, "提现记录")
        return serialize_withdrawal(item)


@api.patch("/withdrawals/{withdrawal_id}")
def update_withdrawal(
    withdrawal_id: int,
    payload: WithdrawalUpdate,
    request: Request,
    admin: AdminUser = Depends(allow_roles("reviewer")),
) -> dict[str, Any]:
    changes = payload.model_dump(exclude_unset=True)
    editable_fields = {
        "good_name", "device_manufacturer", "delivery_name", "delivery_no", "remark",
        "receive_name", "receive_tel", "receive_address", "exchange_value", "exchange_type",
    }
    require_not_none(changes, list(changes))
    if not changes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="至少需要修改一项提现信息")
    if not set(changes).intersection(editable_fields | {"status", "plan_status", "sub_msg", "reason"}):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="没有可修改的提现信息")
    for field in editable_fields - {"exchange_value", "exchange_type"}:
        if field in changes:
            changes[field] = str(changes[field]).strip()
    if "exchange_value" in changes and changes["exchange_value"] < 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="提现金额不能为负数")
    if "exchange_type" in changes and changes["exchange_type"] not in (0, 1, 2):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="提现方式无效")
    if "status" in changes and changes["status"] not in (0, 1, 2, 4):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="提现状态无效")
    if changes.get("status") == 4:
        changes["status"] = 2
    if changes.get("status") == 2:
        changes["reason"] = (changes.get("reason") or "").strip()
        if not changes["reason"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="拒绝提现时必须填写原因")
    if "plan_status" in changes and changes["plan_status"] not in (0, 1, 2):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="转账状态无效")
    with SessionLocal() as session:
        payouts.lock(session)
        item = session.scalar(select(Withdrawal).where(Withdrawal.id == withdrawal_id).with_for_update())
        if item is None: raise HTTPException(404, '提现不存在')
        payout = session.scalar(select(payouts.Payout).where(payouts.Payout.withdrawal_id == item.id))
        if payout and set(changes).intersection({'exchange_value', 'exchange_type', 'receive_name', 'receive_tel'}):
            raise HTTPException(422, '已冻结提现的金额和收款信息不可修改')
        if set(changes).intersection(editable_fields) and item.status != 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已处理的提现记录不能编辑")
        if "status" in changes and changes["status"] != item.status:
            if item.status != 0:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="提现记录已处理，不能重复审核")
            if changes["status"] in (1, 2):
                if changes['status'] == 2: payouts.release_funds(session, item)
                mark_audit(item, admin)
        if "plan_status" in changes and changes["plan_status"] != item.plan_status:
            if item.status != 1:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="提现记录必须先审核")
            if item.plan_status != 0:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="提现记录已处理转账状态，不能重复转账")
            if changes["plan_status"] in (1, 2):
                require_payment_integration()
                raise HTTPException(409, '请使用支付宝转账接口，不能手工标记到账')
        for field, value in changes.items():
            setattr(item, field, value)
        session.add(AdminOperation(admin_id=admin.id, title=f"编辑提现记录（{withdrawal_id}）", path=request.url.path,
                                   ip=request.client.host if request.client else ""))
        session.commit()
        session.refresh(item)
        return serialize_withdrawal(item)


@api.post("/withdrawals/{withdrawal_id}/approve")
def approve_withdrawal(
    withdrawal_id: int,
    payload: WithdrawalAction | None = None,
    admin: AdminUser = Depends(allow_roles("reviewer")),
) -> dict[str, Any]:
    with SessionLocal() as session:
        payouts.lock(session)
        item = session.scalar(select(Withdrawal).where(Withdrawal.id == withdrawal_id).with_for_update())
        if item is None: raise HTTPException(404, '提现不存在')
        if item.status != 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="提现记录已处理，不能重复审核")
        item.status = 1
        if payload and payload.reason:
            item.sub_msg = payload.reason.strip()
        mark_audit(item, admin)
        session.commit()
        session.refresh(item)
        return serialize_withdrawal(item)


@api.post("/withdrawals/{withdrawal_id}/reject")
def reject_withdrawal(
    withdrawal_id: int,
    payload: WithdrawalAction,
    admin: AdminUser = Depends(allow_roles("reviewer")),
) -> dict[str, Any]:
    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="拒绝原因不能为空")
    with SessionLocal() as session:
        payouts.lock(session)
        item = session.scalar(select(Withdrawal).where(Withdrawal.id == withdrawal_id).with_for_update())
        if item is None: raise HTTPException(404, '提现不存在')
        if item.status != 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="提现记录已处理，不能重复审核")
        payouts.release_funds(session, item)
        item.status = 2
        item.reason = reason
        mark_audit(item, admin)
        session.commit()
        session.refresh(item)
        return serialize_withdrawal(item)


@api.post("/withdrawals/{withdrawal_id}/transfer")
def transfer_withdrawal(
    withdrawal_id: int,
    admin: AdminUser = Depends(allow_roles("reviewer")),
) -> dict[str, Any]:
    return payouts.transfer(withdrawal_id, admin)


@api.patch("/subsidies/{subsidy_id}")
def update_subsidy(
    subsidy_id: int,
    payload: SubsidyUpdate,
    request: Request,
    admin: AdminUser = Depends(allow_roles("reviewer")),
) -> dict[str, Any]:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="至少需要修改一项补贴信息")
    require_not_none(changes, list(changes))
    if "status" in changes and changes["status"] not in (0, 1, 2, 4):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="补贴状态无效")
    if changes.get("status") == 4:
        changes["status"] = 2
    if changes.get("status") == 2:
        changes["sub_msg"] = (changes.get("sub_msg") or "").strip()
        if not changes["sub_msg"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="拒绝补贴时必须填写原因")
    with SessionLocal() as session:
        item = session.scalar(select(Subsidy).where(Subsidy.id == subsidy_id).with_for_update())
        if item is None:
            raise HTTPException(status_code=404, detail="补贴记录不存在")
        campaign_snapshot = subsidy_campaigns.application_snapshot(session, item)
        if campaign_snapshot is not None:
            for field in ('tx_price', 'price', 'pics'):
                if field in changes and changes[field] != getattr(item, field):
                    raise HTTPException(422, '活动申请的条件金额、补贴金额和凭证不可修改，请审核通过或驳回')
        if "status" in changes and changes["status"] != item.status:
            if item.status != 0:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="补贴记录已处理，不能重复审核")
            if changes["status"] in (1, 2, 4):
                mark_audit(item, admin)
        for field, value in changes.items():
            setattr(item, field, value)
        session.add(AdminOperation(admin_id=admin.id, title=f"编辑补贴记录（{subsidy_id}）", path=request.url.path,
                                   ip=request.client.host if request.client else ""))
        session.commit()
        session.refresh(item)
        return serialize_subsidy(item)


@api.delete(
    "/subsidies/{subsidy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_subsidy(subsidy_id: int, request: Request,
                   admin: AdminUser = Depends(allow_roles("reviewer"))) -> Response:
    remove_subsidies([subsidy_id], request, admin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api.post("/subsidies/{subsidy_id}/approve")
def approve_subsidy(
    subsidy_id: int,
    payload: SubsidyAction | None = None,
    admin: AdminUser = Depends(allow_roles("reviewer")),
) -> dict[str, Any]:
    with SessionLocal() as session:
        item = get_or_404(session, Subsidy, subsidy_id, "鐞涖儴鍒涚拋鏉跨秿")
        if item.status != 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="补贴记录已处理，不能重复审核")
        item.status = 1
        if payload and payload.message:
            item.sub_msg = payload.message.strip()
        mark_audit(item, admin)
        session.commit()
        session.refresh(item)
        return serialize_subsidy(item)


@api.post("/subsidies/{subsidy_id}/reject")
def reject_subsidy(
    subsidy_id: int,
    payload: SubsidyAction,
    admin: AdminUser = Depends(allow_roles("reviewer")),
) -> dict[str, Any]:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="拒绝原因不能为空")
    with SessionLocal() as session:
        item = get_or_404(session, Subsidy, subsidy_id, "鐞涖儴鍒涚拋鏉跨秿")
        if item.status != 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="补贴记录已处理，不能重复审核")
        item.status = 2
        item.sub_msg = message
        mark_audit(item, admin)
        session.commit()
        session.refresh(item)
        return serialize_subsidy(item)


@api.get("/kuaishou-risk")
def list_kuaishou_risk(
    agent_id: int | None = Query(None, ge=1),
    game_id: int | None = Query(None, ge=1),
    date_from: date | None = None,
    date_to: date | None = None,
    risk_level: Literal["safe", "attention", "warning", "high"] | None = None,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_admin),
) -> dict[str, Any]:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=422, detail="日期范围无效")
    with SessionLocal() as session:
        conditions: list[Any] = []
        if agent_id is not None:
            conditions.append(KuaishouRiskAssessment.agent_id == agent_id)
        if game_id is not None:
            conditions.append(KuaishouRiskAssessment.game_id == game_id)
        if date_from is not None:
            conditions.append(KuaishouRiskAssessment.assessment_date >= date_from)
        if date_to is not None:
            conditions.append(KuaishouRiskAssessment.assessment_date <= date_to)
        if risk_level:
            conditions.append(KuaishouRiskAssessment.risk_level == risk_level)
        payload = list_payload(
            session,
            KuaishouRiskAssessment,
            ["risk_level", "suggestion", "operator_name"],
            serialize_kuaishou_risk,
            None,
            limit,
            offset,
            conditions,
            [KuaishouRiskAssessment.assessment_date.desc(), KuaishouRiskAssessment.id.desc()],
        )
        rows = payload["items"]
        agent_ids = {row["agent_id"] for row in rows if row["agent_id"]}
        game_ids = {row["game_id"] for row in rows if row["game_id"]}
        agents = dict(session.execute(select(Agent.id, Agent.name).where(Agent.id.in_(agent_ids))).all()) if agent_ids else {}
        games = dict(session.execute(select(Game.id, Game.name).where(Game.id.in_(game_ids))).all()) if game_ids else {}
        for row in rows:
            row["agent_name"] = agents.get(row["agent_id"], "")
            row["game_name"] = games.get(row["game_id"], "")
        summary_stmt = select(
            func.count(KuaishouRiskAssessment.id).label("total"),
            func.coalesce(func.avg(KuaishouRiskAssessment.risk_score), 0.0).label("average_score"),
        ).where(*conditions)
        summary_row = session.execute(summary_stmt).one()
        level_counts = dict(session.execute(
            select(KuaishouRiskAssessment.risk_level, func.count(KuaishouRiskAssessment.id))
            .where(*conditions).group_by(KuaishouRiskAssessment.risk_level)
        ).all())
        payload["summary"] = {
            "total": int(summary_row.total or 0),
            "average_score": round(float(summary_row.average_score or 0), 2),
            "levels": {level: int(level_counts.get(level, 0)) for level in ("safe", "attention", "warning", "high")},
        }
        payload["permissions"] = {"can_write": admin.role == "superadmin" or admin.role == "operator"}
        return payload


@api.post("/kuaishou-risk", status_code=status.HTTP_201_CREATED)
def create_kuaishou_risk(
    payload: KuaishouRiskAssessmentCreate,
    request: Request,
    admin: AdminUser = Depends(allow_roles("operator")),
) -> dict[str, Any]:
    with SessionLocal() as session:
        agent = session.get(Agent, payload.agent_id) if payload.agent_id else None
        game = session.get(Game, payload.game_id) if payload.game_id else None
        if payload.agent_id and agent is None:
            raise HTTPException(status_code=404, detail="主体不存在")
        if payload.game_id and game is None:
            raise HTTPException(status_code=404, detail="游戏不存在")
        if game is not None and payload.agent_id and game.agent_id != payload.agent_id:
            raise HTTPException(status_code=422, detail="游戏不属于所选主体")
        result = calculate_kuaishou_risk(payload)
        item = KuaishouRiskAssessment(
            assessment_date=payload.assessment_date,
            agent_id=payload.agent_id,
            game_id=payload.game_id,
            pay_rate=payload.pay_rate,
            retain_1=payload.retain_1,
            ctr=payload.ctr,
            flow_growth=payload.flow_growth,
            device_repeat=payload.device_repeat,
            **result,
            source="manual",
            operator_id=admin.id,
            operator_name=operator_display_name(admin),
        )
        session.add(item)
        session.flush()
        session.add(AdminOperation(
            admin_id=admin.id,
            title="新增快手风控评估",
            path=request.url.path,
            ip=request.client.host if request.client else "",
        ))
        session.commit()
        session.refresh(item)
        response = serialize_kuaishou_risk(item)
        response["agent_name"] = agent.name if agent else ""
        response["game_name"] = game.name if game else ""
        return response


@api.get("/kuaishou-risk/{assessment_id}")
def get_kuaishou_risk(assessment_id: int, admin: AdminUser = Depends(require_admin)) -> dict[str, Any]:
    with SessionLocal() as session:
        item = get_or_404(session, KuaishouRiskAssessment, assessment_id, "快手风控评估")
        response = serialize_kuaishou_risk(item)
        agent = session.get(Agent, item.agent_id) if item.agent_id else None
        game = session.get(Game, item.game_id) if item.game_id else None
        response["agent_name"] = agent.name if agent else ""
        response["game_name"] = game.name if game else ""
        response["permissions"] = {"can_write": admin.role == "superadmin" or admin.role == "operator"}
        return response


# Register campaign routes before the generic detail route and static mount.
from . import subsidy_campaigns
from . import payouts
from . import device_risk


@api.get("/{resource}/{item_id}")
def resource_detail(resource: str, item_id: int) -> dict[str, Any]:
    mapping: dict[str, tuple[Any, list[str], Callable[[Any], dict[str, Any]]]] = {
        "agents": (Agent, AGENT_FIELDS, serialize_agent),
        "games": (Game, GAME_FIELDS, serialize_game),
        "members": (Member, MEMBER_FIELDS, serialize_member),
        "ads": (AdRecord, AD_FIELDS, serialize_ad),
        "withdrawals": (Withdrawal, WITHDRAWAL_FIELDS, serialize_withdrawal),
        "subsidies": (Subsidy, SUBSIDY_FIELDS, serialize_subsidy),
        "coin-logs": (CoinLog, COINLOG_FIELDS, serialize_coinlog),
        "risk-history": (RiskRecord, RISK_FIELDS, serialize_risk),
    }
    if resource not in mapping:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资金流水不存在")

    model, _fields, serializer = mapping[resource]
    with SessionLocal() as session:
        return serializer(get_or_404(session, model, item_id, "记录"))


app.include_router(app_api)
app.include_router(api)

# Keep the standalone FastAPI entry point usable in development as well as
# through the Node shell.  API routes are registered before this catch-all
# mount, so `/api/*` continues to be handled by FastAPI.
app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")


