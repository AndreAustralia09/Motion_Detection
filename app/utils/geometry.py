from __future__ import annotations

from typing import Iterable, Tuple

Point = Tuple[int, int]


def _point_on_segment(point: Point, a: Point, b: Point) -> bool:
    px, py = point
    ax, ay = a
    bx, by = b

    cross = (px - ax) * (by - ay) - (py - ay) * (bx - ax)
    if cross != 0:
        return False

    return (
        min(ax, bx) <= px <= max(ax, bx)
        and min(ay, by) <= py <= max(ay, by)
    )


def point_in_polygon(point: Point, polygon: Iterable[Point]) -> bool:
    x, y = point
    poly = list(polygon)
    inside = False
    if len(poly) < 3:
        return False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if _point_on_segment(point, poly[j], poly[i]):
            return True
        intersect = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def distance_sq(a: Point, b: Point) -> int:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy


def point_to_segment_distance_sq(point: Point, a: Point, b: Point) -> float:
    px, py = point
    ax, ay = a
    bx, by = b
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return float(distance_sq(point, a))
    t = ((px - ax) * dx + (py - ay) * dy) / float(dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    closest_x = ax + t * dx
    closest_y = ay + t * dy
    diff_x = px - closest_x
    diff_y = py - closest_y
    return (diff_x * diff_x) + (diff_y * diff_y)


def polygon_bounds(polygon: Iterable[Point]) -> tuple[int, int, int, int] | None:
    poly = list(polygon)
    if len(poly) < 3:
        return None
    xs = [point[0] for point in poly]
    ys = [point[1] for point in poly]
    return min(xs), min(ys), max(xs), max(ys)


def _orientation(a: Point, b: Point, c: Point) -> int:
    value = (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1])
    if value == 0:
        return 0
    return 1 if value > 0 else 2


def _segments_intersect(a1: Point, a2: Point, b1: Point, b2: Point) -> bool:
    o1 = _orientation(a1, a2, b1)
    o2 = _orientation(a1, a2, b2)
    o3 = _orientation(b1, b2, a1)
    o4 = _orientation(b1, b2, a2)

    if o1 != o2 and o3 != o4:
        return True

    if o1 == 0 and _point_on_segment(b1, a1, a2):
        return True
    if o2 == 0 and _point_on_segment(b2, a1, a2):
        return True
    if o3 == 0 and _point_on_segment(a1, b1, b2):
        return True
    if o4 == 0 and _point_on_segment(a2, b1, b2):
        return True
    return False


def polygon_is_simple(polygon: Iterable[Point]) -> bool:
    poly = list(polygon)
    count = len(poly)
    if count < 3:
        return False

    segments = [(poly[index], poly[(index + 1) % count]) for index in range(count)]
    for index, (a1, a2) in enumerate(segments):
        for other_index in range(index + 1, count):
            if other_index in {index, index - 1, index + 1}:
                continue
            if index == 0 and other_index == count - 1:
                continue
            b1, b2 = segments[other_index]
            if _segments_intersect(a1, a2, b1, b2):
                return False
    return True
