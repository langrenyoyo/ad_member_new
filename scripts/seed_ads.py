"""Append deterministic advertisement records for list/filter/export testing."""
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.main_from_txt import AdRecord, SessionLocal  # noqa: E402

def main(count=50):
    with SessionLocal() as db:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = []
        for i in range(count):
            rows.append(AdRecord(
                parent_id=1, parent_payment_name="测试主体", user_id=1000 + i % 10,
                user_account=f"test_user_{i % 10:02d}", agent_id=1, game_id=1,
                game_name="测试游戏", receive_name="测试用户", ecpm=1.5 + i % 7,
                coin=10 + i, estimate_income=round((10 + i) * 0.01, 2),
                ad_network_platform_name="测试广告平台", is_lottery=i % 2,
                is_rw=1, reward_type="领取", ad_type="激励视频",
                sub_ad_type="", ad_group="主广" if i % 3 else "副广",
                is_type=0, is_fu=i % 3 == 0, fu_type=1, is_look=1,
                status="成功" if i % 5 else "失败", watched_at=now - timedelta(hours=i),
                ad_code=f"TEST-CODE-{i:04d}", request_id=f"TEST-REQ-{i:04d}",
                trans_id=f"TEST-TRANS-{i:04d}"))
        db.add_all(rows)
        db.commit()
        print(f"inserted {len(rows)} ad records")

if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 50)
