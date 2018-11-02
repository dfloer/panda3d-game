from cocos.layer import ScrollingManager, Layer
from cocos.director import director
from cocos.scene import Scene
from cocos.batch import BatchNode
from cocos.sprite import Sprite

import hex_math
from random import randint
from collections import namedtuple
from math import sqrt

Hexagon = namedtuple("Hex", ["q", "r", "s"])
Point = namedtuple("Point", ["x", "y"])

sprite_width = 64
sprite_height = 32
pointy_width = sprite_width / sqrt(3)
window_title = "cocos2d hex test"

window_width = 800
window_height = 600

layout_size = Point(pointy_width, sprite_height)
layout = hex_math.Layout(hex_math.layout_pointy, layout_size, Point(window_width // 2, window_height // 2))


def generate_map(radius):
    """
    Generates a hexagonal map with given radius.

    Args:
        radius (int): radius of the number of tiles to draw.
    Returns:
        A dictionary with the key being the cubic hex coordinates, and the value being the properties of the hex.
        Right now, the properties can only contain the hex's sprite_id.
    """
    hex_map = {}
    for q in range(-radius, radius + 1):
        r1 = max(-radius, -q - radius)
        r2 = min(radius, -q + radius)
        for r in range(r1, r2 + 1):
            hex_properties = {"sprite_id": randint(1, 4)}
            k = Hexagon(q, r, -q - r)
            hex_map[k] = hex_properties
    return hex_map


class MapLayer(Layer):
    is_event_handler = True

    def __init__(self):
        super(MapLayer, self).__init__()
        self.map_sprites_batch = BatchNode()
        self.map_sprites_batch.position = layout.origin.x, layout.origin.y

    def batch_map(self):
        """
        Generate the sprites to put into the render batch.
        """
        for hexagon, hex_properties in hex_map.items():
            position = hex_math.hex_to_pixel(layout, hexagon, False)
            anchor = sprite_width // 2, sprite_height // 2
            sprite_id = hex_properties['sprite_id']
            sprite = Sprite(f"sprites/{sprite_id}.png", position=position, anchor=anchor)
            self.map_sprites_batch.add(sprite, z= -hexagon.r)
        self.add(self.map_sprites_batch)

    def set_view(self, x, y, w, h, a, b):
        """
        A stub to get things working.
        """
        print(x, y, w, h, a, b)
        # This'll need to do something at some point.


if __name__ == "__main__":
    director.init(window_width, window_height, window_title)
    hex_map = generate_map(10)
    layer = MapLayer()
    layer.batch_map()
    scroller = ScrollingManager()
    scroller.add(layer)
    director.run(Scene(scroller))

