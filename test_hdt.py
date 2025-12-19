"""检查数据库中的数据"""
import sys
sys.path.insert(0, '.')

from app.database import SessionLocal
from app.models import ArenaCardStats

db = SessionLocal()

# 查询总数
total = db.query(ArenaCardStats).count()
print(f"arena_card_stats 表中总记录数: {total}")

# 查看几条样例数据
samples = db.query(ArenaCardStats).limit(5).all()
for s in samples:
    print(f"card_id={s.card_id}, class={s.card_class}, win_rate={s.win_rate}")

db.close()
