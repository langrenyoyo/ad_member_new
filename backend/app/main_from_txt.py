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
from urllib.parse import unquote

import jwt
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pydantic import BaseModel, Field
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
    payload = serialize(item, list(item.__table__.columns.keys()))
    payload["target_status"] = 4 if item.status == 2 else item.status
    return payload


def serialize_subsidy(item: Subsidy) -> dict[str, Any]:
    payload = serialize(item, list(item.__table__.columns.keys()))
    payload["target_status"] = 4 if item.status == 2 else item.status
    return payload


def serialize_coinlog(item: CoinLog) -> dict[str, Any]:
    return serialize(item, list(item.__table__.columns.keys()))


def serialize_risk(item: RiskRecord) -> dict[str, Any]:
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


app = FastAPI(title="广告会员后台", version="0.1.0", lifespan=lifespan)
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
    if not ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="至少需要一条提现记录")
    if target_status == 2 and not allow_reasonless and not reason.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="拒绝提现时必须填写原因")
    with SessionLocal() as session:
        rows = session.scalars(select(Withdrawal).where(Withdrawal.id.in_(ids))).all()
        if len(rows) != len(set(ids)):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="提现记录不存在")
        if plan_status is not None:
            for item in rows:
                if item.status != 1 or item.plan_status != 0:
                    raise HTTPException(status_code=409, detail="只能转账已审核通过且尚未转账的提现记录")
            require_payment_integration()
        for item in rows:
            if target_status is not None:
                if item.status != 0:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只能处理申请中的提现记录")
                item.status = target_status
                if target_status == 2:
                    item.reason = reason.strip()
                if admin:
                    mark_audit(item, admin)
            if plan_status is not None:
                if item.status != 1 or item.plan_status != 0:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只能转账已审核通过且尚未转账的提现记录")
                item.plan_status = plan_status
                if plan_status == 1 and admin:
                    item.transfer_operator_id = admin.id
                    item.transfer_operator_name = operator_display_name(admin)
                    item.transferred_at = now()
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
    result = _batch_withdrawal_update(payload.ids, plan_status=1, admin=admin)
    payment = configured_provider().transfer(payload.ids)
    result.update(payment_provider=payment.provider, payment_confirmed=payment.confirmed)
    return result


@api.post("/withdrawals/batch-transfer-scheduled")
def batch_transfer_withdrawals_scheduled(payload: WithdrawalBatch, admin: AdminUser = Depends(allow_roles("reviewer"))) -> dict[str, Any]:
    result = _batch_withdrawal_update(payload.ids, plan_status=1, admin=admin)
    payment = configured_provider().transfer(payload.ids)
    result.update(payment_provider=payment.provider, payment_confirmed=payment.confirmed)
    return result


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
        return serialize(get_or_404(session, Game, game_id, "游戏"), GAME_EDITOR_FIELDS)


@api.post(
    "/games",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(allow_roles("operator"))],
)
def create_game(payload: GameCreate) -> dict[str, Any]:
    changes = payload.model_dump()
    require_nonblank(changes, "name", "游戏名称")
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
    validate_json_text(changes, "settings_json")
    with SessionLocal() as session:
        item = get_or_404(session, Game, game_id, "游戏")
        if "agent_id" in changes:
            validate_game_agent(session, changes["agent_id"])
        for field, value in changes.items():
            setattr(item, field, value)
        session.commit()
        session.refresh(item)
        return serialize_game(item)


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
        item = get_or_404(session, Withdrawal, withdrawal_id, "提现记录")
        if set(changes).intersection(editable_fields) and item.status != 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已处理的提现记录不能编辑")
        if "status" in changes and changes["status"] != item.status:
            if item.status != 0:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="提现记录已处理，不能重复审核")
            if changes["status"] in (1, 2):
                mark_audit(item, admin)
        if "plan_status" in changes and changes["plan_status"] != item.plan_status:
            if item.status != 1:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="提现记录必须先审核")
            if item.plan_status != 0:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="提现记录已处理转账状态，不能重复转账")
            if changes["plan_status"] in (1, 2):
                require_payment_integration()
                item.transfer_operator_id = admin.id
                item.transfer_operator_name = operator_display_name(admin)
                item.transferred_at = now()
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
        item = get_or_404(session, Withdrawal, withdrawal_id, "提现记录")
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
        item = get_or_404(session, Withdrawal, withdrawal_id, "提现记录")
        if item.status != 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="提现记录已处理，不能重复审核")
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
    with SessionLocal() as session:
        item = get_or_404(session, Withdrawal, withdrawal_id, "提现记录")
        if item.status != 1:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="提现记录必须先审核")
        if item.plan_status != 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="提现记录已处理转账状态，不能重复转账")
        require_payment_integration()
        item.plan_status = 1
        item.transfer_operator_id = admin.id
        item.transfer_operator_name = operator_display_name(admin)
        item.transferred_at = now()
        session.commit()
        session.refresh(item)
        return serialize_withdrawal(item)


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


app.include_router(api)


