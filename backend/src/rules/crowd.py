"""
聚集检测 — 基于连通分量聚类
构建邻接图 → BFS 找连通分量 → 群组人数超阈值即告警
"""

import math
import logging
from typing import List, Dict, Any
from collections import defaultdict

from ..detection import Detection
from .base import BaseAnomalyRule

logger = logging.getLogger(__name__)


class CrowdRule(BaseAnomalyRule):

    def __init__(self, max_count: int = 5, radius: float = 200.0,
                 confirm_frames: int = 5, cooldown: float = 60.0):
        super().__init__("crowd", confirm_frames, cooldown)
        self.max_count = max_count
        self.radius = radius

    def _find_clusters(self, person_dets: list) -> List[List[int]]:
        """BFS 找连通分量"""
        n = len(person_dets)
        adj: Dict[int, List[int]] = defaultdict(list)
        for i in range(n):
            for j in range(i + 1, n):
                dist = math.dist(person_dets[i].center, person_dets[j].center)
                if dist < self.radius:
                    adj[i].append(j)
                    adj[j].append(i)

        visited = [False] * n
        clusters = []
        for start in range(n):
            if visited[start]:
                continue
            queue = [start]
            visited[start] = True
            cluster = []
            while queue:
                node = queue.pop(0)
                cluster.append(node)
                for nb in adj[node]:
                    if not visited[nb]:
                        visited[nb] = True
                        queue.append(nb)
            clusters.append(cluster)
        return clusters

    def _cluster_bbox(self, person_dets: list, indices: List[int]) -> list:
        x1 = min(person_dets[i].bbox[0] for i in indices)
        y1 = min(person_dets[i].bbox[1] for i in indices)
        x2 = max(person_dets[i].bbox[2] for i in indices)
        y2 = max(person_dets[i].bbox[3] for i in indices)
        return [x1, y1, x2, y2]

    def update(self, detections: List[Detection],
               camera_id: str = "",
               frame_ts: float = 0.0) -> List[Dict[str, Any]]:
        import time
        events = []
        now = frame_ts if frame_ts > 0 else time.time()

        person_dets = [d for d in detections
                       if d.track_id >= 0 and d.class_name == "person"]

        if len(person_dets) < self.max_count:
            self._confirm_count.clear()
            return events

        clusters = self._find_clusters(person_dets)

        for indices in clusters:
            count = len(indices)
            if count < self.max_count:
                continue

            tids = sorted(person_dets[i].track_id for i in indices)
            key = f"crowd_{'_'.join(str(t) for t in tids)}"

            if self._check_confirm_and_cooldown(key, True, now=now):
                bbox = self._cluster_bbox(person_dets, indices)
                cx = sum(person_dets[i].center[0] for i in indices) / count
                cy = sum(person_dets[i].center[1] for i in indices) / count
                events.append({
                    "type": "anomaly",
                    "sub_type": "crowd",
                    "camera_id": camera_id,
                    "count": count,
                    "center": (cx, cy),
                    "bbox": bbox,
                    "track_ids": tids,
                    "detail": f"聚集告警：{count}人在半径{self.radius:.0f}px内聚集",
                    "timestamp": now,
                })
                logger.info(f"[聚集] cam={camera_id} count={count} tids={tids}")
                break

        return events
