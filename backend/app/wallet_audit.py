"""Read-only reconciliation: findings require review, never automatic adjustments."""
import json
from decimal import Decimal, InvalidOperation
from sqlalchemy import select, func, inspect, text
from . import main_from_txt as m


def reconcile(session):
    findings = []
    def number(value):
        return Decimal(str(value or 0))
    members = session.scalars(select(m.Member).order_by(m.Member.id)).all()
    audit_rewards(session, findings)
    for log in session.scalars(select(m.CoinLog).where(~select(m.Member.id).where(m.Member.id == m.CoinLog.user_id).exists())):
        findings.append({'kind':'orphan_ledger','log_id':log.id,'member_id':log.user_id})
        if number(log.coin_before) + number(log.coin) != number(log.coin_after):
            findings.append({'kind':'ledger_equation','log_id':log.id,'member_id':log.user_id})
    valid_states = {'pending_review', 'queued', 'processing', 'succeeded', 'failed', 'rejected'}
    for payout in session.scalars(select(m.payouts.Payout)):
        member = session.get(m.Member, payout.member_id)
        withdrawal = session.get(m.Withdrawal, payout.withdrawal_id)
        if member is None:
            findings.append({'kind':'orphan_payout','payout_id':payout.id,'member_id':payout.member_id})
        if withdrawal is None:
            findings.append({'kind':'missing_withdrawal','payout_id':payout.id})
        elif withdrawal.user_id != payout.member_id or withdrawal.game_id != payout.game_id:
            findings.append({'kind':'payout_owner_mismatch','payout_id':payout.id})
        if payout.state not in valid_states:
            findings.append({'kind':'unknown_payout_state','payout_id':payout.id,'state':payout.state})
    total_available = total_frozen = Decimal(0)
    for member in members:
        available, frozen = number(member.coin), number(member.freeze_coin)
        total_available += available
        total_frozen += frozen
        logs = session.scalars(select(m.CoinLog).where(m.CoinLog.user_id == member.id).order_by(m.CoinLog.id)).all()
        previous = None
        for log in logs:
            before, change, after = map(number, (log.coin_before, log.coin, log.coin_after))
            if before + change != after:
                findings.append({'kind':'ledger_equation', 'member_id':member.id, 'log_id':log.id,
                    'difference':str(after-before-change)})
            if previous is not None and before != previous:
                findings.append({'kind':'ledger_chain', 'member_id':member.id, 'log_id':log.id,
                    'difference':str(before-previous)})
            previous = after
        if previous is not None and previous != available:
            findings.append({'kind':'wallet_vs_latest_log','member_id':member.id,'difference':str(available-previous)})
        if not logs and available != 0:
            findings.append({'kind':'opening_balance_without_ledger','member_id':member.id,'amount':str(available)})
        held = number(session.scalar(select(func.sum(m.payouts.Payout.coin_cost)).where(
            m.payouts.Payout.member_id == member.id,
            m.payouts.Payout.state.not_in(['succeeded','failed','rejected']))))
        if held != frozen:
            findings.append({'kind':'frozen_vs_payouts','member_id':member.id,'difference':str(frozen-held)})
        if available < 0 or frozen < 0:
            findings.append({'kind':'negative_balance','member_id':member.id})
    archived_changes = 0
    if 'wallet_decimal_migration_values' in inspect(session.get_bind()).get_table_names():
        for original, converted in session.execute(text('SELECT original_value, decimal_value FROM wallet_decimal_migration_values')):
            if number(original) != number(converted): archived_changes += 1
    return {'read_only':True,'member_count':len(members),'available_coin':str(total_available),
        'frozen_coin':str(total_frozen),'migration_changed_fields':archived_changes,
        'findings':findings,'passed':not findings}


def audit_rewards(session, findings):
    """Explicit links for new entries; conservative matching for legacy commissions."""
    p = m.member_policy
    used = {}
    rewards_by_ad = {}
    for ledger in session.scalars(select(p.RewardLedger).order_by(p.RewardLedger.id)):
        def issue(kind):
            findings.append({'kind':kind,'reward_ledger_id':ledger.id,'ad_session_id':ledger.ad_session_id})
        ad = session.get(m.AppAdSession, ledger.ad_session_id)
        if ad is None:
            issue('reward_missing_ad')
        elif ad.member_id != ledger.member_id or ad.game_id != ledger.game_id or ad.status != 'rewarded':
            issue('reward_ad_mismatch')
        beneficiary = session.get(m.Member, ledger.beneficiary_id)
        if beneficiary is None or beneficiary.game_id != ledger.game_id:
            issue('reward_beneficiary_mismatch')
        if ledger.kind == 'reward':
            rewards_by_ad.setdefault(ledger.ad_session_id, []).append(ledger.id)
            try:
                ledger_snapshot = json.loads(ledger.rule_json or '{}')
                if not isinstance(ledger_snapshot, dict):
                    raise ValueError('Reward snapshot must be an object')
                if ledger_snapshot.get('commission_audit_version') == 1 and 'commission_outcomes' not in ledger_snapshot:
                    raise ValueError('Commission outcomes are missing')
                outcomes = ledger_snapshot.get('commission_outcomes', [])
                if not isinstance(outcomes, list):
                    raise ValueError('Commission outcomes must be a list')
                for outcome in outcomes:
                    if not isinstance(outcome, dict):
                        raise ValueError('Commission outcome must be an object')
                    beneficiary_id = int(outcome['beneficiary_id'])
                    amount = Decimal(str(outcome['amount']))
                    level = int(outcome['level'])
                    if (level not in range(4) or beneficiary_id <= 0 or not amount.is_finite()
                            or amount < 0 or not isinstance(outcome.get('eligible'), bool)):
                        raise ValueError('Invalid commission outcome')
                    if not outcome['eligible'] or amount == 0:
                        continue
                    expected_kind = f'commission_{level}'
                    match = session.scalar(select(p.RewardLedger).where(
                        p.RewardLedger.ad_session_id == ledger.ad_session_id,
                        p.RewardLedger.beneficiary_id == beneficiary_id,
                        p.RewardLedger.kind == expected_kind,
                        p.RewardLedger.amount == amount))
                    if match is None:
                        findings.append({'kind':'expected_commission_missing',
                            'reward_ledger_id':ledger.id,'ad_session_id':ledger.ad_session_id,
                            'beneficiary_id':beneficiary_id,'amount':str(amount)})
            except (ValueError, TypeError, KeyError, InvalidOperation):
                findings.append({'kind':'invalid_commission_outcomes','reward_ledger_id':ledger.id,
                    'ad_session_id':ledger.ad_session_id})
            if ledger.beneficiary_id != ledger.member_id: issue('reward_owner_mismatch')
            if ledger.coin_log_id is not None and ad and ledger.coin_log_id != ad.coin_log_id:
                issue('reward_log_link_mismatch')
            log_id = ledger.coin_log_id if ledger.coin_log_id is not None else (ad.coin_log_id if ad else None)
            logs = [session.get(m.CoinLog, log_id)] if log_id is not None else []
            expected_type = 1
        elif ledger.kind in {'commission_0','commission_1','commission_2','commission_3'}:
            expected_type = 301
            logs = [session.get(m.CoinLog, ledger.coin_log_id)] if ledger.coin_log_id is not None else session.scalars(
                select(m.CoinLog).where(m.CoinLog.user_id == ledger.beneficiary_id,
                    m.CoinLog.game_id == ledger.game_id, m.CoinLog.type == 301,
                    m.CoinLog.remark == f'广告分佣 {ledger.ad_session_id}')).all()
        else:
            issue('unknown_reward_kind'); continue
        logs = [log for log in logs if log is not None]
        if len(logs) != 1:
            issue('reward_missing_credit' if not logs else 'reward_ambiguous_credit'); continue
        log = logs[0]
        if log.user_id != ledger.beneficiary_id or log.game_id != ledger.game_id or log.type != expected_type or log.coin != ledger.amount:
            issue('reward_credit_mismatch')
        if log.id in used: issue('reward_reused_credit')
        used[log.id] = ledger.id
    for ad in session.scalars(select(m.AppAdSession).where(m.AppAdSession.status == 'rewarded')):
        log = session.get(m.CoinLog, ad.coin_log_id) if ad.coin_log_id is not None else None
        if log is None or log.user_id != ad.member_id or log.game_id != ad.game_id or log.type != 1:
            findings.append({'kind':'settled_ad_credit_mismatch','ad_session_id':ad.id})
        snapshot = session.scalar(select(m.AppAdEvent).where(m.AppAdEvent.event_id == 'policy:'+ad.id))
        if snapshot:
            try:
                captured = json.loads(snapshot.result_json)
                if not isinstance(captured, dict):
                    raise ValueError('Settlement snapshot must be an object')
                rule = p.Policy.model_validate(captured.get('rule', captured))
                enabled = rule.reward_enabled or (rule.commission_enabled if rule.commission_enabled is not None else rule.reward_enabled)
                if enabled and len(rewards_by_ad.get(ad.id, [])) != 1:
                    findings.append({'kind':'settled_ad_reward_ledger_missing','ad_session_id':ad.id})
            except (ValueError, TypeError):
                findings.append({'kind':'invalid_settlement_snapshot','ad_session_id':ad.id})
    for log in session.scalars(select(m.CoinLog).where(m.CoinLog.type == 301)):
        if log.id not in used: findings.append({'kind':'commission_without_ledger','log_id':log.id})
