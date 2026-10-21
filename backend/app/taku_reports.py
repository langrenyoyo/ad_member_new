"""Versioned, read-only revenue reconciliation. Never changes wallet balances."""
import csv
import hashlib
import io
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column
from . import main_from_txt as m

CN = timezone(timedelta(hours=8))


class ReportBatch(m.Base, m.TimestampMixin):
    __tablename__ = 'taku_report_batches'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(Integer, index=True)
    day: Mapped[str] = mapped_column(String(10), index=True)
    digest: Mapped[str] = mapped_column(String(64))
    stage: Mapped[str] = mapped_column(String(20))
    rows_json: Mapped[str] = mapped_column(Text)
    admin_id: Mapped[int] = mapped_column(Integer)


class ReportRule(m.Base, m.TimestampMixin):
    __tablename__ = 'taku_report_rules'
    game_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    config_json: Mapped[str] = mapped_column(Text)


class RuleInput(BaseModel):
    basis: str = Field(default='backend_estimate', pattern='^(backend_estimate|taku_estimate)$')
    threshold_percent: Decimal = Field(default=Decimal('20'), ge=0, le=100, allow_inf_nan=False)
    min_estimate: Decimal = Field(default=Decimal('0.01'), ge=0, le=1000000, allow_inf_nan=False)
    min_impressions: int = Field(default=3, ge=1, le=1000000)


class ImportInput(BaseModel):
    day: date
    csv_text: str = Field(min_length=1, max_length=5_000_000)
    stage: str = Field(default='preliminary', pattern='^(preliminary|rechecked)$')


def number(value):
    try:
        result = Decimal(str(value).strip())
        if not result.is_finite() or result < 0 or result > Decimal('1e15'):
            raise ValueError()
        return result
    except (InvalidOperation, ValueError):
        raise HTTPException(422, '报表金额或展示数无效') from None


def parse_report(text):
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    required = {'user_id', 'placement_id', 'network_firm_id', 'impression', 'revenue', 'currency'}
    if not required.issubset(reader.fieldnames or []):
        raise HTTPException(422, '需要设备明细 CSV：user_id/placement_id/network_firm_id/impression/revenue/currency')
    groups = {}
    for index, row in enumerate(reader):
        if index >= 100000 or None in row or any(v is None for v in row.values()):
            raise HTTPException(422, '报表行格式不完整或超过十万行')
        currency = row['currency'].strip().upper()
        if currency not in ('CNY', 'USD'):
            raise HTTPException(422, '仅支持明确的 CNY/USD，不能自动猜测币种')
        price_field = 'cny_estimate_revenue' if currency == 'CNY' else 'estimate_revenue'
        estimate = number(row[price_field]) if row.get(price_field, '').strip() else None
        count = number(row['impression'])
        if count != count.to_integral_value():
            raise HTTPException(422, '展示数必须为整数')
        identity = row['user_id'].strip()
        # Preserve ambiguity, but do not persist raw advertising device identifiers.
        device = next((row.get(k, '').strip() for k in ('oaid', 'android_id', 'idfa', 'gaid') if row.get(k, '').strip()), '')
        device_hash = hashlib.sha256(device.encode()).hexdigest() if device else ''
        key = (identity, row['placement_id'].strip(), row['network_firm_id'].strip(), currency)
        if any(len(v) > 255 for v in key):
            raise HTTPException(422, '报表标识过长')
        g = groups.setdefault(key, dict(user_id=identity, placement_id=key[1], network_id=key[2], currency=currency,
            impressions=0, revenue=Decimal(0), estimate=Decimal(0), missing_estimate=False, devices=set()))
        g['impressions'] += int(count)
        g['revenue'] += number(row['revenue'])
        g['missing_estimate'] |= estimate is None
        g['estimate'] += estimate or Decimal(0)
        if device_hash:
            g['devices'].add(device_hash)
    if not groups:
        raise HTTPException(422, '空报表不能用于清除已有异常标记')
    return [{**g, 'revenue': str(g['revenue']), 'estimate': str(g['estimate']), 'devices': sorted(g['devices'])} for g in groups.values()]


def evaluate(rows, members, rule, stage):
    owners = {}
    for r in rows:
        for d in r['devices']:
            owners.setdefault(d, set()).add(r['user_id'])
    results = []
    for row in rows:
        r = {k: v for k, v in row.items() if k != 'devices'}
        uid = row['user_id']
        member_id = int(uid) if uid.isascii() and uid.isdecimal() and len(uid) < 19 else None
        r['member_id'] = member_id if member_id in members else None
        estimate, revenue = Decimal(row['estimate']), Decimal(row['revenue'])
        r.update(difference=str(estimate-revenue), reduction_percent=None, flagged=False)
        if r['member_id'] is None:
            r['status'] = 'unmatched'
        elif any(len(owners[d]) > 1 for d in row['devices']):
            r['status'] = 'shared_device_review'
        elif row['missing_estimate']:
            r['status'] = 'missing_estimate'
        elif estimate <= 0 or estimate < rule.min_estimate or row['impressions'] < rule.min_impressions:
            r['status'] = 'insufficient_sample'
        else:
            rate = (estimate-revenue) / estimate * 100
            r['reduction_percent'] = str(rate)
            r['flagged'] = rate > rule.threshold_percent
            r['status'] = ('preliminary_alert' if stage == 'preliminary' else 'suspected_reduction') if r['flagged'] else 'normal'
        results.append(r)
    return results


@m.api.get('/games/{game_id}/taku-reports/rule')
def get_rule(game_id: int, admin=Depends(m.allow_roles('superadmin'))):
    with m.SessionLocal() as s:
        m.get_or_404(s, m.Game, game_id, '游戏')
        rule = s.get(ReportRule, game_id)
        return RuleInput.model_validate_json(rule.config_json) if rule else RuleInput()


@m.api.put('/games/{game_id}/taku-reports/rule')
def save_rule(game_id: int, body: RuleInput, admin=Depends(m.allow_roles('superadmin'))):
    with m.SessionLocal() as s:
        m.get_or_404(s, m.Game, game_id, '游戏')
        m.device_risk.game_lock(s, game_id)
        row = s.get(ReportRule, game_id)
        if row is None:
            row = ReportRule(game_id=game_id)
            s.add(row)
        row.config_json = body.model_dump_json()
        s.add(m.AdminOperation(admin_id=admin.id, title='更新 TAKU 对账阈值 '+body.model_dump_json(), path='/taku-reports/rule', ip=''))
        s.commit()
    return body


@m.api.post('/games/{game_id}/taku-reports/import')
def import_report(game_id: int, body: ImportInput, admin=Depends(m.allow_roles('superadmin'))):
    today = datetime.now(CN).date()
    if body.day >= today or (today-body.day).days > 30:
        raise HTTPException(422, '请选择最近三十天内已结束的日期，时区 UTC+8')
    if body.stage == 'rechecked' and datetime.now(CN) < datetime.combine(body.day+timedelta(days=2), datetime.min.time(), CN)+timedelta(hours=4):
        raise HTTPException(422, '尚未到 D+2 04:00，请作为初步报表导入')
    rows = parse_report(body.csv_text)
    digest = hashlib.sha256(body.csv_text.encode()).hexdigest()
    with m.SessionLocal() as s:
        m.get_or_404(s, m.Game, game_id, '游戏')
        m.device_risk.game_lock(s, game_id)
        latest = s.scalar(select(ReportBatch).where(ReportBatch.game_id == game_id, ReportBatch.day == str(body.day)).order_by(ReportBatch.id.desc()))
        if latest and latest.digest == digest and latest.stage == body.stage:
            return {'batch_id': latest.id, 'imported': False}
        if latest and latest.stage == 'rechecked' and body.stage == 'preliminary':
            raise HTTPException(409, '不能以初步报表覆盖已复核版本')
        batch = ReportBatch(game_id=game_id, day=str(body.day), digest=digest, stage=body.stage,
            rows_json=json.dumps(rows), admin_id=admin.id)
        s.add(batch)
        s.add(m.AdminOperation(admin_id=admin.id, title=f'导入 TAKU 对账 {game_id} {body.day} {digest[:12]}', path='/taku-reports/import', ip=''))
        s.commit()
        return {'batch_id': batch.id, 'imported': True}


@m.api.get('/games/{game_id}/taku-reports')
def results(game_id: int, day: date, member_id: int | None = None, admin=Depends(m.allow_roles('superadmin'))):
    with m.SessionLocal() as s:
        m.get_or_404(s, m.Game, game_id, '游戏')
        batch = s.scalar(select(ReportBatch).where(ReportBatch.game_id == game_id, ReportBatch.day == str(day)).order_by(ReportBatch.id.desc()))
        if batch is None:
            return {'status': 'waiting_report', 'items': [], 'flagged_members': []}
        config = s.get(ReportRule, game_id)
        rule = RuleInput.model_validate_json(config.config_json) if config else RuleInput()
        members = set(s.scalars(select(m.Member.id).where(m.Member.game_id == game_id)))
        rows = json.loads(batch.rows_json)
        # Compare all networks within the same user/placement/currency scope.
        combined = {}
        for r in rows:
            key = (r['user_id'], r['placement_id'], r['currency'])
            if key not in combined:
                combined[key] = {**r, 'network_id': 'all', 'devices': set(r['devices'])}
            else:
                v = combined[key]
                for field in ('estimate', 'revenue'):
                    v[field] = str(Decimal(v[field])+Decimal(r[field]))
                v['impressions'] += r['impressions']
                v['missing_estimate'] |= r['missing_estimate']
                v['devices'].update(r['devices'])
        local = local_estimates(s, game_id, day)
        for key, r in combined.items():
            r['taku_estimate'] = r['estimate']
            entry = local.get(key)
            r['backend_estimate'] = str(entry['revenue']) if entry else None
            r['backend_impressions'] = entry['count'] if entry else 0
            if rule.basis == 'backend_estimate':
                r['estimate'] = r['backend_estimate'] or '0'
                # Missing SDK prices or mismatched scope must not become a deduction.
                r['missing_estimate'] = not entry or entry['missing'] or entry['count'] != r['impressions']
        items = evaluate(list(combined.values()), members, rule, batch.stage)
        if member_id is not None:
            items = [r for r in items if r['member_id'] == member_id]
        return {'status': batch.stage, 'batch_id': batch.id, 'day': batch.day, 'rule': rule.model_dump(mode='json'),
            'basis': rule.basis, 'items': items,
            'flagged_members': sorted({r['member_id'] for r in items if r['flagged']}),
            'updated_at': m.stringify(batch.created_at)}


def local_estimates(s, game_id, day):
    start = datetime.combine(day, datetime.min.time(), CN).astimezone(timezone.utc)
    ads = s.scalars(select(m.AppAdSession).where(m.AppAdSession.game_id == game_id,
        m.AppAdSession.provider == 'taku', m.AppAdSession.impressed_at >= start,
        m.AppAdSession.impressed_at < start+timedelta(days=1))).all()
    output = {}
    events = dict(s.execute(select(m.AppAdEvent.ad_session_id, m.AppAdEvent.result_json).join(
        m.AppAdSession, m.AppAdSession.id == m.AppAdEvent.ad_session_id).where(
        m.AppAdSession.game_id == game_id, m.AppAdSession.provider == 'taku',
        m.AppAdSession.impressed_at >= start, m.AppAdSession.impressed_at < start+timedelta(days=1),
        m.AppAdEvent.event_type == 'client_metadata',
        m.AppAdEvent.event_id == 'metadata:' + m.AppAdSession.id + ':shown')).all())
    for ad in ads:
        data = json.loads(events.get(ad.id, '{}'))
        proof = data.get('revenue_diagnostic', {})
        prices = {p['currency']: p for p in proof.get('prices', [])} if proof.get('status') == 'decrypted' else {}
        for currency in ('CNY', 'USD'):
            key = (str(ad.member_id), ad.ad_unit_id, currency)
            value = output.setdefault(key, {'revenue': Decimal(0), 'count': 0, 'missing': False})
            value['count'] += 1
            p = prices.get(currency)
            if p:
                value['revenue'] += Decimal(p['ecpm']) / 1000
            else:
                value['missing'] = True
    return output
