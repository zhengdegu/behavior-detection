#!/usr/bin/env python3
"""
按比例放宽 fight/fall 检测阈值，根据 deviceId 更新数据库。

使用方式（在部署服务器上）:

    # 1. 将脚本复制进容器
    docker cp backend/scripts/relax_thresholds.py behavior-detection-behavior-detection-1:/app/

    # 2. Dry-run 预览变更
    docker exec behavior-detection-behavior-detection-1 python3 /app/relax_thresholds.py --dry-run

    # 3. 执行更新
    docker exec behavior-detection-behavior-detection-1 python3 /app/relax_thresholds.py

    # 4. 重启容器使配置生效
    docker compose restart behavior-detection

    # 只更新指定设备:
    docker exec behavior-detection-behavior-detection-1 python3 /app/relax_thresholds.py --device-id 2563
"""

import argparse
import json
import sqlite3
import sys

# ── 各摄像头原始配置（从 camera-configs.md 提取）──

ORIGINAL_CONFIGS = {
    "18995": {
        "name": "C84-Exterior",
        "fight": {"enabled": True, "proximity_radius": 250, "min_speed": 120, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.7, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.1, "min_ratio_change": 0.35, "min_y_drop": 8, "min_hip_velocity": 15, "spine_angle_threshold": 48, "inactivity_frames": 4, "inactivity_threshold": 10, "history_size": 10, "confirm_frames": 3, "cooldown": 30},
    },
    "19554": {
        "name": "Breakroom1_Bay4",
        "fight": {"enabled": True, "proximity_radius": 180, "min_speed": 120, "min_persons": 2, "confirm_frames": 10, "cooldown": 30, "co_move_cos_threshold": 0.7, "min_relative_speed": 55, "min_distance_variance": 5, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.2, "min_ratio_change": 0.4, "min_y_drop": 12, "min_hip_velocity": 22, "spine_angle_threshold": 48, "inactivity_frames": 3, "inactivity_threshold": 15, "history_size": 10, "confirm_frames": 3, "cooldown": 30},
    },
    "19555": {
        "name": "BreakroomHall_Bay4",
        "fight": {"enabled": True, "proximity_radius": 120, "min_speed": 200, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.6, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 0.9, "min_ratio_change": 0.5, "min_y_drop": 22, "min_hip_velocity": 30, "spine_angle_threshold": 45, "inactivity_frames": 3, "inactivity_threshold": 15, "history_size": 10, "confirm_frames": 2, "cooldown": 30},
    },
    "2370": {
        "name": "Bay4 - DK74 Bay Ent - 003",
        "fight": {"enabled": True, "proximity_radius": 180, "min_speed": 120, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.7, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.2, "min_ratio_change": 0.35, "min_y_drop": 12, "min_hip_velocity": 20, "spine_angle_threshold": 48, "inactivity_frames": 3, "inactivity_threshold": 12, "history_size": 10, "confirm_frames": 2, "cooldown": 30},
    },
    "2371": {
        "name": "Bay4 - DK74 Ramp - 001",
        "fight": {"enabled": True, "proximity_radius": 170, "min_speed": 120, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.7, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.2, "min_ratio_change": 0.4, "min_y_drop": 12, "min_hip_velocity": 20, "spine_angle_threshold": 48, "inactivity_frames": 2, "inactivity_threshold": 12, "history_size": 10, "confirm_frames": 2, "cooldown": 30},
    },
    "2384": {
        "name": "Bay4 - DK110 - 016",
        "fight": {"enabled": True, "proximity_radius": 200, "min_speed": 120, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.7, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.3, "min_ratio_change": 0.35, "min_y_drop": 10, "min_hip_velocity": 18, "spine_angle_threshold": 50, "inactivity_frames": 3, "inactivity_threshold": 12, "history_size": 10, "confirm_frames": 2, "cooldown": 30},
    },
    "2386": {
        "name": "Bay4 - Bay4 to Bay5 Entry - 018",
        "fight": {"enabled": True, "proximity_radius": 200, "min_speed": 120, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.7, "min_relative_speed": 50, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.3, "min_ratio_change": 0.35, "min_y_drop": 10, "min_hip_velocity": 18, "spine_angle_threshold": 50, "inactivity_frames": 3, "inactivity_threshold": 12, "history_size": 10, "confirm_frames": 2, "cooldown": 30},
    },
    "2431": {
        "name": "Bay2 - A237 FR - 017",
        "fight": {"enabled": True, "proximity_radius": 200, "min_speed": 120, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.7, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.3, "min_ratio_change": 0.35, "min_y_drop": 10, "min_hip_velocity": 18, "spine_angle_threshold": 50, "inactivity_frames": 3, "inactivity_threshold": 12, "history_size": 10, "confirm_frames": 2, "cooldown": 30},
    },
    "2563": {
        "name": "OF - East Lunch Area - 005",
        "fight": {"enabled": True, "proximity_radius": 180, "min_speed": 120, "min_persons": 2, "confirm_frames": 10, "cooldown": 30, "co_move_cos_threshold": 0.6, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.2, "min_ratio_change": 0.4, "min_y_drop": 12, "min_hip_velocity": 22, "spine_angle_threshold": 45, "inactivity_frames": 3, "inactivity_threshold": 15, "history_size": 10, "confirm_frames": 3, "cooldown": 30},
    },
    "2568": {
        "name": "Bay2 - Lunch Hallway-002",
        "fight": {"enabled": True, "proximity_radius": 120, "min_speed": 200, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.6, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 0.9, "min_ratio_change": 0.5, "min_y_drop": 20, "min_hip_velocity": 28, "spine_angle_threshold": 45, "inactivity_frames": 2, "inactivity_threshold": 15, "history_size": 10, "confirm_frames": 2, "cooldown": 30},
    },
    "2573": {
        "name": "160.118-Exterior",
        "fight": {"enabled": True, "proximity_radius": 200, "min_speed": 120, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.7, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.2, "min_ratio_change": 0.35, "min_y_drop": 8, "min_hip_velocity": 15, "spine_angle_threshold": 50, "inactivity_frames": 3, "inactivity_threshold": 10, "history_size": 10, "confirm_frames": 2, "cooldown": 30},
    },
    "2575": {
        "name": "Nyard - Forklift Mec / H2O Tower",
        "fight": {"enabled": True, "proximity_radius": 170, "min_speed": 120, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.7, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.1, "min_ratio_change": 0.4, "min_y_drop": 15, "min_hip_velocity": 25, "spine_angle_threshold": 45, "inactivity_frames": 3, "inactivity_threshold": 15, "history_size": 10, "confirm_frames": 2, "cooldown": 30},
    },
    "2582": {
        "name": "164.17-Exterior",
        "fight": {"enabled": True, "proximity_radius": 250, "min_speed": 120, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.7, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.0, "min_ratio_change": 0.35, "min_y_drop": 8, "min_hip_velocity": 15, "spine_angle_threshold": 48, "inactivity_frames": 4, "inactivity_threshold": 10, "history_size": 10, "confirm_frames": 3, "cooldown": 30},
    },
    "2583": {
        "name": "Bay1 - Emp GDD Ent - 001",
        "fight": {"enabled": True, "proximity_radius": 220, "min_speed": 200, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.7, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.4, "min_ratio_change": 0.3, "min_y_drop": 8, "min_hip_velocity": 15, "spine_angle_threshold": 50, "inactivity_frames": 3, "inactivity_threshold": 10, "history_size": 10, "confirm_frames": 2, "cooldown": 30},
    },
    "2606": {
        "name": "160.107",
        "fight": {"enabled": True, "proximity_radius": 200, "min_speed": 120, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.7, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.2, "min_ratio_change": 0.35, "min_y_drop": 10, "min_hip_velocity": 18, "spine_angle_threshold": 48, "inactivity_frames": 4, "inactivity_threshold": 10, "history_size": 10, "confirm_frames": 3, "cooldown": 30},
    },
    "2613": {
        "name": "C93-Exterior",
        "fight": {"enabled": True, "proximity_radius": 150, "min_speed": 120, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.6, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.2, "min_ratio_change": 0.4, "min_y_drop": 12, "min_hip_velocity": 22, "spine_angle_threshold": 48, "inactivity_frames": 3, "inactivity_threshold": 15, "history_size": 10, "confirm_frames": 2, "cooldown": 30},
    },
    "2614": {
        "name": "C85-Exterior Exit Off",
        "fight": {"enabled": True, "proximity_radius": 130, "min_speed": 120, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.6, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.0, "min_ratio_change": 0.45, "min_y_drop": 18, "min_hip_velocity": 25, "spine_angle_threshold": 45, "inactivity_frames": 2, "inactivity_threshold": 15, "history_size": 10, "confirm_frames": 2, "cooldown": 30},
    },
    "2623": {
        "name": "C062-Exterior",
        "fight": {"enabled": True, "proximity_radius": 170, "min_speed": 120, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.7, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.2, "min_ratio_change": 0.35, "min_y_drop": 10, "min_hip_velocity": 20, "spine_angle_threshold": 48, "inactivity_frames": 3, "inactivity_threshold": 12, "history_size": 10, "confirm_frames": 3, "cooldown": 30},
    },
    "2624": {
        "name": "VVP - Main - 004",
        "fight": {"enabled": True, "proximity_radius": 180, "min_speed": 120, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.7, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.0, "min_ratio_change": 0.45, "min_y_drop": 15, "min_hip_velocity": 25, "spine_angle_threshold": 45, "inactivity_frames": 3, "inactivity_threshold": 15, "history_size": 10, "confirm_frames": 3, "cooldown": 30},
    },
    "2625": {
        "name": "C86-Exterior (入口平台)",
        "fight": {"enabled": True, "proximity_radius": 160, "min_speed": 120, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.6, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.0, "min_ratio_change": 0.4, "min_y_drop": 14, "min_hip_velocity": 22, "spine_angle_threshold": 45, "inactivity_frames": 3, "inactivity_threshold": 15, "history_size": 10, "confirm_frames": 2, "cooldown": 30},
    },
    "7426": {
        "name": "BP 164.156",
        "fight": {"enabled": True, "proximity_radius": 190, "min_speed": 120, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.7, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.3, "min_ratio_change": 0.35, "min_y_drop": 10, "min_hip_velocity": 18, "spine_angle_threshold": 50, "inactivity_frames": 3, "inactivity_threshold": 12, "history_size": 10, "confirm_frames": 2, "cooldown": 30},
    },
    "7427": {
        "name": "BP 164.157",
        "fight": {"enabled": True, "proximity_radius": 190, "min_speed": 120, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.7, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.3, "min_ratio_change": 0.35, "min_y_drop": 10, "min_hip_velocity": 18, "spine_angle_threshold": 50, "inactivity_frames": 3, "inactivity_threshold": 12, "history_size": 10, "confirm_frames": 2, "cooldown": 30},
    },
    "7428": {
        "name": "BP 164.158",
        "fight": {"enabled": True, "proximity_radius": 180, "min_speed": 120, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.7, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.3, "min_ratio_change": 0.35, "min_y_drop": 10, "min_hip_velocity": 18, "spine_angle_threshold": 50, "inactivity_frames": 3, "inactivity_threshold": 12, "history_size": 10, "confirm_frames": 2, "cooldown": 30},
    },
    "8128": {
        "name": "C081-Parking Valley",
        "fight": {"enabled": True, "proximity_radius": 250, "min_speed": 120, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.7, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.0, "min_ratio_change": 0.3, "min_y_drop": 6, "min_hip_velocity": 12, "spine_angle_threshold": 48, "inactivity_frames": 4, "inactivity_threshold": 8, "history_size": 10, "confirm_frames": 3, "cooldown": 30},
    },
    "8140": {
        "name": "C083-Exterior",
        "fight": {"enabled": True, "proximity_radius": 200, "min_speed": 120, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.7, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.2, "min_ratio_change": 0.3, "min_y_drop": 9, "min_hip_velocity": 16, "spine_angle_threshold": 50, "inactivity_frames": 3, "inactivity_threshold": 10, "history_size": 10, "confirm_frames": 2, "cooldown": 30},
    },
    "8142": {
        "name": "C086-Exterior",
        "fight": {"enabled": True, "proximity_radius": 200, "min_speed": 120, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.7, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.2, "min_ratio_change": 0.3, "min_y_drop": 8, "min_hip_velocity": 15, "spine_angle_threshold": 50, "inactivity_frames": 3, "inactivity_threshold": 10, "history_size": 10, "confirm_frames": 2, "cooldown": 30},
    },
    "8147": {
        "name": "Bay1 - Stairway WH 2nd",
        "fight": {"enabled": True, "proximity_radius": 110, "min_speed": 200, "min_persons": 2, "confirm_frames": 8, "cooldown": 30, "co_move_cos_threshold": 0.6, "min_relative_speed": 55, "min_distance_variance": 18, "joint_overlap_threshold": 2},
        "fall": {"enabled": True, "ratio_threshold": 1.0, "min_ratio_change": 0.5, "min_y_drop": 20, "min_hip_velocity": 28, "spine_angle_threshold": 45, "inactivity_frames": 2, "inactivity_threshold": 15, "history_size": 10, "confirm_frames": 2, "cooldown": 30},
    },
}


# ── 放宽策略 ──

def relax_fight(cfg):
    r = dict(cfg)
    r["min_speed"] = max(round(r.get("min_speed", 120) * 0.38), 20)
    r["confirm_frames"] = max(round(r.get("confirm_frames", 8) * 0.38), 2)
    r["proximity_radius"] = r.get("proximity_radius", 180) + 20
    r["co_move_cos_threshold"] = 0.8
    r["joint_overlap_threshold"] = 1
    r["min_relative_speed"] = max(round(r.get("min_relative_speed", 55) * 0.55), 15)
    r["min_distance_variance"] = max(round(r.get("min_distance_variance", 18) * 0.33), 3)
    return r


def relax_fall(cfg):
    r = dict(cfg)
    r["ratio_threshold"] = round(r.get("ratio_threshold", 1.2) * 0.75, 2)
    r["min_ratio_change"] = round(r.get("min_ratio_change", 0.4) * 0.55, 2)
    r["min_y_drop"] = max(round(r.get("min_y_drop", 12) * 0.42), 3)
    r["min_hip_velocity"] = max(round(r.get("min_hip_velocity", 20) * 0.4), 5)
    r["spine_angle_threshold"] = r.get("spine_angle_threshold", 45) + 8
    r["inactivity_frames"] = max(round(r.get("inactivity_frames", 3) * 0.67), 2)
    r["inactivity_threshold"] = max(round(r.get("inactivity_threshold", 12) * 0.67), 5)
    r["history_size"] = round(r.get("history_size", 10) * 1.5)
    return r


# ── 数据库操作 ──

DB_PATH = "/app/data/app.db"


def update_camera(device_id, fight_relaxed, fall_relaxed, dry_run=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        "SELECT rules_config FROM cameras WHERE id = ?", (device_id,)
    ).fetchone()

    if row is None:
        conn.close()
        return False

    rules = json.loads(row["rules_config"])

    # 更新 fight 参数（不改 enabled 状态）
    if fight_relaxed and "fight" in rules:
        for k, v in fight_relaxed.items():
            if k != "enabled":
                rules["fight"][k] = v

    # 更新 fall 参数（不改 enabled 状态）
    if fall_relaxed and "fall" in rules:
        for k, v in fall_relaxed.items():
            if k != "enabled":
                rules["fall"][k] = v

    if not dry_run:
        conn.execute(
            "UPDATE cameras SET rules_config = ?, updated_at = datetime('now') WHERE id = ?",
            (json.dumps(rules, ensure_ascii=False), device_id),
        )
        conn.commit()

    conn.close()
    return True


# ── 主流程 ──

def main():
    parser = argparse.ArgumentParser(description="按比例放宽 fight/fall 阈值")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写库")
    parser.add_argument("--device-id", action="append", help="只更新指定 deviceId")
    parser.add_argument("--db-path", default=None, help="覆盖数据库路径")
    args = parser.parse_args()

    global DB_PATH
    if args.db_path:
        DB_PATH = args.db_path

    target_ids = set(args.device_id) if args.device_id else set(ORIGINAL_CONFIGS.keys())

    print(f"{'[DRY-RUN] ' if args.dry_run else ''}更新 {len(target_ids)} 个摄像头\n")

    updated = 0
    not_found = 0

    for device_id in sorted(target_ids):
        if device_id not in ORIGINAL_CONFIGS:
            print(f"  ⚠ deviceId={device_id} 不在配置列表中")
            continue

        cam = ORIGINAL_CONFIGS[device_id]
        name = cam["name"]

        fight_relaxed = relax_fight(cam["fight"]) if cam["fight"].get("enabled") else None
        fall_relaxed = relax_fall(cam["fall"]) if cam["fall"].get("enabled") else None

        found = update_camera(device_id, fight_relaxed, fall_relaxed, dry_run=args.dry_run)

        if found:
            updated += 1
            tag = "🔍" if args.dry_run else "✅"
            print(f"  {tag} [{device_id}] {name}")
            if fight_relaxed:
                print(f"      fight: min_speed {cam['fight']['min_speed']}→{fight_relaxed['min_speed']}, "
                      f"confirm {cam['fight']['confirm_frames']}→{fight_relaxed['confirm_frames']}, "
                      f"dist_var {cam['fight']['min_distance_variance']}→{fight_relaxed['min_distance_variance']}")
            if fall_relaxed:
                print(f"      fall:  hip_vel {cam['fall']['min_hip_velocity']}→{fall_relaxed['min_hip_velocity']}, "
                      f"spine {cam['fall']['spine_angle_threshold']}→{fall_relaxed['spine_angle_threshold']}, "
                      f"history {cam['fall']['history_size']}→{fall_relaxed['history_size']}")
        else:
            not_found += 1
            print(f"  ❌ [{device_id}] {name} — 数据库中未找到")

    print(f"\n完成: 更新 {updated}, 未找到 {not_found}")
    if args.dry_run:
        print("💡 去掉 --dry-run 执行实际更新")


if __name__ == "__main__":
    main()
