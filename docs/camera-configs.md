# 摄像头参数配置参考

根据各摄像头实际场景分析得出的推荐参数配置。

> **注意：** Pose 模型已确认加载（`yolo26m-pose.engine`），wrist_speed 可用。打架和跌倒参数已调整为宽松配置，适配高俯视远距离仓库场景。打架 `min_speed` 基线 **45**，跌倒 `min_hip_velocity` 基线 **8**。

---

## OF - East Lunch Area - 005  2563

**场景：** 办公室休息/午餐区，广角俯视，沙发休闲区 + 长桌用餐区

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 8,
    "radius": 280,
    "confirm_frames": 8,
    "cooldown": 120
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": false
  }
}
```

---

## office_Kitchen

**场景：** 办公室厨房/茶水间，中等广角略俯视，地面可能湿滑

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 5,
    "radius": 200,
    "confirm_frames": 6,
    "cooldown": 60
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": false
  }
}
```

---

## Nyard - Forklift Mec / H2O Tower 2575

**场景：** 叉车维修/机械维护车间，广角俯视，地面有蓝色安全标线

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 4,
    "radius": 250,
    "confirm_frames": 6,
    "cooldown": 60
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 45,
    "max_distance": 120,
    "max_displacement_ratio": 0.25,
    "min_total_path": 40,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 90
  }
}
```

---

## OF - 1st Flr Elevator - 006

**场景：** 一楼电梯厅，广角鱼眼俯视，夜间红外

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 4,
    "radius": 180,
    "confirm_frames": 5,
    "cooldown": 60
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 120,
    "max_distance": 100,
    "max_displacement_ratio": 0.3,
    "min_total_path": 30,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 90
  }
}
```

---

## BreakroomHall_Bay4. 19555

**场景：** 通往休息室的走廊，窄角正对纵深，夜间红外

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 3,
    "radius": 150,
    "confirm_frames": 5,
    "cooldown": 60
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 60,
    "max_distance": 80,
    "max_displacement_ratio": 0.3,
    "min_total_path": 30,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 60
  }
}
```

---

## Bay1 - Emp GDD Ent - 001. 2583

**场景：** 仓库 Bay1 员工入口通道，中等广角带纵深

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 4,
    "radius": 220,
    "confirm_frames": 6,
    "cooldown": 60
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 90,
    "max_distance": 120,
    "max_displacement_ratio": 0.25,
    "min_total_path": 40,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 90
  }
}
```

---

## Bay4 - DK110 - 016 2384

**场景：** 仓库装卸月台，广角俯视，绿色装卸板 + 安全标线

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 5,
    "radius": 300,
    "confirm_frames": 8,
    "cooldown": 90
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 120,
    "max_distance": 200,
    "max_displacement_ratio": 0.3,
    "min_total_path": 50,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 120
  }
}
```

---

## Bay4 - DK107 - 015. 2383

**场景：** 装卸月台，广角高俯视，人体极小

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 5,
    "radius": 320,
    "confirm_frames": 8,
    "cooldown": 90
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 120,
    "max_distance": 220,
    "max_displacement_ratio": 0.3,
    "min_total_path": 50,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 120
  }
}
```

---

## Bay2 - Lunch Hallway-002. 2568

**场景：** 通往午餐区走廊，窄角俯视，地面有水渍

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 3,
    "radius": 150,
    "confirm_frames": 5,
    "cooldown": 60
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 60,
    "max_distance": 80,
    "max_displacement_ratio": 0.3,
    "min_total_path": 30,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 60
  }
}
```

---

## Breakroom1_Bay4 19554

**场景：** 仓库员工休息室/食堂，广角俯视，多张长桌

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 10,
    "radius": 260,
    "confirm_frames": 10,
    "cooldown": 120
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": false
  }
}
```

---

## Bay4 - Bay4 to Bay5 Entry - 018 2386

**场景：** Bay4 到 Bay5 连接通道/装卸区，广角俯视，有货物堆放

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 5,
    "radius": 300,
    "confirm_frames": 8,
    "cooldown": 90
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 90,
    "max_distance": 180,
    "max_displacement_ratio": 0.25,
    "min_total_path": 50,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 90
  }
}
```

---

## VVP - Main - 004  2624

**场景：** 室外停车场/货车场，广角近平视，夜间路灯

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 3,
    "radius": 250,
    "confirm_frames": 8,
    "cooldown": 60
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 90,
    "max_distance": 200,
    "max_displacement_ratio": 0.3,
    "min_total_path": 50,
    "trajectory_window": 90,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 60
  }
}
```

---

## Bay1 - Stairway WH 2nd 8147

**场景：** 仓库楼梯间/二楼通道，广角鱼眼俯视，极狭窄

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 3,
    "radius": 130,
    "confirm_frames": 4,
    "cooldown": 60
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 45,
    "max_distance": 60,
    "max_displacement_ratio": 0.3,
    "min_total_path": 20,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 60
  }
}
```

---

## Bay4 - DK74 Bay Ent - 003 2370

**场景：** 仓库货物存储区入口/叉车通道，广角俯视，夜间红外

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 3,
    "radius": 250,
    "confirm_frames": 6,
    "cooldown": 60
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 60,
    "max_distance": 150,
    "max_displacement_ratio": 0.25,
    "min_total_path": 40,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 60
  }
}
```

---

## C84-Exterior 18995

**场景：** 建筑外部停车场/园区外景，广角略俯视，夜间路灯，人体极小

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 3,
    "radius": 350,
    "confirm_frames": 8,
    "cooldown": 60
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 90,
    "max_distance": 200,
    "max_displacement_ratio": 0.3,
    "min_total_path": 50,
    "trajectory_window": 90,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 60
  }
}
```

---

## BP 164.156  7426

**场景：** 仓库装卸区（dock doors 关闭状态），广角俯视，地面有水渍

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 5,
    "radius": 280,
    "confirm_frames": 8,
    "cooldown": 90
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 90,
    "max_distance": 180,
    "max_displacement_ratio": 0.28,
    "min_total_path": 45,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 90
  }
}
```

---

## BP 164.157 7427

**场景：** 仓库分拣/发货工作站，广角高俯视，黄色安全护栏

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 5,
    "radius": 280,
    "confirm_frames": 8,
    "cooldown": 90
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 90,
    "max_distance": 160,
    "max_displacement_ratio": 0.25,
    "min_total_path": 40,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 90
  }
}
```

---

## Bay4 - DK74 Ramp - 001  2371

**场景：** 装卸坡道/集装箱对接区，广角俯视，有坡道高度差

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 4,
    "radius": 240,
    "confirm_frames": 6,
    "cooldown": 60
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 75,
    "max_distance": 140,
    "max_displacement_ratio": 0.25,
    "min_total_path": 40,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 90
  }
}
```

---

## C067-Office 2nd Flr Main East

**场景：** 二楼开放式办公区，广角略俯视，两侧密集工位，中间宽阔通道

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 8,
    "radius": 250,
    "confirm_frames": 10,
    "cooldown": 120
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": false
  }
}
```

---

## Bay2 - A237 FR - 017 2431

**场景：** 大型仓库货架/拣货区，广角高俯视，多层高架，叉车通道，人体较小

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 5,
    "radius": 300,
    "confirm_frames": 8,
    "cooldown": 90
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 120,
    "max_distance": 180,
    "max_displacement_ratio": 0.3,
    "min_total_path": 50,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 120
  }
}
```

---

## C086-Exterior. 8142

**场景：** 室外装卸/货车停靠区，广角俯视，多辆半挂货车，有高处作业（梯子），人体较小

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 5,
    "radius": 300,
    "confirm_frames": 8,
    "cooldown": 90
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 120,
    "max_distance": 200,
    "max_displacement_ratio": 0.3,
    "min_total_path": 50,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 120
  }
}
```

---

## C85-Exterior Exit Off 2614

**场景：** 室外楼梯出口/紧急出口，中等广角俯视，有台阶和扶手栏杆，纯通行区域

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 3,
    "radius": 160,
    "confirm_frames": 5,
    "cooldown": 60
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 60,
    "max_distance": 80,
    "max_displacement_ratio": 0.3,
    "min_total_path": 25,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 60
  }
}
```

---

## C93-Exterior. 2613

**场景：** 建筑外入口/人行道，广角鱼眼高俯视，混凝土走道 + 防滑垫，纯通行区域

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 4,
    "radius": 200,
    "confirm_frames": 6,
    "cooldown": 60
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 90,
    "max_distance": 120,
    "max_displacement_ratio": 0.3,
    "min_total_path": 30,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 60
  }
}
```

---

## 164.17-Exterior 2582

**场景：** 建筑外部停车场/道路全景，广角侧视，视野极开阔，人体极小

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 4,
    "radius": 350,
    "confirm_frames": 8,
    "cooldown": 60
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 90,
    "max_distance": 200,
    "max_displacement_ratio": 0.3,
    "min_total_path": 50,
    "trajectory_window": 90,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 60
  }
}
```

---

## C081-Parking Valley 8128

**场景：** 室外集装箱/拖车停放场，广角近平视，纵深极远，人体极小，高安全区域

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 3,
    "radius": 350,
    "confirm_frames": 8,
    "cooldown": 60
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 60,
    "max_distance": 200,
    "max_displacement_ratio": 0.3,
    "min_total_path": 40,
    "trajectory_window": 90,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 60
  }
}
```

---

## C062-Exterior 2623

**场景：** 员工停车场（紧邻集装箱），广角俯视，密集停车区，车辆间通道狭窄

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 3,
    "radius": 220,
    "confirm_frames": 6,
    "cooldown": 60
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 60,
    "max_distance": 130,
    "max_displacement_ratio": 0.3,
    "min_total_path": 35,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 60
  }
}
```

---

## 160.118-Exterior. 2573

**场景：** 仓库外围/集装箱后方死角通道，广角高俯视，围界安防监控

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 2,
    "radius": 280,
    "confirm_frames": 5,
    "cooldown": 60
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 45,
    "max_distance": 150,
    "max_displacement_ratio": 0.3,
    "min_total_path": 30,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 60
  }
}
```

---

## 160.107  2606

**场景：** 办公楼外侧停车场，广角高俯视，有大树遮挡，人体较小

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 4,
    "radius": 280,
    "confirm_frames": 8,
    "cooldown": 60
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 90,
    "max_distance": 160,
    "max_displacement_ratio": 0.3,
    "min_total_path": 40,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 60
  }
}
```

---

## 164.77_BAY5 Ext Water Tank

**场景：** Bay5 外部区域/叉车停放场，广角高俯视，重型车辆 + 黄色叉车集群，人体很小

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 5,
    "radius": 300,
    "confirm_frames": 8,
    "cooldown": 90
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 120,
    "max_distance": 200,
    "max_displacement_ratio": 0.3,
    "min_total_path": 50,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 120
  }
}
```

---

## C083-Exterior. 8140

**场景：** 仓库外部货车停靠/调度区，广角鱼眼俯视，多辆货车牵引头，大面积空旷地面

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 4,
    "radius": 300,
    "confirm_frames": 8,
    "cooldown": 90
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 120,
    "max_distance": 200,
    "max_displacement_ratio": 0.3,
    "min_total_path": 50,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 120
  }
}
```

---

## C86-Exterior (入口平台) 2625

**场景：** 建筑入口/露台通道，中等广角略俯视，混凝土平台 + 防撞柱 + 金属围栏

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 4,
    "radius": 220,
    "confirm_frames": 6,
    "cooldown": 60
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 90,
    "max_distance": 130,
    "max_displacement_ratio": 0.3,
    "min_total_path": 35,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 60
  }
}
```

---

## BP 164.158 7428

**场景：** 仓库内部发货/暂存区，广角高俯视，dock doors + 密集托盘货物，地面湿滑

```json
{
  "crowd": {
    "enabled": true,
    "max_count": 5,
    "radius": 260,
    "confirm_frames": 8,
    "cooldown": 90
  },
  "fight": {
    "enabled": true,
    "proximity_radius": 200,
    "min_speed": 45,
    "min_persons": 2,
    "confirm_frames": 3,
    "cooldown": 30,
    "co_move_cos_threshold": 0.8,
    "min_relative_speed": 30,
    "min_distance_variance": 6,
    "joint_overlap_threshold": 1
  },
  "fall": {
    "enabled": true,
    "ratio_threshold": 0.9,
    "min_ratio_change": 0.2,
    "min_y_drop": 5,
    "min_hip_velocity": 8,
    "spine_angle_threshold": 55,
    "inactivity_frames": 2,
    "inactivity_threshold": 8,
    "history_size": 15,
    "confirm_frames": 2,
    "cooldown": 30
  },
  "loiter": {
    "enabled": true,
    "min_duration": 90,
    "max_distance": 150,
    "max_displacement_ratio": 0.28,
    "min_total_path": 40,
    "trajectory_window": 60,
    "inertia": 3,
    "confirm_frames": 5,
    "cooldown": 90
  }
}
```

---

## 全局打架误报修复建议

经过多次误报分析（食堂用餐、搬货协作、走廊并行、休息区交谈），建议所有摄像头打架检测使用以下基线：

| 参数 | 建议基线值 | 说明 |
|------|-----------|------|
| `min_speed` | **120** | 排除正常行走/搬货/手势动作 |
| `confirm_frames` | **8-10** | 正常活动不会连续 8 帧满足条件 |
| `min_relative_speed` | **55** | 排除并行行走/协作搬货 |
| `min_distance_variance` | **18** | 排除坐着/站着交谈（食堂特殊场景用 5） |
| `joint_overlap_threshold` | **2** | 排除偶尔手臂进入对方区域 |
| `co_move_cos_threshold` | **0.6** | 放宽同向过滤覆盖更多并行场景 |
