"""APP Alipay withdrawals with immutable orders and transactional wallet holds."""
import json
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from fastapi import Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, Integer, Numeric, String, Text, UniqueConstraint, func, select, text
from sqlalchemy.orm import Mapped, mapped_column

from . import main_from_txt as m


class AlipayAccount(m.Base, m.TimestampMixin):
    __tablename__ = 'alipay_accounts'
    member_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account: Mapped[str] = mapped_column(String(128))
    real_name: Mapped[str] = mapped_column(String(64))


class Payout(m.Base, m.TimestampMixin):
    __tablename__ = 'withdrawal_payouts'
    __table_args__ = (UniqueConstraint('member_id', 'request_key', name='uq_payout_member_request'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    withdrawal_id: Mapped[int] = mapped_column(Integer, unique=True)
    member_id: Mapped[int] = mapped_column(Integer, index=True)
    request_key: Mapped[str] = mapped_column(String(128))
    game_id: Mapped[int] = mapped_column(Integer)
    amount_cents: Mapped[int] = mapped_column(Integer)
    coin_cost: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    account: Mapped[str] = mapped_column(String(128))
    real_name: Mapped[str] = mapped_column(String(64))
    out_biz_no: Mapped[str] = mapped_column(String(64), unique=True)
    provider_scope: Mapped[str] = mapped_column(String(128), default='')
    provider_order_id: Mapped[str] = mapped_column(String(128), default='')
    state: Mapped[str] = mapped_column(String(32), default='pending_review', index=True)
    error: Mapped[str] = mapped_column(String(512), default='')
    next_query_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BindAlipay(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    account: str = Field(min_length=3, max_length=64)
    real_name: str = Field(min_length=2, max_length=64)
    current_password: str = Field(min_length=1, max_length=128)

    @field_validator('account')
    @classmethod
    def valid_account(cls, value):
        if not m.re.fullmatch(r'(?:\+?\d{7,20}|[^\s@]+@[^\s@]+\.[^\s@]+)', value):
            raise ValueError('支付宝账号应为手机号或邮箱')
        return value


class WithdrawalApply(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_key: str = Field(min_length=8, max_length=128)
    game_id: int = Field(ge=1)
    amount_cents: int = Field(ge=1, le=100000000)


def lock(session):
    if session.get_bind().dialect.name == 'sqlite': session.execute(text('BEGIN IMMEDIATE'))


def decimal_coin(value):
    number = Decimal(str(value))
    if not number.is_finite() or number < 0: raise HTTPException(409, '账户余额异常，请联系管理员')
    return number.quantize(Decimal('.000001'))


def tiers(game):
    try:
        amounts = [Decimal(x.strip()) for x in game.tixian_price.split(',')]
        coins = [Decimal(x.strip()) for x in game.tixian_coin.split(',')]
        if len(amounts) != len(coins) or not amounts: raise ValueError()
        result = []
        for amount, coin in zip(amounts, coins):
            if not amount.is_finite() or not coin.is_finite() or amount <= 0 or coin <= 0:
                raise ValueError()
            if amount * 100 != (amount * 100).to_integral_value() or coin != coin.quantize(Decimal('.000001')):
                raise ValueError()
            if amount > 1000000 or coin > 100000000000: raise ValueError()
            result.append({'amount_cents': int(amount * 100), 'coin_cost': str(coin)})
        if len({x['amount_cents'] for x in result}) != len(result): raise ValueError()
        return result
    except (ValueError, InvalidOperation):
        raise HTTPException(409, '游戏提现档位未正确配置') from None


def mask(account):
    return account[:2] + '***' + account[-2:]


def payout_payload(payout):
    return {'state': payout.state, 'amount_cents': payout.amount_cents, 'coin_cost': str(payout.coin_cost),
            'out_biz_no': payout.out_biz_no, 'provider_order_id': payout.provider_order_id,
            'account_masked': mask(payout.account), 'error': payout.error}


def withdrawal_payload(session, item):
    result = m.serialize(item, list(item.__table__.columns.keys()))
    payout = session.scalar(select(Payout).where(Payout.withdrawal_id == item.id))
    result['payout'] = payout_payload(payout) if payout else None
    result['target_status'] = 4 if item.status == 2 else item.status
    return result


def app_payload(session, item):
    result = withdrawal_payload(session, item)
    for field in ['audit_operator_id', 'audit_operator_name', 'transfer_operator_id', 'transfer_operator_name', 'receive_tel']:
        result.pop(field, None)
    return result


def require_game(session, member, game_id):
    game = session.get(m.Game, game_id)
    agent = session.get(m.Agent, member.agent_id)
    if game is None or game.agent_id != member.agent_id: raise HTTPException(404, '游戏不存在')
    if game.id != member.game_id: raise HTTPException(403, '请在账号绑定的游戏中提现')
    if game.status != 1 or agent is None or agent.status != 1: raise HTTPException(403, '游戏或主体不可用')
    if not member.exchange_enable: raise HTTPException(403, '账户提现已停用')
    return game


@m.app_api.put('/me/alipay')
def bind_alipay(payload: BindAlipay, member: m.Member = Depends(m.require_app_member)):
    with m.SessionLocal() as session:
        lock(session)
        user = session.scalar(select(m.Member).where(m.Member.id == member.id).with_for_update())
        if user is None or user.status != 1 or not m.verify_password(payload.current_password, user.password_hash, user.password_salt):
            raise HTTPException(401, '请验证当前登录密码后绑定收款账号')
        if session.scalar(select(Payout.id).where(Payout.member_id == user.id,
            Payout.state.in_(['pending_review', 'queued', 'processing']))) is not None:
            raise HTTPException(409, '存在处理中提现，暂不能更换支付宝账号')
        account = session.get(AlipayAccount, user.id)
        if account is None:
            account = AlipayAccount(member_id=user.id)
            session.add(account)
        account.account, account.real_name = payload.account, payload.real_name
        session.commit()
        return {'data': {'account_masked': mask(account.account), 'real_name': account.real_name,
                         'identity_verified': False}, 'request_id': secrets.token_urlsafe(12)}


@m.app_api.get('/me/alipay')
def get_alipay(member: m.Member = Depends(m.require_app_member)):
    with m.SessionLocal() as session:
        account = session.get(AlipayAccount, member.id)
        return {'data': None if account is None else {'account_masked': mask(account.account),
            'real_name': account.real_name, 'identity_verified': False}, 'request_id': secrets.token_urlsafe(12)}


@m.app_api.get('/withdrawal-options')
def withdrawal_options(game_id: int = Query(ge=1), member: m.Member = Depends(m.require_app_member)):
    with m.SessionLocal() as session:
        game = require_game(session, member, game_id)
        return {'data': {'tiers': tiers(game), 'payment_available': m.configured_provider().available,
            'alipay_bound': session.get(AlipayAccount, member.id) is not None}, 'request_id': secrets.token_urlsafe(12)}


@m.app_api.post('/withdrawals', status_code=201)
def apply_withdrawal(payload: WithdrawalApply, member: m.Member = Depends(m.require_app_member)):
    with m.SessionLocal() as session:
        lock(session)
        user = session.scalar(select(m.Member).where(m.Member.id == member.id).with_for_update())
        if user is None or user.status != 1: raise m._app_auth_error()
        prior = session.scalar(select(Payout).where(Payout.member_id == user.id, Payout.request_key == payload.request_key))
        if prior:
            if prior.game_id != payload.game_id or prior.amount_cents != payload.amount_cents:
                raise HTTPException(409, '请求编号已用于其他提现内容')
            item = session.get(m.Withdrawal, prior.withdrawal_id)
            if item is None: raise HTTPException(410, '原提现记录已不存在')
            return {'data': app_payload(session, item), 'request_id': secrets.token_urlsafe(12)}
        m.require_payment_integration()
        game = require_game(session, user, payload.game_id)
        tier = next((x for x in tiers(game) if x['amount_cents'] == payload.amount_cents), None)
        if tier is None: raise HTTPException(422, '请选择有效的提现档位')
        account = session.get(AlipayAccount, user.id)
        if account is None: raise HTTPException(409, '请先绑定支付宝账号')
        _, day_start, day_end = m.subsidy_campaigns.day_bounds()
        count = session.scalar(select(func.count()).select_from(Payout).where(Payout.member_id == user.id,
            Payout.game_id == game.id, Payout.created_at >= day_start, Payout.created_at < day_end)) or 0
        if game.exchange_num <= 0 or count >= game.exchange_num: raise HTTPException(409, '已达到今日提现次数限制')
        if session.scalar(select(m.WithdrawalBlacklist.id).where(m.WithdrawalBlacklist.receive_name == account.real_name,
            m.WithdrawalBlacklist.receive_tel == account.account, m.WithdrawalBlacklist.status == 1)):
            raise HTTPException(403, '收款账号暂不支持提现')
        cost = Decimal(tier['coin_cost'])
        before = decimal_coin(user.coin)
        if before < cost: raise HTTPException(409, '可用金币不足')
        user.coin = float(before - cost)
        user.freeze_coin = float(decimal_coin(user.freeze_coin) + cost)
        item = m.Withdrawal(user_id=user.id, agent_id=user.agent_id, game_id=game.id,
            receive_name=account.real_name, receive_tel=account.account, exchange_value=payload.amount_cents / 100,
            exchange_type=1, status=0, plan_status=0, good_name='金币提现')
        session.add(item)
        session.flush()
        session.add(Payout(withdrawal_id=item.id, member_id=user.id, request_key=payload.request_key,
            game_id=game.id, amount_cents=payload.amount_cents, coin_cost=cost, account=account.account,
            real_name=account.real_name, out_biz_no='AM' + secrets.token_hex(20),
            provider_scope=getattr(m.configured_provider(), 'scope', ''), state='pending_review'))
        session.add(m.CoinLog(user_id=user.id, agent_id=user.agent_id, game_id=game.id,
            coin_before=float(before), coin=-float(cost), coin_after=user.coin, type=200, remark=f'提现冻结 #{item.id}'))
        session.commit()
        return {'data': app_payload(session, item), 'request_id': secrets.token_urlsafe(12)}


@m.app_api.get('/withdrawals')
def app_withdrawals(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                    member: m.Member = Depends(m.require_app_member)):
    with m.SessionLocal() as session:
        rows = session.scalars(select(m.Withdrawal).where(m.Withdrawal.user_id == member.id)
            .order_by(m.Withdrawal.id.desc()).offset(offset).limit(limit)).all()
        count = session.scalar(select(func.count()).select_from(m.Withdrawal).where(m.Withdrawal.user_id == member.id)) or 0
        return {'data': {'items': [app_payload(session, x) for x in rows], 'total': count, 'limit': limit, 'offset': offset},
                'request_id': secrets.token_urlsafe(12)}


@m.app_api.get('/withdrawals/{withdrawal_id}')
def app_withdrawal_detail(withdrawal_id: int, member: m.Member = Depends(m.require_app_member)):
    with m.SessionLocal() as session:
        item = session.scalar(select(m.Withdrawal).where(m.Withdrawal.id == withdrawal_id, m.Withdrawal.user_id == member.id))
        if item is None: raise HTTPException(404, '提现不存在')
        return {'data': app_payload(session, item), 'request_id': secrets.token_urlsafe(12)}


def release_funds(session, item, state='rejected'):
    payout = session.scalar(select(Payout).where(Payout.withdrawal_id == item.id).with_for_update())
    if payout is None: return  # imported historical records have no wallet hold
    if payout.state in ('rejected', 'failed'): return
    if state == 'rejected' and payout.state != 'pending_review': raise HTTPException(409, '支付处理中，不能驳回')
    user = session.scalar(select(m.Member).where(m.Member.id == payout.member_id).with_for_update())
    frozen, before = decimal_coin(user.freeze_coin), decimal_coin(user.coin)
    if frozen < payout.coin_cost: raise HTTPException(409, '冻结余额异常，需人工核对')
    user.freeze_coin = float(frozen - payout.coin_cost)
    user.coin = float(before + payout.coin_cost)
    payout.state = state
    session.add(m.CoinLog(user_id=user.id, agent_id=item.agent_id, game_id=item.game_id,
        coin_before=float(before), coin=float(payout.coin_cost), coin_after=user.coin, type=201, remark=f'提现退回 #{item.id}'))


def record_result(withdrawal_id, result):
    with m.SessionLocal() as session:
        lock(session)
        item = session.scalar(select(m.Withdrawal).where(m.Withdrawal.id == withdrawal_id).with_for_update())
        payout = session.scalar(select(Payout).where(Payout.withdrawal_id == withdrawal_id).with_for_update())
        if payout.state in ('succeeded', 'failed', 'rejected'): return withdrawal_payload(session, item)
        payout.error = result.message[:512]
        payout.next_query_at = m.now() + timedelta(seconds=60)
        if result.state == 'succeeded':
            user = session.scalar(select(m.Member).where(m.Member.id == payout.member_id).with_for_update())
            frozen = decimal_coin(user.freeze_coin)
            if frozen < payout.coin_cost: raise HTTPException(409, '冻结余额异常，需人工核对')
            user.freeze_coin = float(frozen - payout.coin_cost)
            payout.state = 'succeeded'
            payout.provider_order_id = result.order_id
            item.plan_status = 1
            item.transferred_at = m.now()
            payout.error = ''
            # Available coin was debited at application time; only clear hold.
            session.add(m.CoinLog(user_id=user.id, agent_id=item.agent_id, game_id=item.game_id,
                coin_before=user.coin, coin=0, coin_after=user.coin, type=202, remark=f'提现到账 #{item.id}'))
        elif result.state == 'failed':
            release_funds(session, item, 'failed')
            item.plan_status = 0
            item.sub_msg = result.message[:255]
        session.commit()
        return withdrawal_payload(session, item)


def transfer(withdrawal_id, admin, query_only=False, scheduled=False, retry=False):
    provider = m.configured_provider()
    m.require_payment_integration()
    with m.SessionLocal() as session:
        lock(session)
        item = session.scalar(select(m.Withdrawal).where(m.Withdrawal.id == withdrawal_id).with_for_update())
        if item is None: raise HTTPException(404, '提现不存在')
        if item.status != 1: raise HTTPException(409, '请先审核通过')
        payout = session.scalar(select(Payout).where(Payout.withdrawal_id == item.id).with_for_update())
        if payout is None: raise HTTPException(409, '历史提现没有资金冻结订单，不能自动打款')
        if payout.provider_scope != getattr(provider, 'scope', ''):
            raise HTTPException(409, '支付宝应用或环境与原订单不同，请恢复原配置后处理')
        if payout.state in ('succeeded', 'failed', 'rejected'): return withdrawal_payload(session, item)
        if query_only and payout.state not in ('processing',): return withdrawal_payload(session, item)
        send = payout.state in ('pending_review', 'queued') and not query_only
        if send:
            user = session.get(m.Member, payout.member_id)
            if user is None or user.status != 1 or not user.exchange_enable:
                raise HTTPException(409, '用户状态不允许打款，请人工核对')
            if session.scalar(select(m.WithdrawalBlacklist.id).where(m.WithdrawalBlacklist.receive_name == payout.real_name,
                m.WithdrawalBlacklist.receive_tel == payout.account, m.WithdrawalBlacklist.status == 1)):
                raise HTTPException(409, '收款账号已列入黑名单，请人工核对')
        if scheduled and send:
            payout.state = 'queued'
            item.plan_status = 2
            payout.next_query_at = m.now()
        else:
            payout.state = 'processing'
            item.plan_status = 2
            payout.next_query_at = m.now() + timedelta(seconds=60)
        if admin:
            item.transfer_operator_id = admin.id
            item.transfer_operator_name = m.operator_display_name(admin)
            session.add(m.AdminOperation(admin_id=admin.id, title=f'支付宝提现{"查询" if query_only else "转账"} #{item.id}',
                path=f'/api/v1/withdrawals/{item.id}/transfer', ip=''))
        session.commit()
        if scheduled: return withdrawal_payload(session, item)
        order = dict(out_biz_no=payout.out_biz_no, amount_cents=payout.amount_cents, account=payout.account, real_name=payout.real_name)
    # Network calls occur outside the transaction. A crash leaves a durable
    # processing order, which the reconciler queries using the SAME out_biz_no.
    result = provider.send(order) if send else provider.query(order)
    if retry and not send and result.state == 'not_found':
        result = provider.send(order)  # same immutable merchant order number
    return record_result(withdrawal_id, result)


def batch_transfer(ids, admin, scheduled=False):
    if not ids: raise HTTPException(422, '请选择提现记录')
    ids = list(dict.fromkeys(ids))
    if len(ids) > 100: raise HTTPException(422, '每批最多100条')
    with m.SessionLocal() as session:
        rows = session.scalars(select(m.Withdrawal).where(m.Withdrawal.id.in_(ids))).all()
        if len(rows) != len(ids): raise HTTPException(404, '提现不存在')
        if any(x.status != 1 for x in rows): raise HTTPException(409, '只能转账已审核提现')
    m.require_payment_integration()
    results, errors = [], []
    for wid in ids:
        try: results.append(transfer(wid, admin, scheduled=scheduled))
        except HTTPException as exc: errors.append({'id': wid, 'detail': exc.detail})
    return {'updated': len(results), 'items': results, 'errors': errors, 'payment_provider': 'alipay',
            'payment_confirmed': not errors and all(x['payout']['state'] == 'succeeded' for x in results)}


@m.api.post('/withdrawals/{withdrawal_id}/query-transfer')
def query_transfer(withdrawal_id: int, admin: m.AdminUser = Depends(m.allow_roles('reviewer'))):
    return transfer(withdrawal_id, admin, query_only=True)


@m.api.post('/withdrawals/{withdrawal_id}/retry-transfer')
def retry_transfer(withdrawal_id: int, admin: m.AdminUser = Depends(m.allow_roles('reviewer'))):
    return transfer(withdrawal_id, admin, retry=True)


@m.app.post('/api/payments/alipay/notify')
async def alipay_notify(request: Request):
    from urllib.parse import parse_qsl
    from fastapi.responses import PlainTextResponse
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > 65536: return PlainTextResponse('failure', status_code=413)
        raw.extend(chunk)
    try:
        pairs = parse_qsl(raw.decode('utf-8'), keep_blank_values=True, max_num_fields=100)
        params = dict(pairs)
        if len(params) != len(pairs): raise ValueError()
    except (ValueError, UnicodeError):
        return PlainTextResponse('failure', status_code=400)
    provider = m.configured_provider()
    if not provider.available or not provider.verify_notification(params):
        return PlainTextResponse('failure', status_code=400)
    with m.SessionLocal() as session:
        payout = session.scalar(select(Payout).where(Payout.out_biz_no == params.get('out_biz_no', '')))
        if payout is None: return PlainTextResponse('failure', status_code=404)
        wid = payout.withdrawal_id
    # The callback only triggers an authenticated query. Its amount or status
    # never directly changes the wallet.
    result = transfer(wid, None, query_only=True)
    confirmed = result['payout']['state'] in ('succeeded', 'failed', 'rejected')
    return PlainTextResponse('success' if confirmed else 'failure')


@m.api.get('/payment-status')
def payment_status(admin: m.AdminUser = Depends(m.require_admin)):
    provider = m.configured_provider()
    return {'provider': provider.name, 'available': provider.available, 'environment': getattr(provider, 'environment', ''),
            'detail': getattr(provider, 'configuration_error', '')}
