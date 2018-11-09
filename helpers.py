import hex_math
from hex_math import Point

def get_current_viewport(sprite_width, scroller, safe=True):
    """
    Get the current viewport coordinates. I feel like Cocos2d should handle this, but I can't seem to find it.
    Args:
        safe (bool): if true, add a safety margin to the edges of the viewport.
        sprite_width (int): width of the sprite in pixels.
        scroller (ScrollingManager): cocos2d scrolling manager.
    Returns:
        Dictionary with te key being one of "top_left", "bottom_right", "top_right" or "bottom_left".
        Values are (x, y) pixel coordinates.
    """
    safety_direction = {"top_left": (-1, 1), "bottom_right": (1, -1), "top_right": (1, 1), "bottom_left": (-1, -1)}
    safety_factor = 1 * sprite_width
    x = scroller.fx
    y = scroller.fy
    window_width = scroller.view_w
    window_height = scroller.view_h

    tl = x - window_width // 2, y + window_height // 2
    bl = x - window_width // 2, y - window_height // 2
    tr = x + window_width // 2, y + window_height // 2
    br = x + window_width // 2, y - window_height // 2
    coords = {"top_left": tl, "bottom_right": br, "top_right": tr, "bottom_left": bl}
    new_coords = {}
    if safe:
        for k, v in coords.items():
            new_coords[k] = tuple([x[1] + x[0] * safety_factor for x in zip(safety_direction[k], v)])
    else:
        new_coords = coords
    return new_coords


def get_current_viewport_hexes(layout, sprite_width, scroller, safe=True):
    """
    Find the corner hexes for the viewport.
    Args:
        safe (bool): if true, add a safety margin to the edges of the viewport.
        layout: the layout to use.
    Returns:
        A dictionary of the hegaxons corresponding to the corners of the viewport.
    """
    coordinates = get_current_viewport(sprite_width, scroller, safe)
    return {k: hex_math.pixel_to_hex(layout, Point(*v)) for k, v in coordinates.items()}


def find_visible_hexes(sprite_width, layout, scroller, safe=True):
    """
    Finds all of the visible hexes in the current viewport.
    Args:
        safe (bool): if true, add a safety margin to the edges of the viewport.
    Returns:
        Set of all of the hexes visible in the current viewport.
    """
    corners = get_current_viewport_hexes(layout, sprite_width, scroller, safe)
    top_line = hex_math.hex_linedraw(corners["top_left"], corners["top_right"])
    bottom_line = hex_math.hex_linedraw(corners["bottom_left"], corners["bottom_right"])
    visible = []
    for x in zip(top_line, bottom_line):
        visible += hex_math.hex_linedraw(*x)
    #  Use a set to make sure we don't have any duplicates.
    return {x for x in visible}