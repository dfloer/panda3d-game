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
        self.hexagon_map = {}
        self.city_cores = []
        self.random_seed = random_seed
        self.chunk_size = chunk_size
        # Dictionary where the key is the hexagon the building pertains to, and the value is a Building instance.
        self.buildings = {}
        # Dictionary where the key is the center and the value is a list of 4 hexs containing the 4 corner hexes.
        self.chunk_list = {}

    def generate_chunk(self, center):
        """
        Generates a chunk, sized as given. Current algorithm is to generate a "rectangle". Why a rectangle? Because that's the shape of a window, and it allows chunks to be accessed as x/y coordinates of their centers.
        Args:
            center (Hexagon): the q, r, and s coordinates for the center of the chunk.
        Returns:
            A dictionary of terrain hexes, containing chunk_size * chunk_size items.
        """
        print(center, self.chunk_size)
        if center not in self.chunk_list.keys():
            print(f"New chunk added at {center}.")
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
                    h = Hexagon(q, r, -q - r)
                    terrain_type = randint(1, 6)
                    sprite_id = terrain_type
                    building = None
                    chunk_cells[h] = TerrainCell(terrain_type, sprite_id, building)
                    if (r, q) == (0, 0):
                        building = Building(0)
                        self.add_building(building, h)
                        chunk_cells[h].sprite_id = 7

            r1 = r_min
            r2 = r_max - 1
            c1 = [-(y_dim // 2) - r2 // 2, r2]  # top left
            c2 = [y_dim // 2 - r2 // 2, r2]  # top right
            c3 = [y_dim // 2 - r1 // 2, r1]  # bottom right
            c4 = [-(y_dim // 2) - r1 // 2, r1]  # bottom left
            corners = [Hexagon(*c1, -c1[0] - c1[1]), Hexagon(*c2, -c2[0] - c2[1]), Hexagon(*c3, -c3[0] - c3[1]), Hexagon(*c4, -c4[0] - c4[1])]
            self.chunk_list[center] = corners
            # There is a better way to do this.
            for k, v in chunk_cells.items():
                self.hexagon_map[k] = v

    def fill_viewport_chunks(self):
        """
        Fills the viewport with hex chunks.
        Chunks are assumed to be larger than the viewport. Note: This will cause issues with resizing.
        """
        # Subtract the size of a sprite off to make sure the hex we're checking against is always fully on screen.
        w = scroller.view_w // 2 - sprite_width * 2
        h = scroller.view_h // 2 - sprite_height * 2
        x = scroller.fx
        y = scroller.fy
        top_left = hex_math.pixel_to_hex(layout, Point(x - w, y - h))
        top_right = hex_math.pixel_to_hex(layout, Point(x + w, y - h))
        bottom_right = hex_math.pixel_to_hex(layout, Point(x + w, y + h))
        bottom_left = hex_math.pixel_to_hex(layout, Point(x - w, y + h))
        print(top_left, top_right, bottom_left, bottom_right)

    def add_building(self, building, hex_coords):
        """
        Adds a building to the terrain.
        Args:
            building (Building): building object to add to the terrain map.
            hex_coords (Hexagon): coordinates for the building.
        Returns:
            The building that was added.
        """
        self.buildings[hex_coords] = building
        self.hexagon_map[hex_coords] = building

    def __len__(self):
        return len(self.hexagon_map)


class TerrainCell:
    """
    A class to store specific terrain cells and their associated properties. This is just a cell, and doesn't know coordinates, or anything.
    """
    def __init__(self, terrain_type=0, sprite_id=None, building=None):
        self.terrain_type = terrain_type
        self.sprite_id = sprite_id
        self.building = building

    def __str__(self):
        return f"Terrain: {self.terrain_type}, id: {self.sprite_id}, building: {self.building}."


class Building:
    """
    A class to store the different buildings in.
    """
    _sprite_to_building = {0: "core claimed", 1: "RB"}

    def __init__(self, building_id):
        self.building_id = building_id
        self.sprite_id = self._sprite_to_building[building_id]

    def __str__(self):
        return f"Building with id: {self.building_id} and sprite: {self.sprite_id }."




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


class InputLayer(ScrollableLayer):
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
        p = Point(x + scroller.offset[0], y + scroller.offset[1])
        h = hex_math.pixel_to_hex(layout, p)
        if button == 4:  # Right click.
            print(h)
        position = hex_math.hex_to_pixel(layout, h, False)
        # Todo: Figure out the issue causing hexes to sometime not be properly selected, probably rouning.

        anchor = sprite_width / 2, sprite_height / 2
        sprite = Sprite(f"sprites/select red border.png", position=position, anchor=anchor)
        self.selected_batch.add(sprite, z=-h.r)
        self.add(self.selected_batch)

    def on_mouse_motion(self, x, y, dx, dy):
        p = Point(x + scroller.offset[0], y + scroller.offset[1])
        h = hex_math.pixel_to_hex(layout, p)
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
            sprite = Sprite(f"sprites/{building.sprite_id}.png", position=position, anchor=anchor)
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
        position = hex_math.hex_to_pixel(layout, cell, False)
        anchor = sprite_width / 2, sprite_height / 2
        sprite = Sprite(f"sprites/{building.sprite_id}.png", position=position, anchor=anchor)
        terrain_map.add_building(building, cell)
        self.add(sprite, z=-cell.r)


class InputScrolling(ScrollingManager):
    is_event_handler = True

    def __init__(self, center):
        super().__init__()
        self.center = list(center)
        self.scroll_inc = 10
        self.offset = [0, 0]

    def on_key_press(self, key, modifiers):
        if key == 65362:  # up arrow
            self.offset[1] -= self.scroll_inc
        if key == 65364:  # down arrow
            self.offset[1] += self.scroll_inc
        if key == 65363:  # right arrow
            self.offset[0] -= self.scroll_inc
        if key == 65361:  # left arrow
            self.offset[0] += self.scroll_inc
        if key == 65461:  # numpad 5
            self.offset = [0, 0]  # Resets entire view to default center.
        new_center = [sum(x) for x in zip(self.center, self.offset)]
        self.scroll(new_center)
        terrain_map.fill_viewport_chunks()

    def set_focus(self, *args, **kwargs):
        super().set_focus(*args, **kwargs)

    def scroll(self, new_center):

        self.set_focus(*new_center)


class MenuLayer(Menu):
    is_event_handler = True

    def __init__(self):
        super().__init__()



if __name__ == "__main__":
    scroller = InputScrolling(layout.origin)
    terrain_map = Terrain(21)
    terrain_map.generate_chunk(Hexagon(0, 0, 0))
    building_layer = BuildingLayer()
    input_layer = InputLayer()
    terrain_layer = MapLayer()
    terrain_layer.batch_map()
    terrain_layer.set_focus(*layout.origin)

    scroller.add(input_layer, z=2)
    scroller.add(terrain_layer, z=0)
    scroller.add(building_layer, z=1)
    director.window.push_handlers(keyboard)
    director.run(Scene(scroller))

