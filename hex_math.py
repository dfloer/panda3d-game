import collections
import math


# Below code from http://www.redblobgames.com/grids/hexagons/
Point = collections.namedtuple("Point", ["x", "y"])
Hexagon = collections.namedtuple("Hex", ["q", "r", "s"])


def hexagon(q, r, s):
    assert not (round(q + r + s) != 0), "q + r + s must be 0"
    return Hexagon(q, r, s)


def hex_add(a, b):
    return hexagon(a.q + b.q, a.r + b.r, a.s + b.s)


def hex_subtract(a, b):
    return hexagon(a.q - b.q, a.r - b.r, a.s - b.s)


def hex_scale(a, k):
    return hexagon(a.q * k, a.r * k, a.s * k)


def hex_rotate_left(a):
    return hexagon(-a.s, -a.q, -a.r)


def hex_rotate_right(a):
    return hexagon(-a.r, -a.s, -a.q)


hex_directions = [hexagon(1, 0, -1), hexagon(1, -1, 0), hexagon(0, -1, 1), hexagon(-1, 0, 1), hexagon(-1, 1, 0), hexagon(0, 1, -1)]


def hex_direction(direction):
    return hex_directions[direction]


def hex_neighbor(hex, direction):
    return hex_add(hex, hex_direction(direction))


hex_diagonals = [hexagon(2, -1, -1), hexagon(1, -2, 1), hexagon(-1, -1, 2), hexagon(-2, 1, 1), hexagon(-1, 2, -1), hexagon(1, 1, -2)]


def hex_diagonal_neighbor(hex, direction):
    return hex_add(hex, hex_diagonals[direction])


def hex_length(hex):
    return (abs(hex.q) + abs(hex.r) + abs(hex.s)) // 2


def hex_distance(a, b):
    return hex_length(hex_subtract(a, b))


def hex_round(h):
    qi = int(round(h.q))
    ri = int(round(h.r))
    si = int(round(h.s))
    q_diff = abs(qi - h.q)
    r_diff = abs(ri - h.r)
    s_diff = abs(si - h.s)
    if q_diff > r_diff and q_diff > s_diff:
        qi = -ri - si
    else:
        if r_diff > s_diff:
            ri = -qi - si
        else:
            si = -qi - ri
    return hexagon(qi, ri, si)


def hex_lerp(a, b, t):
    return hexagon(a.q * (1.0 - t) + b.q * t, a.r * (1.0 - t) + b.r * t, a.s * (1.0 - t) + b.s * t)


def hex_linedraw(a, b):
    n = hex_distance(a, b)
    a_nudge = hexagon(a.q + 0.000001, a.r + 0.000001, a.s - 0.000002)
    b_nudge = hexagon(b.q + 0.000001, b.r + 0.000001, b.s - 0.000002)
    results = []
    step = 1.0 / max(n, 1)
    for i in range(0, n + 1):
        results.append(hex_round(hex_lerp(a_nudge, b_nudge, step * i)))
    return results


Orientation = collections.namedtuple("Orientation", ["f0", "f1", "f2", "f3", "b0", "b1", "b2", "b3", "start_angle"])
Layout = collections.namedtuple("Layout", ["orientation", "size", "origin"])
layout_pointy = Orientation(math.sqrt(3.0), math.sqrt(3.0) / 2.0, 0.0, 3.0 / 2.0, math.sqrt(3.0) / 3.0, -1.0 / 3.0, 0.0, 2.0 / 3.0, 0.5)
layout_flat = Orientation(3.0 / 2.0, 0.0, math.sqrt(3.0) / 2.0, math.sqrt(3.0), 2.0 / 3.0, 0.0, -1.0 / 3.0, math.sqrt(3.0) / 3.0, 0.0)


def hex_to_pixel(layout, h, use_origin=True):
    m = layout.orientation
    size = layout.size
    if use_origin:
        origin = layout.origin
    else:
        origin = Point(0, 0)
    x = (m.f0 * h.q + m.f1 * h.r) * size.x
    y = (m.f2 * h.q + m.f3 * h.r) * size.y
    return Point(x + origin.x, y + origin.y)


def pixel_to_hex(layout, p):
    return hex_round(raw_pixel_to_hex(layout, p))


def raw_pixel_to_hex(layout, p):
    m = layout.orientation
    size = layout.size
    origin = layout.origin
    pt = Point((p.x - origin.x) / size.x, (p.y - origin.y) / size.y)
    q = m.b0 * pt.x + m.b1 * pt.y
    r = m.b2 * pt.x + m.b3 * pt.y
    return hexagon(q, r, -q - r)


def hex_corner_offset(layout, corner):
    m = layout.orientation
    size = layout.size
    angle = 2.0 * math.pi * (m.start_angle - corner) / 6.0
    return Point(size.x * math.cos(angle), size.y * math.sin(angle))


def polygon_corners(layout, h):
    corners = []
    center = hex_to_pixel(layout, h)
    for i in range(0, 6):
        offset = hex_corner_offset(layout, i)
        corners.append(Point(center.x + offset.x, center.y + offset.y))
    return corners

def cube_to_offset(h):
    col = h.q
    row = h.r + (h.q + 1 * (h.q & 1)) // 2
    return Point(col, row)

# End of code from Redblob.

def get_hex_chunk(center, radius):
    """
    Given a hexagon, returns all hexagons that would be in a chunk with the given radius.
    Args:
        center (Hexagon): center of the new chunk.
        radius (int): distance from the center to an edge.
    Returns:
        List of hexagons in the hexagonal chunk.
    """
    hexes = []
    for q in range(-radius, radius + 1):
        r1 = max(-radius, -q - radius)
        r2 = min(radius, -q + radius)
        for r in range(r1, r2 + 1):
            h = Hexagon(center.q + q, center.r + r, -(center.q + q) - (center.r + r))
            hexes += [h]
    return hexes