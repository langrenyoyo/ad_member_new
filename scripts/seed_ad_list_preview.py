"""Create isolated ad-list fixtures without reward or wallet side effects.

Use the deployment environment and an explicit --commit to write records.
The batch is immutable: reusing a batch marker is rejected.
"""
import argparse
from collections import Counter
from datetime import timedelta
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app import main_from_txt as m  # noqa: E402
from sqlalchemy import func, select  # noqa: E402


SOURCE_MEMBER_BATCH = "TEST-20261029-YZ"
COUNT = 120
PLATFORMS = ("TEST-TAKU", "TEST-GDT", "TEST-KS")
SECONDARY_TYPES = ((1, "开屏", "开屏广告"), (2, "Banner", "Banner"),
                   (3, "插屏", "插屏"), (4, "信息流", "信息流"))


def build_rows(game, members, marker):
    current = m.now().replace(tzinfo=None)
    today = (current + timedelta(hours=8)).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(hours=8)
    rows = []
    for i in range(COUNT):
        # 36 rows each for today and yesterday; the rest cover the previous week.
        if i < 36:
            watched_at = today + (current - today) * ((i + 1) / 37)
        elif i < 72:
            yesterday = today - timedelta(days=1)
            watched_at = yesterday + (today - yesterday) * ((i - 35) / 37)
        else:
            watched_at = current - timedelta(days=2 + (i % 6), minutes=i * 7)

        member = members[i % len(members)]
        is_secondary = i % 3 != 0
        is_success = i % 5 != 0
        if is_secondary:
            fu_type, sub_ad_type, ad_type = SECONDARY_TYPES[(i // 3) % len(SECONDARY_TYPES)]
            ad_group = "副广"
        else:
            fu_type, sub_ad_type, ad_type = 1, "", "激励"
            ad_group = "主广"

        # Deliberately varied evidence states for the operations columns.
        price_case = i % 4
        client_ecpm = None if price_case == 0 else round(18.0 + (i % 17) * 1.25, 4)
        callback_ecpm = None if price_case in (0, 1) else round(
            client_ecpm if price_case == 2 else client_ecpm * 0.72, 4
        )
        currency = "" if price_case == 0 else "CNY"
        ecpm = callback_ecpm if callback_ecpm is not None else (client_ecpm or 0.0)
        tags = [{
            "code": "synthetic_preview",
            "label": "模拟测试数据（非真实收益、未发奖）",
            "level": "info",
        }]
        if price_case == 3:
            tags.append({"code": "synthetic_price_difference", "label": "模拟价格差异样例", "level": "warning"})
        if i % 11 == 0:
            tags.append({"code": "synthetic_cross_region", "label": "模拟跨区样例", "level": "info"})

        rows.append(m.AdRecord(
            parent_id=member.parent_id or 0,
            parent_payment_name="",
            user_id=member.id,
            user_account=member.username,
            agent_id=game.agent_id,
            game_id=game.id,
            game_name=game.name,
            receive_name=member.name or "测试会员",
            ecpm=ecpm,
            coin=0,
            estimate_income=0,
            ad_network_platform_name=PLATFORMS[i % len(PLATFORMS)],
            is_lottery=int(i % 10 == 0),
            is_rw=0,
            reward_type="模拟未发奖",
            ad_type=ad_type,
            sub_ad_type=sub_ad_type,
            ad_group=ad_group,
            is_type=0,
            is_fu=int(is_secondary),
            fu_type=fu_type,
            is_look=int(is_success),
            status="成功" if is_success else "失败",
            watched_at=watched_at,
            ad_code=f"{marker}-SLOT-{i % 12 + 1:02}",
            request_id=f"{marker}-REQ-{i + 1:04}",
            trans_id=f"{marker}-TRANS-{i + 1:04}",
            client_ecpm=client_ecpm,
            callback_ecpm=callback_ecpm,
            settlement_ecpm=None,
            callback_price_currency=currency,
            attention_count=i % 5,
            gps_ip_cross_region=int(i % 11 == 0),
            risk_tags_json=json.dumps(tags, ensure_ascii=False),
            created_at=watched_at,
        ))
    return rows


def seed(batch, game_id, commit):
    if not re.fullmatch(r"[A-Za-z0-9-]{1,24}", batch):
        raise ValueError("Batch must contain 1-24 ASCII letters, digits or hyphens")
    marker = "TEST-" + batch
    manifest = {
        "batch": marker,
        "synthetic": True,
        "game_id": game_id,
        "source_member_batch": SOURCE_MEMBER_BATCH,
        "record_count": COUNT,
        "committed": bool(commit),
        "tables": {},
    }

    with m.SessionLocal() as db:
        game = db.get(m.Game, game_id)
        if game is None:
            raise RuntimeError("Target game does not exist")
        members = db.scalars(select(m.Member).where(
            m.Member.game_id == game_id,
            m.Member.username.startswith(SOURCE_MEMBER_BATCH + "-"),
        ).order_by(m.Member.id)).all()
        if len(members) < 30:
            raise RuntimeError("Expected the existing batch of disabled preview members")
        if any(x.agent_id != game.agent_id or x.is_true != 1 or x.status != 0 or
               bool(x.exchange_enable) or float(x.coin or 0) != 0 for x in members):
            raise RuntimeError("Source members must remain disabled, internal, and zero-balance")

        existing = db.scalar(select(func.count(m.AdRecord.id)).where(
            m.AdRecord.game_id == game_id,
            m.AdRecord.request_id.startswith(marker + "-"),
        ))
        if existing:
            raise RuntimeError("Batch already exists; no data changed")

        member_ids = [x.id for x in members]
        wallet_before = {
            "coin_sum": float(db.scalar(select(func.coalesce(func.sum(m.Member.coin), 0)).where(m.Member.id.in_(member_ids))) or 0),
            "freeze_coin_sum": float(db.scalar(select(func.coalesce(func.sum(m.Member.freeze_coin), 0)).where(m.Member.id.in_(member_ids))) or 0),
            "coin_log_count": int(db.scalar(select(func.count(m.CoinLog.id)).where(m.CoinLog.user_id.in_(member_ids))) or 0),
        }
        rows = build_rows(game, members, marker)
        stats = {
            "by_status": dict(Counter(row.status for row in rows)),
            "by_ad_group": dict(Counter(row.ad_group for row in rows)),
            "by_platform": dict(Counter(row.ad_network_platform_name for row in rows)),
            "with_callback_ecpm": sum(row.callback_ecpm is not None for row in rows),
            "with_client_ecpm": sum(row.client_ecpm is not None for row in rows),
        }
        manifest.update(game_name=game.name, member_count=len(members), stats=stats,
                        wallet_before=wallet_before)
        if not commit:
            manifest["preview"] = "No database changes made"
            return manifest

        db.add_all(rows)
        db.flush()
        manifest["tables"] = {"ad_records": {
            "primary_key": "id",
            "ids": [row.id for row in rows],
            "request_id_prefix": marker + "-REQ-",
        }}
        wallet_after = {
            "coin_sum": float(db.scalar(select(func.coalesce(func.sum(m.Member.coin), 0)).where(m.Member.id.in_(member_ids))) or 0),
            "freeze_coin_sum": float(db.scalar(select(func.coalesce(func.sum(m.Member.freeze_coin), 0)).where(m.Member.id.in_(member_ids))) or 0),
            "coin_log_count": int(db.scalar(select(func.count(m.CoinLog.id)).where(m.CoinLog.user_id.in_(member_ids))) or 0),
        }
        if wallet_after != wallet_before:
            raise RuntimeError("Wallet data changed unexpectedly; transaction rolled back")
        manifest["wallet_after"] = wallet_after
        db.commit()
        return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", required=True)
    parser.add_argument("--game-id", type=int, required=True)
    parser.add_argument("--commit", action="store_true", help="Persist records; without this flag only validate")
    args = parser.parse_args()
    print(json.dumps(seed(args.batch, args.game_id, args.commit), ensure_ascii=False, indent=2))
