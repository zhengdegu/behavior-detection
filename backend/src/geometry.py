"""
Geometry utility module — polygon containment, line intersection, and other basic operations.
"""

from typing import List, Tuple

Point = Tuple[float, float]
Polygon = List[Point]


def point_in_polygon(point: Point, polygon: Polygon) -> bool:
    """Ray casting algorithm to determine if a point is inside a polygon"""
    x, y = point
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside
