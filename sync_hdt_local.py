"""
本地同步 HDT 竞技场胜率数据脚本

使用方法：
1. 在本地运行此脚本：python sync_hdt_local.py
2. 脚本会生成 arena_stats_data.json 文件
3. 将此文件上传到线上服务器的 app/static/uploads/ 目录
4. 在线上访问 /api/arena/import-json 接口导入数据
"""
import json
import httpx
from datetime import datetime

# 职业映射：HSReplay 英文 -> 中文（与 cards 表一致）
CLASS_MAP = {
    "ALL": "全部职业",
    "DEATHKNIGHT": "死亡骑士",
    "DRUID": "德鲁伊",
    "HUNTER": "猎人",
    "MAGE": "法师",
    "PALADIN": "圣骑士",
    "PRIEST": "牧师",
    "ROGUE": "潜行者",
    "SHAMAN": "萨满",
    "WARLOCK": "术士",
    "WARRIOR": "战士",
    "DEMONHUNTER": "恶魔猎手",
}


def main():
    print("=" * 50)
    print("HDT 竞技场胜率数据同步脚本")
    print("=" * 50)
    
    # 第一步：获取卡牌 ID 映射
    print("\n[1/3] 正在获取卡牌 ID 映射...")
    cards_url = "https://api.hearthstonejson.com/v1/latest/zhCN/cards.json"
    with httpx.Client(timeout=60.0) as client:
        resp = client.get(cards_url)
        resp.raise_for_status()
        cards_data = resp.json()
    
    card_dict = {}
    for card in cards_data:
        card_id_str = card.get("id")
        dbf_id = card.get("dbfId")
        if card_id_str and dbf_id:
            card_dict[card_id_str] = dbf_id
    
    print(f"   已获取 {len(card_dict)} 张卡牌的 ID 映射")
    
    # 第二步：获取 HSReplay 竞技场统计数据
    print("\n[2/3] 正在获取 HSReplay 竞技场统计数据...")
    stats_url = "https://hsreplay.net/api/v1/arena/card_stats/free/?ArenaTimestampRangeFilter=LAST_4_DAYS"
    with httpx.Client(timeout=60.0) as client:
        resp = client.get(stats_url)
        resp.raise_for_status()
        stats_data = resp.json()
    
    data_section = stats_data.get("data", {})
    print(f"   已获取 {len(data_section)} 个职业的数据")
    
    # 第三步：处理数据
    print("\n[3/3] 正在处理数据...")
    result_data = []
    skipped_count = 0
    
    for class_key, class_cards in data_section.items():
        card_class_cn = CLASS_MAP.get(class_key)
        if not card_class_cn:
            continue
        
        for card_stat in class_cards:
            card_id_str = card_stat.get("card_id")
            if not card_id_str:
                skipped_count += 1
                continue
            
            dbf_id = card_dict.get(card_id_str)
            if not dbf_id:
                skipped_count += 1
                continue
            
            result_data.append({
                "card_id": dbf_id,
                "popularity": card_stat.get("popularity"),
                "avg_copies_in_deck": card_stat.get("avg_copies_in_deck"),
                "win_rate": card_stat.get("win_rate"),
                "drawn_win_rate": card_stat.get("drawn_win_rate"),
                "played_win_rate": card_stat.get("played_win_rate"),
                "num_games": card_stat.get("num_games"),
                "card_class": card_class_cn,
            })
    
    print(f"   处理完成：{len(result_data)} 条记录，跳过 {skipped_count} 条")
    
    # 保存到文件
    output_file = "arena_stats_data.json"
    output = {
        "generated_at": datetime.utcnow().isoformat(),
        "total_count": len(result_data),
        "data": result_data,
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 数据已保存到 {output_file}")
    print(f"   文件大小：{len(json.dumps(output)) / 1024:.1f} KB")
    print("\n下一步：")
    print("1. 将 arena_stats_data.json 上传到线上服务器")
    print("2. 访问线上 /api/arena/import-json 接口导入数据")


if __name__ == "__main__":
    main()
