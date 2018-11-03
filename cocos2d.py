from cocos.layer import ScrollingManager, Layer, ScrollableLayer
from cocos.director import director
from cocos.scene import Scene
from cocos.batch import BatchNode
from cocos.sprite import Sprite
from cocos.menu import Menu
from pyglet.window import key

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

window_width = 1280
window_height = 800

layout_size = Point(pointy_width, sprite_height)
layout = hex_math.Layout(hex_math.layout_pointy, layout_size, Point(window_width // 2, window_height // 2))

director.init(window_width, window_height, window_title)
keyboard = key.KeyStateHandler()
scroller = ScrollingManager()


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
            hex_properties = {"sprite_id": randint(1, 6)}
            k = Hexagon(q, r, -q - r)
            hex_map[k] = hex_properties
    return hex_map


class Terrain:
    """
    A class to store the terrain.
    """
    def __init__(self, chunk_size=31, random_seed=42):
        self.hexagon_map = {}
        self.random_seed = random_seed
        self.chunk_size = chunk_size


    def generate_chunk(self, center, chunk_radius=31, start=False):
        """
        Generates a chunk, sized as given.
        Args:
            start (bool): If this is True, this is the starting segment and doesn't need to be reconciled with neighbours.
            chunk_radius (int): size of a chunk. A chunk will be a "hex" segment of this many tiles.
                Must be odd, in order to have a center.
            center (Hexagon): the q, r, and s coordinates for the center of the chunk.
        Returns:
            A dictionary of terrain hexes, containing chunk_size * chunk_size items.
        """
        print(center, chunk_radius, start)
        chunk_cells = {}
        # if not start:
        #     # Check each of the 6 corners for neighbours.
        #     # Order is left, top left, top right, right, bottom right, bottom left.
        #     corners = [(0, chunk_radius, -chunk_radius), (chunk_radius, 0, -chunk_radius), (chunk_radius, -chunk_radius, 0), (0, -chunk_radius, chunk_radius), (-chunk_radius, 0, chunk_radius), (-chunk_radius, chunk_radius, 0)]
        #     for corner in corners:
        #         print(corner)
        #         pass
        # else:

        for q in range(-chunk_radius, chunk_radius + 1):
            r1 = max(-chunk_radius, -q - chunk_radius)
            r2 = min(chunk_radius, -q + chunk_radius)
            for r in range(r1, r2 + 1):
                t_id = randint(1, 6)
                hex_cell = TerrainCell(t_id, t_id, None)
                k = Hexagon(q, r, -q - r)
                chunk_cells[k] = hex_cell
        # There is a better way to do this.
        for k, v in chunk_cells.items():
            self.hexagon_map[k] = v


class TerrainCell:
    """
    A class to store specific terrain cells and their associated properties. This is just a cell, and doesn't know coordinates, or anything.
    """
    def __init__(self, terrain_type=0, sprite_id=0, building=None):
        self.terrain_type = terrain_type
        self.sprite_id = sprite_id
        self.building = building
        test_buildings = randint(0, 32)
        if test_buildings == 8:
            self.building = 'A'
        elif test_buildings == 16:
            self.building = 'B'

    def __str__(self):
        return f"Terrain: {self.terrain_type}, id: {self.sprite_id}, building: {self.building}."



class MapLayer(ScrollableLayer):
    is_event_handler = True

    def __init__(self):
        super().__init__()
        self.map_sprites_batch = BatchNode()
        self.map_sprites_batch.position = layout.origin.x, layout.origin.y

    def batch_map(self):
        """
        Generate the sprites to put into the render batch.
        """
        for hexagon, hex_properties in terrain_map.hexagon_map.items():
            position = hex_math.hex_to_pixel(layout, hexagon, False)
            anchor = sprite_width // 2, sprite_height // 2
            sprite_id = hex_properties.sprite_id
            sprite = Sprite(f"sprites/{sprite_id}.png", position=position, anchor=anchor)
            self.map_sprites_batch.add(sprite, z=-hexagon.r)
        self.add(self.map_sprites_batch)

    def set_view(self, x, y, w, h, viewport_ox=0, viewport_oy=0):
        """
        A stub to get things working.
        """
        super().set_view(x, y, w, h, viewport_ox, viewport_oy)

    def set_focus(self, *args, **kwargs):
        scroller.set_focus(*args, **kwargs)


class MouseLayer(ScrollableLayer):
    is_event_handler = True

    def __init__(self):
        super().__init__()
        self.last_hex = None
        self.mouse_sprites_batch = BatchNode()
        self.mouse_sprites_batch.position = layout.origin.x, layout.origin.y
        self.selected_batch = BatchNode()
        self.selected_batch.position = layout.origin.x, layout.origin.y

    def on_mouse_press(self, x, y, button, dy):
        """
        Right now, this is a test function
        This overrides the function from the base class.
        Args:
            x: mouse x position.
            y: mouse y position.
            button: which button was pushed.
            dy: no idea what this does.
        """
        p = Point(x, y)
        raw = hex_math.pixel_to_hex(layout, p)
        h = hex_math.hex_round(raw)
        position = hex_math.hex_to_pixel(layout, h, False)
        # Todo: Figure out the issue causing hexes to sometime not be properly selected, probably rouning.

        anchor = sprite_width / 2, sprite_height / 2
        sprite = Sprite(f"sprites/select red border.png", position=position, anchor=anchor)
        self.selected_batch.add(sprite, z=-h.r)
        self.add(self.selected_batch)

    def on_mouse_motion(self, x, y, dx, dy):
        p = Point(x, y)
        raw = hex_math.pixel_to_hex(layout, p)
        h = hex_math.hex_round(raw)
        position = hex_math.hex_to_pixel(layout, h, False)

        anchor = sprite_width / 2, sprite_height / 2
        sprite = Sprite(f"sprites/select.png", position=position, anchor=anchor)
        self.mouse_sprites_batch.add(sprite, z=-h.r)
        if self.last_hex is not None:
                self.mouse_sprites_batch.remove(self.last_hex)
        self.add(self.mouse_sprites_batch)
        self.last_hex = sprite
        # print(f"mouse move: ({x}, {y}), dx: {dx}, dy: {dy}.")


    def set_view(self, x, y, w, h, viewport_ox=0, viewport_oy=0):
        """
        A stub to get things working.
        """
        super().set_view(x, y, w, h, viewport_ox, viewport_oy)


class MenuLayer(Menu):
    is_event_handler = True

    def __init__(self):
        super().__init__()



if __name__ == "__main__":
    terrain_map = Terrain()
    mouse_layer = MouseLayer()
    terrain_map.generate_chunk(None, 31, True)
    layer = MapLayer()
    layer.batch_map()
    layer.set_focus(*layout.origin)
    scroller.add(mouse_layer, z=10)
    scroller.add(layer, z=0)
    director.window.push_handlers(keyboard)
    director.run(Scene(scroller))

