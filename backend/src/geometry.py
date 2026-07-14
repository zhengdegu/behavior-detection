"""
Geometry utility module — polygon containment, line intersection, and other basic operations.
"""

from typing import List, Tuple

Point = Tuple[float, float]
Polygon = List[Point]
MultiPolygon = List[Polygon]


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


def point_in_any_polygon(point: Point, polygons: MultiPolygon) -> bool:
    """Check if a point is inside any polygon in the list (union logic)."""
    for polygon in polygons:
        if point_in_polygon(point, polygon):
            return True
    return False
