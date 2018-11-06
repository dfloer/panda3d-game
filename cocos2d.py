from cocos.layer import ScrollingManager, Layer, ScrollableLayer
from cocos.director import director
from cocos.scene import Scene
from cocos.batch import BatchNode
from cocos.sprite import Sprite
from cocos.menu import Menu
from pyglet.window import key
from pyglet import image

import hex_math
from random import randint
from collections import namedtuple
from math import sqrt
import os

Hexagon = namedtuple("Hex", ["q", "r", "s"])
Point = namedtuple("Point", ["x", "y"])

sprite_width = 64
sprite_height = 32
pointy_width = round(sprite_width / sqrt(3))  # This is the distance from the center to one of the corners.
window_title = "cocos2d hex test"

window_width = 1280
window_height = 800

layout_size = Point(pointy_width, sprite_height)
layout = hex_math.Layout(hex_math.layout_pointy, layout_size, Point(window_width // 2, window_height // 2))

director.init(window_width, window_height, window_title, autoscale=False)
keyboard = key.KeyStateHandler()


class Terrain:
    """
    A class to store the terrain.
    """
    def __init__(self, chunk_size=31, random_seed=42):
        self.city_cores = []
        self.random_seed = random_seed
        self.chunk_size = chunk_size
        # Dictionary where the key is the hexagon the building pertains to, and the value is a Building instance.
        self.buildings = {}

        # This seems is a bit of a hack, but it seems to work. Hopefully I won't regret it later.
        # Chunk list has a key of the center of a chunk, and the values are the hexes inside that chunk.
        # The actual terrain hexes are stored in hexagon_map, with their key being the hexagon from the chunk_list.
        self.chunk_list = {}
        self.hexagon_map = {}


    def fill_viewport_chunks(self):
        """
        Fills the viewport with hex chunks.
        Chunks are assumed to be larger than the viewport. Note: This will cause issues with resizing.
        """
        chunks = self.find_visible_chunks()
        before_size = len(self.chunk_list)
        for c in chunks:
            self.generate_chunk(c)
        if len(self.chunk_list) > before_size:  # Only redraw map if we've added hexes.
            terrain_layer.batch_map()


    def find_visible_chunks(self):
        """
        Used to find the visible chunks in a viewport. May return chunks that aren't quite visible to be safe.
        Returns:
            A list of TerrainChunk objects that are visible in the current viewport.
        """
        x = scroller.fx
        y = scroller.fy
        screen_center = hex_math.pixel_to_hex(layout, Point(x, y))
        center = self.find_chunk_parent(screen_center)

        # find the centers of the 8 chunks surrounding our chunk.
        # Start with the cross ones first
        q_offset = self.chunk_size // 2
        left = Hexagon(center.q - self.chunk_size, center.r, -(center.q - self.chunk_size) - center.r)
        right = Hexagon(center.q + self.chunk_size, center.r, -(center.q + self.chunk_size) - center.r)
        up = Hexagon(center.q - q_offset, center.r + self.chunk_size, -(center.q +-q_offset) - (center.r + self.chunk_size))
        down = Hexagon(center.q + q_offset + 1, center.r - self.chunk_size, -(center.q + q_offset + 1) - (center.r - self.chunk_size))
        # And the four diagonals, based on the previous ones.
        up_left = Hexagon(up.q - self.chunk_size, up.r, -(up.q - self.chunk_size) - up.r)
        up_right = Hexagon(up.q + self.chunk_size, up.r, -(up.q + self.chunk_size) - up.r)
        down_left = Hexagon(down.q - self.chunk_size, down.r, -(down.q - self.chunk_size) - down.r)
        down_right = Hexagon(down.q + self.chunk_size, down.r, -(down.q + self.chunk_size) - down.r)

        return up, down, left, right, up_left, up_right, down_left, down_right

    def find_chunk_parent(self, cell):
        """
        Given a cell, which chunk does it belong to?
        Args:
            cell (Hexagon): cell we're interested in knowing the chunk of.
        Returns:
            Hexagon pointing to the center of the chunk.
        """
        # Generate a chunk with myself in the middle.
        test_chunk = TerrainChunk(cell, self.chunk_size)
        to_check = test_chunk.chunk_cells.keys()
        for x in to_check:
            if x in self.chunk_list.keys():
                return x
        return cell


    def generate_chunk(self, center):
        """
        Generates a chunk. See note in init function about how hacky this is.
        Args:
            center (Hexagon): hexagon representing the center of the chunk.
        """
        if center not in self.chunk_list.keys():
            chunk = TerrainChunk(center, self.chunk_size)
            self.chunk_list[center] = [k for k in chunk.chunk_cells.keys()]
            for k, v in chunk.chunk_cells.items():
                self.hexagon_map[k] = v
            if center == Hexagon(0, 0, 0):
                self.add_building(center, Building(0))

    def add_building(self, hex_coords, building):
        """
        Adds a building to the terrain.
        Args:
            building (Building): building object to add to the terrain map.
            hex_coords (Hexagon): coordinates for the building.
        Returns:
            The building that was added.
        """
        self.buildings[hex_coords] = building
        self.hexagon_map[hex_coords].building = building

    def __len__(self):
        return len(self.chunk_list) * self.chunk_size * self.chunk_size


class TerrainChunk:
    """
    Stores metadata and data related to a terrain chunk.
    """
    def __init__(self, center, chunk_size):
        self.center = center
        self.chunk_size = chunk_size
        self.chunk_cells = self.generate(self.center)

    def generate(self, center):
        """
        Generates a chunk, sized as given. Current algorithm is to generate a "rectangle". Why a rectangle? Because that's the shape of a window, and it allows chunks to be accessed as x/y coordinates of their centers.
        Args:
            center (Hexagon): the q, r, and s coordinates for the center of the chunk.
        Returns:
            A dictionary of terrain hexes, containing chunk_size * chunk_size items.
        """
        x_dim, y_dim = (self.chunk_size, self.chunk_size)
        chunk_cells = {}
        # Why all this futzing around with dimensions // 2? Because I wanted the start of the chunk to be centered in the middle of the chunk.
        r_min = -x_dim // 2 + 1
        r_max = x_dim // 2 + 1
        for r in range(r_min, r_max):
            r_offset = r // 2
            q_min = -(y_dim // 2) - r_offset
            q_max = y_dim // 2 + 1 - r_offset
            for q in range(q_min, q_max):
                qq = center.q + q
                rr = center.r + r
                h = Hexagon(qq, rr, -qq - rr)
                terrain_type = str(randint(1, 6))
                sprite_id = terrain_type
                building = None
                chunk_cells[h] = TerrainCell(terrain_type, sprite_id, building)
        return chunk_cells

    def __len__(self):
        return len(self.chunk_cells)

    def __str__(self):
        return f"Chunk at {self.center} contains {len(self.chunks_cells)} hexes"


class TerrainCell:
    """
    A class to store specific terrain cells and their associated properties. This is just a cell, and doesn't know coordinates, or anything.
    """
    def __init__(self, terrain_type=0, sprite_id=None, building=None):
        self.terrain_type = terrain_type
        self.sprite_id = sprite_id
        self.building = building

    def __str__(self):
        return f"Terrain: {self.terrain_type}, id: {self.sprite_id}, building: {self.building}"


class Building:
    """
    A class to store the different buildings in.
    """
    _sprite_to_building = {0: "core claimed", 1: "RB"}

    def __init__(self, building_id):
        self.building_id = building_id
        self.sprite_id = self._sprite_to_building[building_id]

    def __str__(self):
        return f"Building with id: {self.building_id} and sprite: {self.sprite_id }"




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
        self.children = []  # Hack. But I don't need many copies of the same hexes.
        for hexagon, hex_properties in terrain_map.hexagon_map.items():
            position = hex_math.hex_to_pixel(layout, hexagon, False)
            anchor = sprite_width // 2, sprite_height // 2
            sprite_id = hex_properties.sprite_id
            sprite = Sprite(sprite_images[sprite_id], position=position, anchor=anchor)
            self.map_sprites_batch.add(sprite, z=-hexagon.r)
        self.add(self.map_sprites_batch)

    def set_view(self, x, y, w, h, viewport_ox=0, viewport_oy=0):
        """
        A stub to get things working.
        """
        super().set_view(x, y, w, h, viewport_ox, viewport_oy)

    def set_focus(self, *args, **kwargs):
        scroller.set_focus(*args, **kwargs)


class InputLayer(ScrollableLayer):
    is_event_handler = True

    def __init__(self):
        super().__init__()
        self.last_hex = None
        self.mouse_sprites_batch = BatchNode()
        self.mouse_sprites_batch.position = layout.origin.x, layout.origin.y
        self.selected_batch = BatchNode()
        self.selected_batch.position = layout.origin.x, layout.origin.y
        self.key = None

    def on_mouse_press(self, x, y, button, dy):
        """
        This is a test function for now.
        Right click displays info, left click draws a red hex, and left click + button does things.
        Args:
            x (int): mouse x position.
            y (int): mouse y position.
            button (int): which button was pushed.
            dy (int): no idea what this does.
        """
        p = Point(x + scroller.offset[0], y + scroller.offset[1])
        h = hex_math.pixel_to_hex(layout, p)
        if button == 4:  # Right click.
            print(f"({h.q}, {h.r}, {h.s}). {terrain_map.hexagon_map[h]}")
        # This will get split out into it
        else:
            if self.key is None:
                self.default_click(h)
            elif self.key is ord('q'):  # or 97
                # Place a test building.
                b = Building(1)
                building_layer.plop_building(h, b)

    def on_mouse_motion(self, x, y, dx, dy):
        p = Point(x + scroller.offset[0], y + scroller.offset[1])
        h = hex_math.pixel_to_hex(layout, p)
        position = hex_math.hex_to_pixel(layout, h, False)

        anchor = sprite_width / 2, sprite_height / 2
        sprite = Sprite(sprite_images["select"], position=position, anchor=anchor)
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

    def on_key_press(self, key, modifiers):
        self.key = key

    def on_key_release(self, key, modifiers):
        self.key = None

    def default_click(self, h):
        position = hex_math.hex_to_pixel(layout, h, False)
        # Todo: Figure out the issue causing hexes to sometime not be properly selected, probably rouning.

        anchor = sprite_width / 2, sprite_height / 2
        sprite = Sprite(sprite_images["select red border"], position=position, anchor=anchor)
        self.selected_batch.add(sprite, z=-h.r)
        self.add(self.selected_batch)


class BuildingLayer(ScrollableLayer):
    is_event_handler = True

    def __init__(self):
        super().__init__()
        self.last_hex = None
        self.buildings_batch = BatchNode()
        self.buildings_batch.position = layout.origin.x, layout.origin.y
        self.draw_buildings()

    def draw_buildings(self):
        for k, building in terrain_map.buildings.items():
            position = hex_math.hex_to_pixel(layout, k, False)
            anchor = sprite_width / 2, sprite_height / 2
            sprite = Sprite(sprite_images[building.sprite_id], position=position, anchor=anchor)
            self.buildings_batch.add(sprite, z=-k.r)
        self.add(self.buildings_batch)

    def plop_building(self, cell, building):
        """
        Adds the building with the given ID at the given location.
        Right now this is basically a stub to get the display code running, but this will need to be more complex as buildings actually do something.
        Args:
            cell (Hexagon): where do we want to plop this building?
            building (Building): id of the building to add.
        """
        if cell not in terrain_map.buildings.keys():
            terrain_map.add_building(cell, building)
            self.draw_buildings()
        else:
            print("Building already exists, skipping.")


class InputScrolling(ScrollingManager):
    is_event_handler = True

    def __init__(self, center):
        super().__init__()
        self.center = list(center)
        self.scroll_inc = 32
        self.offset = [0, 0]

    def on_key_press(self, key, modifiers):
        scroll = False
        if key == 65362:  # up arrow
            self.offset[1] -= self.scroll_inc
            scroll = True
        elif key == 65364:  # down arrow
            self.offset[1] += self.scroll_inc
            scroll = True
        elif key == 65363:  # right arrow
            self.offset[0] -= self.scroll_inc
            scroll = True
        elif key == 65361:  # left arrow
            self.offset[0] += self.scroll_inc
            scroll = True
        elif key == 65461:  # numpad 5
            self.offset = [0, 0]  # Resets entire view to default center.
            scroll = True
        if scroll:
            new_focus = [sum(x) for x in zip(self.center, self.offset)]
            self.scroll(new_focus)
            terrain_map.fill_viewport_chunks()

    def set_focus(self, *args, **kwargs):
        super().set_focus(*args, **kwargs)

    def scroll(self, new_center):

        self.set_focus(*new_center)


class MenuLayer(Menu):
    is_event_handler = True

    def __init__(self):
        super().__init__()


def load_images(path):
    """
    Loads the sprites from the given path.
    Args:
        path: Path to sprites directory, loads everything in it.
    Returns:
        Dictionary contraining the sprites. Key is the sprites filename without extension, value is a Sprite object.
    """
    images = {}
    for file in os.listdir(path):
        full_path = os.path.join(path, file)
        sprite_id = os.path.splitext(file)[0]
        img = image.load(full_path)
        images[sprite_id] = img
    return images

if __name__ == "__main__":
    scroller = InputScrolling(layout.origin)
    sprite_images = load_images("sprites/")
    terrain_map = Terrain(11)
    building_layer = BuildingLayer()
    terrain_map.generate_chunk(Hexagon(0, 0, 0))
    input_layer = InputLayer()
    terrain_layer = MapLayer()
    terrain_layer.batch_map()
    terrain_layer.set_focus(*layout.origin)
    terrain_map.fill_viewport_chunks()

    scroller.add(input_layer, z=2)
    scroller.add(terrain_layer, z=0)
    scroller.add(building_layer, z=1)
    building_layer.draw_buildings()
    director.window.push_handlers(keyboard)
    director.run(Scene(scroller))

