from cocos.layer import ScrollingManager, Layer, ScrollableLayer
from cocos.director import director
from cocos.scene import Scene
from cocos.batch import BatchNode
from cocos.sprite import Sprite
from cocos.menu import Menu
from cocos.text import Label
from pyglet.window import key
from pyglet import image
from cocos.actions import Action

import hex_math
import settings
from random import randint
from opensimplex import OpenSimplex
from collections import namedtuple
from math import sqrt
import os
from heapq import heappush, heappop
from queue import PriorityQueue
import helpers

Hexagon = namedtuple("Hex", ["q", "r", "s"])
Point = namedtuple("Point", ["x", "y"])

sprite_width = 64
sprite_height = 32
pointy_width = round(sprite_width / sqrt(3))  # This is the distance from the center to one of the corners.
window_title = "cocos2d hex test"

window_width = 1920
window_height = 1200

layout_size = Point(pointy_width, sprite_height)
layout = hex_math.Layout(hex_math.layout_pointy, layout_size, Point(window_width // 2, window_height // 2))

director.init(window_width, window_height, window_title, autoscale=False)
keyboard = key.KeyStateHandler()


class Terrain:
    """
    A class to store the terrain.
    """
    def __init__(self, chunk_size=31, random_seed=42):
        self.city_cores = {}
        self.random_seed = random_seed
        self.chunk_size = chunk_size
        # Dictionary where the key is the hexagon the building pertains to, and the value is a Building instance.
        self.buildings = {}
        self.terrain_noise = OpenSimplex(seed=self.random_seed)
        self.random_noise = OpenSimplex(seed=self.random_seed ** self.random_seed)
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
        # chunks = self.find_visible_chunks()
        # for c in chunks:
        #     self.generate_chunk(c)
        chunks = self.find_visible_chunks()
        before_size = len(self.chunk_list)
        for chunk in chunks:
            self.generate_chunk(chunk)
        if len(self.chunk_list) > before_size:  # Only redraw map if we've added hexes.
            terrain_layer.draw_terrain()

    def find_visible_chunks(self):
        """
        Used to find the visible chunks in a viewport. May return chunks that aren't quite visible to be safe.
        Returns:
            A list of TerrainChunk objects that are visible in the current viewport.
        """
        x = window_width // 2
        y = window_height // 2
        screen_center = hex_math.pixel_to_hex(layout, Point(x, y))
        center = self.find_chunk_parent(screen_center)
        return self.find_chunks(center)

    def chunk_get_next(self, center, direction="up"):
        """
        Given a current chunk's anchor hexagon, find the next chunk's anchor hexagon.
        Currently doesn't support diagonals.
        Args:
            center (Hexagon): the anchor hexagon for this chunk.
            direction (str): One up up, down, left or right for the direction to get the next chunk from.
        Returns:
            A hexagon with the desired chunk's anchor.
        """
        q_offset = self.chunk_size // 2
        directions = {
            "up": (center.q + q_offset + 1,
                   center.r - self.chunk_size - 1,
                   -(center.q + q_offset + 1) - (center.r - self.chunk_size - 1)),
            "down": (center.q - q_offset - 1,
                     center.r + self.chunk_size + 1,
                     -(center.q - q_offset - 1) - (center.r + self.chunk_size + 1)),
            "left": (center.q - self.chunk_size,
                     center.r,
                     -(center.q - self.chunk_size) - center.r),
            "right": (center.q + self.chunk_size,
                      center.r,
                      -(center.q + self.chunk_size) - center.r),
        }
        return Hexagon(*directions[direction])

    def find_chunks(self, center):
        """
        Finds all of the chunks in the viewport.
        Args:
            center (Hexagon): hexagon representing the center of the viewport.
        Returns:
            A set of all the chunk anchors visible in the viewport (and then some that aren't to make sure we've filled past the edge of the viewport).
        """
        # First generate all of the chunks in a vertical strip centered on the center chunk to the top and bottom of viewport, plus a little extra for safety.
        all_visible_hexes = helpers.find_visible_hexes(sprite_width, layout, scroller, safe=True)
        ups = [center]
        while True:
            ups += [self.chunk_get_next(ups[-1], "up")]
            if ups[-1] not in all_visible_hexes:
                break
        downs = [center]
        while True:
            downs += [self.chunk_get_next(downs[-1], "down")]
            if downs[-1] not in all_visible_hexes:
                break
        vertical_strip = ups + downs
        horizontal_strips = []
        # With the vertical strip down, generate a horizontal strip for each chunk in it, to cover the viewpor.
        for c in vertical_strip:
            lefts = [c]
            rights = [c]
            while True:
                lefts += [self.chunk_get_next(lefts[-1], "left")]
                if lefts[-1] not in all_visible_hexes:
                    break
            while True:
                rights += [self.chunk_get_next(rights[-1], "right")]
                if rights[-1] not in all_visible_hexes:
                    break
            horizontal_strips += lefts + rights
        chunks = set()
        for x in ups + downs:
            chunks.add(x)
        for x in horizontal_strips:
            chunks.add(x)
        return chunks

    def find_chunk_parent(self, cell):
        """
        Given a cell, which chunk does it belong to?
        Args:
            cell (Hexagon): cell we're interested in knowing the chunk of.
        Returns:
            Hexagon pointing to the center of the chunk.
        """
        # Generate a chunk with myself in the middle.
        test_chunk = TerrainChunk(cell, self.chunk_size, self.terrain_noise)
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
            chunk_hash (int): hash value used to determine things about this chunk.
        """
        if center not in self.chunk_list.keys():
            chunk = TerrainChunk(center, self.chunk_size, self.terrain_noise)
            self.chunk_list[center] = [k for k in chunk.chunk_cells.keys()]
            new_city_core = False
            xy = hex_math.cube_to_offset(center)
            noise_val = self.random_noise.noise2d(xy.x, xy.y) / 2.0 + 0.5  # Rescale to 0.0 to 1.0
            if noise_val >= 0.85:
                new_city_core = True
            for k, v in chunk.chunk_cells.items():
                # Todo: this is a hack, figure out why overlapping chunks are ever generated.
                if k in self.hexagon_map.keys():
                    print(f"duplicate hex: {k}.")
                    continue
                self.hexagon_map[k] = v
                if k == Hexagon(0, 0, 0):
                    self.hexagon_map[center].terrain_type = 15
                    self.hexagon_map[center].sprite_id = '15'
                    self.add_building(center, Building(0))
                    terrain_map.city_cores[k] = "friendly"
                # Add an enemy city core, not on a water tile.
                elif k == center and new_city_core and int(self.hexagon_map[center].terrain_type) > 2:
                    if self.add_core(center):
                        print(f"Enemy core added at: {center}.")
                        self.hexagon_map[center].terrain_type = 16
                        self.hexagon_map[center].sprite_id = '16'
                        terrain_map.city_cores[k] = "enemy"
                # temporary, for testing
                elif k == Hexagon(19, -11, -8):
                    self.hexagon_map[center].terrain_type = 16
                    self.hexagon_map[center].sprite_id = '16'
                    terrain_map.city_cores[k] = "enemy"


    def add_safe_area(self, center, safe_type=0, radius=7):
        """
        Adds safety to terrain hexes. Can also be used to remove safety, by setting safe_type=0.
        City core safe area is highest priority and can't be overridden or removed.
        Args:
            center (Hexagon): center of the area to be made safe.
            safe_type (int): 0 for unsafe, 1 for city-core safety, 2 for other safety, -2 to remove other safety.
            radius (int): radius of the safe area.
        """
        safe_hexes = hex_math.get_hex_chunk(center, radius)
        for h in safe_hexes:
            if self.hexagon_map[h].safe == 1:
                continue
            self.hexagon_map[h].safe += safe_type

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

    def remove_building(self, hex_coords):
        """
        Removes the building from a cell.
        Args:
            hex_coords (Hexagon): coordinates of cell to modify.
        """
        del self.buildings[hex_coords]
        self.hexagon_map[hex_coords].building = None

    def add_core(self, center):
        """
        Attempts to add a core to this chunk. Minimum distance from another core determined in settings file.
        Args:
            center (Hexagon): hexagon to attempt to add the new city core at.
        Returns:
            True if this is a good chunk to add a core in, False if it isn't.
        """
        minimum = settings.minimum_core_distance
        for c in terrain_map.city_cores.keys():
            # If we're less than the minimum to any core, we're done.
            if hex_math.hex_distance(c, center) < minimum:
                return False
        return True

    def __len__(self):
        return len(self.chunk_list) * self.chunk_size * self.chunk_size


class TerrainChunk:
    """
    Stores metadata and data related to a terrain chunk.
    """
    def __init__(self, center, chunk_size, noise):
        self.center = center
        self.chunk_size = chunk_size
        self.chunk_cells = self.generate(self.center, noise)

    def generate(self, center, noise):
        """
        Generates a chunk, sized as given. Current algorithm is to generate a "rectangle". Why a rectangle? Because that's the shape of a window, and it allows chunks to be accessed as x/y coordinates of their centers.
        Args:
            center (Hexagon): the q, r, and s coordinates for the center of the chunk.
        Returns:
            A dictionary of terrain hexes, containing chunk_size * chunk_size items.
        """
        n_bins = settings.terrain_sprite_bins
        x_dim, y_dim = (self.chunk_size, self.chunk_size)
        chunk_cells = {}
        # Why all this futzing around with dimensions // 2? Because I wanted the start of the chunk to be centered in the middle of the chunk.
        r_min = -x_dim // 2
        r_max = x_dim // 2
        for r in range(r_min, r_max + 1):
            r_offset = r // 2
            q_min = -(y_dim // 2) - r_offset
            q_max = y_dim // 2 - r_offset
            for q in range(q_min, q_max + 1):
                qq = center.q + q
                rr = center.r + r
                h = Hexagon(qq, rr, -qq - rr)
                # Normalize to offset grid coordinates, because we want to sample the noise at points right next to each other.
                xy = hex_math.cube_to_offset(h)
                damp = settings.noise_damping_factor
                noise_val = noise.noise2d(xy.x * damp, xy.y * damp) / 2.0 + 0.5  # Rescale to 0.0 to 1.0
                # Find the closest value in the list to our noise value. We want to normalize to a sprite.
                t = min(range(len(n_bins)), key=lambda i: abs(n_bins[i] - noise_val))
                terrain_type = str(t)
                sprite_id = terrain_type
                chunk_cells[h] = TerrainCell(terrain_type, sprite_id)
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
        self.safe = 0
        self.visible = 0

    def __str__(self):
        return f"Terrain: {self.terrain_type}, id: {self.sprite_id}, building: {self.building}, safe: {self.safe}, visible: {self.visible}"


class Building:
    """
    A class to store the different buildings in.
    """
    _sprite_to_building = {0: "core claimed", 1: "RB", 2: "HR", 3: "protection tower", 4: "sensor tower", 5: "energy tower"}

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

    def draw_terrain(self):
        """
        Generate the sprites to put into the render batch.
        """
        self.children = []  # Hack. But I don't need many copies of the same hexes.
        for hexagon, hex_properties in terrain_map.hexagon_map.items():
            if hexagon not in scroller.visible_hexes:
                try:
                    self.map_sprites_batch.remove(f"{hexagon.q}_{hexagon.r}_{hexagon.s}")
                except Exception:
                    pass
                continue
            position = hex_math.hex_to_pixel(layout, hexagon, False)
            anchor = sprite_width // 2, sprite_height // 2
            sprite_id = hex_properties.sprite_id
            sprite = Sprite(sprite_images[sprite_id], position=position, anchor=anchor)
            try:
                self.map_sprites_batch.add(sprite, z=-hexagon.r, name=f"{hexagon.q}_{hexagon.r}_{hexagon.s}")
            except Exception:
                pass
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
        self.modifier = None
        self.selection = set()
        self.unit_move = False

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
            c = ''
            if h in terrain_map.chunk_list:
                c = " chunk"
            info = f"({h.q}, {h.r}, {h.s}){c}. {terrain_map.hexagon_map[h]}"
            print(info)
            text_layer.update_label(info)
        # This will get split out into it
        else:
            b = None
            if self.key is None:
                self.default_click(h)
            elif self.key is ord('q'):  # or 97
                # Place a test building.
                b = Building(1)
            elif self.key is ord('d'):
                if terrain_map.hexagon_map[h].visible != 0:
                    print("delete")
                    building_layer.remove_building(h)
                    network_layer.remove_network(h)
                else:
                    print("can't delete under fog")
            elif self.key is ord('p'):
                b = Building(3)
            elif self.key is ord('e'):
                if terrain_map.hexagon_map[h].visible != 0:
                    network_layer.plop_network(h, "energy")
                else:
                    print("Can't network in fog-of-war.")
            elif self.key is ord('s'):
                b = Building(4)
            elif self.key is ord('t'):
                unit_layer.add_unit(h, 1)
            elif self.key is ord('r'):
                b = Building(5)
            if b is not None and terrain_map.hexagon_map[h].visible != 0:
                building_layer.plop_building(h, b)
            elif b is not None and terrain_map.hexagon_map[h].visible == 0:
                print("Can't build in fog-of-war.")

    def on_mouse_release(self, x, y, button, modifiers):
        # This may not be the best way to track movement, but self.unit_move has the start cell.
        # So we move it to the new cell and clear movement.
        p = Point(x + scroller.offset[0], y + scroller.offset[1])
        h = hex_math.pixel_to_hex(layout, p)
        if self.unit_move:
            print(f"Moving unit from {self.unit_move} to {h}")
            unit_layer.move_unit(self.unit_move, h)
            self.unit_move = False

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
        self.modifier = modifiers

    def on_key_release(self, key, modifiers):
        self.key = None
        self.modifier = None

    def default_click(self, h):
        position = hex_math.hex_to_pixel(layout, h, False)
        # Todo: Figure out the issue causing hexes to sometime not be properly selected, probably rouning.
        if h in unit_layer.units.keys():
            self.unit_move = h
        else:
            anchor = sprite_width / 2, sprite_height / 2
            sprite = Sprite(sprite_images["select red border"], position=position, anchor=anchor)
            try:
                self.selected_batch.add(sprite, z=-h.r, name=f"{h.q}_{h.r}_{h.s}_red")
                self.selection.add(h)
            except Exception:
                self.selected_batch.remove(f"{h.q}_{h.r}_{h.s}_red")
                self.selection.remove(h)
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
        self.children = []
        for k, building in terrain_map.buildings.items():
            if k not in scroller.visible_hexes:
                try:
                    self.buildings_batch.remove(f"{k.q}_{k.r}_{k.s}")
                except Exception:
                    pass
                continue
            if not terrain_map.hexagon_map[k].visible:
                continue
            powered = network_map.network[k]["powered"]
            position = hex_math.hex_to_pixel(layout, k, False)
            anchor = sprite_width / 2, sprite_height / 2
            p = " off"
            if powered:
                p = " on"
            if building.building_id == 0:
                p = ''
            sprite = Sprite(sprite_images[f"{building.sprite_id}{p}"], position=position, anchor=anchor)
            try:
                self.buildings_batch.add(sprite, z=-k.r, name=f"{k.q}_{k.r}_{k.s}")
            except Exception:
                self.buildings_batch.remove(f"{k.q}_{k.r}_{k.s}")
                self.buildings_batch.add(sprite, z=-k.r, name=f"{k.q}_{k.r}_{k.s}")
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
            network_layer.plop_network(cell, "sink")
            terrain_map.add_building(cell, building)
            if building.building_id == 3 and network_map.network[cell]["powered"]:
                terrain_map.add_safe_area(cell, 2, 3)
                overlay_layer.draw_safe()
            elif building.building_id == 4 and network_map.network[cell]["powered"]:
                fog_layer.add_visible_area(cell, 2, 5)
                fog_layer.draw_fog()
            self.draw_buildings()
        else:
            print("Building already exists, skipping.")

    def remove_building(self, cell):
        """
        Removes a building.
        Args:
            cell (Hexagon): hex to remove the building from.
        """
        if cell not in terrain_map.buildings.keys():
            print("No building.")
        elif terrain_map.buildings[cell].building_id == 0:
            print("Can't remove city cores.")
        else:
            name = f"{cell.q}_{cell.r}_{cell.s}"
            building_id = terrain_map.buildings[cell].building_id
            terrain_map.remove_building(cell)
            self.buildings_batch.remove(name)
            self.draw_buildings()
            if building_id == 3 and network_map.network[cell]["powered"]:
                terrain_map.add_safe_area(cell, -2, 3)
                overlay_layer.draw_safe()
            elif building_id == 4 and network_map.network[cell]["powered"]:
                fog_layer.add_visible_area(cell, -2, 5)
                fog_layer.draw_fog()


class FogLayer(ScrollableLayer):
    """
    Class to hold the fog of war.
    """
    def __init__(self):
        super().__init__()
        self.fog_batch = BatchNode()
        self.fog_batch.position = layout.origin.x, layout.origin.y

    def add_visible_area(self, center, visible_type=0, radius=7):
        """
        Adds a visible area to terrain hexes. Can also be used to remove visibility, by setting safe_type=0.
        Args:
            center (Hexagon): center of the area to be made safe.
            visible_type (int): 0 for unsafe, 1 for city-core visibility, 2 for other visibility, -2 to remove other visibility.
            radius (int): radius of the visible area.
        """
        visible_hexes = hex_math.get_hex_chunk(center, radius)
        for h in visible_hexes:
            if terrain_map.hexagon_map[h].visible == 1:
                continue
            terrain_map.hexagon_map[h].visible += visible_type

    def draw_fog(self):
        # Todo: Handle fog drawing over buildings/networks that have been culled due to scrolling.
        self.children = []
        viewport_hexes = scroller.visible_hexes
        for k in viewport_hexes:
            try:
                h = terrain_map.hexagon_map[k]
            except Exception:
                continue
            if h.visible == 0:
                position = hex_math.hex_to_pixel(layout, k, False)
                anchor = sprite_width / 2, sprite_height / 2
                sprite_id = "fog"
                sprite = Sprite(sprite_images[sprite_id], position=position, anchor=anchor, opacity=223)
                try:
                    self.fog_batch.add(sprite, z=-k.r, name=f"{k.q}_{k.r}_{k.s}")
                except Exception:
                    pass
            else:
                try:
                    self.fog_batch.remove(f"{k.q}_{k.r}_{k.s}")
                except Exception:
                    pass
        self.add(self.fog_batch)


class OverlayLayer(ScrollableLayer):
    def __init__(self):
        super().__init__()
        self.overlay_batch = BatchNode()
        self.overlay_batch.position = layout.origin.x, layout.origin.y
        self.draw_safe()

    _neighbour_to_edge_sprite = {0: "right", 1: "bottom right", 2: "bottom left", 3: "left", 4: "top left", 5: "top right"}

    def draw_safe(self):
        self.children = []
        for k, h in terrain_map.hexagon_map.items():
            if k not in scroller.visible_hexes:
                for idx in range(6):
                    try:
                        self.overlay_batch.remove(f"{k.q}_{k.r}_{k.s}_{idx}")
                    except Exception:
                        pass
                continue
            if h.safe != 0:
                neighbours = [terrain_map.hexagon_map[hex_math.hex_neighbor(k, x)].safe for x in range(6)]
                position = hex_math.hex_to_pixel(layout, k, False)
                anchor = sprite_width / 2, sprite_height / 2
                for idx, n in enumerate(neighbours):
                    # print(h.safe, neighbours)
                    if n == 0:
                        sprite_id = f"safe {self._neighbour_to_edge_sprite[idx]}"
                        sprite = Sprite(sprite_images[sprite_id], position=position, anchor=anchor)
                        # I should probably squash these images into one image first, but this works for now.
                        try:
                            self.overlay_batch.add(sprite, z=-k.r, name=f"{k.q}_{k.r}_{k.s}_{idx}")
                        except Exception:
                            pass
                    else:
                        # In this case, we may have already drawn an overlay here that needs to be removed.
                        # Try to remove it.
                        try:
                            self.overlay_batch.remove(f"{k.q}_{k.r}_{k.s}_{idx}")
                        except Exception:
                            pass
            else:
                # Now we check hexes that aren't safe that may have been drawn on. There seems like there is a better way to do this...
                neighbours = []
                for x in range(6):
                    try:
                        neighbours += [terrain_map.hexagon_map[hex_math.hex_neighbor(k, x)].safe]
                    except KeyError:
                        pass  # We're off the edge of the hexes we've made. ToDo: limit to viewport?
                for idx, n in enumerate(neighbours):
                    if n == 0:
                        try:
                            self.overlay_batch.remove(f"{k.q}_{k.r}_{k.s}_{idx}")
                        except Exception:
                            pass
        self.add(self.overlay_batch)

    def set_focus(self, *args, **kwargs):
        super().set_focus(*args, **kwargs)


class Network:
    """
    Class to store the data structures related to the networks.
    I've split these from the terrain because I think there's going to be some significant complexity here.
    """
    def __init__(self):
        """
        Dictionary will be of the form {Hexagon(q, r, s): {"type": "network type", "powered": True/False}, ...}
        Possible values for network type are "energy", "control" and "sink". Energy means this network transports energy, control means it transports control signals and sink means it needs energy and control signals.
        Powered indicated that this network node is recieving energy.
        """
        self.network = {Hexagon(0, 0, 0): {"type": "start", "powered": True}}

    def update_powered(self):
        """
        Update all nodes in the network as to whether they're powered or not.
        """
        powered = self.find_all_connected(Hexagon(0, 0, 0))
        for n in self.network:
            previous_powered = self.network[n]["powered"]
            if n in powered:
                self.network[n]["powered"] = True
            else:
                self.network[n]["powered"] = False
            try:
                if terrain_map.buildings[n].building_id == 3:
                    p = 0
                    # This tile is making the transition from unpowered to powered
                    if self.network[n]["powered"] and not previous_powered:
                        p = 2
                    # This tile was previously powered but isn't anymore.
                    elif not self.network[n]["powered"] and previous_powered:
                        p = -2
                    terrain_map.add_safe_area(n, p, 3)
                    overlay_layer.draw_safe()
            except KeyError:
                pass
            try:
                if terrain_map.buildings[n].building_id == 4:
                    p = 0
                    # This tile is making the transition from unpowered to powered
                    if self.network[n]["powered"] and not previous_powered:
                        p = 2
                    # This tile was previously powered but isn't anymore.
                    elif not self.network[n]["powered"] and previous_powered:
                        p = -2
                    fog_layer.add_visible_area(n, p, 5)
                    fog_layer.draw_fog()
            except KeyError:
                pass


    def find_connected(self, cell_source, cell_destination):
        """
        Checks to see if the source cell is connected to a destination cell.
        Uses A*. Dijkstra’s may be better with multiple sources.
        Args:
            cell_source (Hexagon): hex cell that we are starting from.
            cell_destination (Hexagon): hex cell that we want to find a path to.
        Returns:
            Either a list containing the hexes that need to be traversed for the path, or None if they aren't connected.
        """
        q = PriorityQueue()
        q.put((0, cell_source))
        visited = {}
        total_cost = {}
        visited[cell_source] = None
        total_cost[cell_source] = 0

        while not q.empty():
            _, current = q.get()
            if current == cell_destination:
                return visited
            neighbours = [hex_math.hex_neighbor(current, x) for x in range(6) if hex_math.hex_neighbor(current, x) in self.network.keys()]
            for next_cell in neighbours:
                new_cost = total_cost[current] + 1
                if next_cell not in total_cost.keys() or new_cost < total_cost[next_cell]:
                    total_cost[next_cell] = new_cost
                    p = new_cost + hex_math.hex_distance(cell_destination, next_cell)
                    q.put((p, next_cell))
                    visited[next_cell] = current
        return None

    def find_all_connected(self, start_cell):
        """
        Finds all all the cells connected to the current cell.
        Args:
            start_cell (Hexagon): cell we want to determine connectivity from.
            visited (list): cells that we have visited already and don't need to be checked again.
        Returns:
            List of cells that are connected.
        """
        return self.find_all_connected_inner(start_cell, set())

    def find_all_connected_inner(self, start_cell, visited):
        if start_cell in visited:
            return visited
        visited.add(start_cell)
        neighbours = [hex_math.hex_neighbor(start_cell, x) for x in range(6) if
                      hex_math.hex_neighbor(start_cell, x) in self.network.keys()]
        for n in neighbours:
            if n not in visited:
                visited.union(self.find_all_connected_inner(n, visited))
        return visited

    def __len__(self):
        return len(self.network)


class NetworkLayer(ScrollableLayer):
    _neighbour_to_edge_sprite = {0: "right", 1: "bottom right", 2: "bottom left", 3: "left", 4: "top left", 5: "top right"}
    def __init__(self):
        super().__init__()
        self.network_batch = BatchNode()
        self.network_batch.position = layout.origin.x, layout.origin.y

    def draw_network(self):
        """
        Handles drawing of the network.
        """
        self.children = []
        network_map.update_powered()
        for k, h in network_map.network.items():
            if k not in scroller.visible_hexes:
                for idx in range(7):
                    try:
                        self.network_batch.remove(f"{k.q}_{k.r}_{k.s}_{idx}")
                    except Exception:
                        pass
                continue
            if not terrain_map.hexagon_map[k].visible:
                continue
            if h["type"] == "start":
                continue
            neighbours = []
            for x in range(6):
                try:
                    neighbours += [network_map.network[hex_math.hex_neighbor(k, x)]]
                except Exception:
                    neighbours += [{"type": None}]
            position = hex_math.hex_to_pixel(layout, k, False)
            anchor = sprite_width / 2, sprite_height / 2
            powered = "off"
            if h["powered"]:
                powered = "on"
            sprite = Sprite(sprite_images[f"energy network center {powered}"], position=position, anchor=anchor)
            try:
                self.network_batch.add(sprite, z=-k.r - 10, name=f"{k.q}_{k.r}_{k.s}_6")
            except Exception:
                self.network_batch.remove(f"{k.q}_{k.r}_{k.s}_6")
                self.network_batch.add(sprite, z=-k.r - 10, name=f"{k.q}_{k.r}_{k.s}_6")
            for idx, n in enumerate(neighbours):
                if n["type"] in (h["type"], "start", "energy", "sink"):
                    try:
                        sprite_name = f"energy network {self._neighbour_to_edge_sprite[idx]} {powered}"
                    except Exception:
                        pass
                    sprite = Sprite(sprite_images[sprite_name], position=position, anchor=anchor)
                    try:
                        self.network_batch.add(sprite, z=-k.r, name=f"{k.q}_{k.r}_{k.s}_{idx}")
                    except Exception:
                        self.network_batch.remove(f"{k.q}_{k.r}_{k.s}_{idx}")
                        self.network_batch.add(sprite, z=-k.r, name=f"{k.q}_{k.r}_{k.s}_{idx}")
        self.add(self.network_batch)

    def plop_network(self, cell, network_type="energy"):
        """
        Adds the network with the given type at the current tile.
        Mostly a stub to get things working right now.
        Args:
            cell (Hexagon): where do we want to plop this building?
            network_type (str): id of the building to add.
        """
        if cell not in network_map.network.keys():
            n = network_map.find_connected(cell, Hexagon(0, 0, 0))
            powered = False
            if n is not None:
                powered = True
                # Going to either need to tell neighbours to check themselves again, or force a redraw and reparse of the whole network, which could be painful.
            network_map.network[cell] = {"type": network_type, "powered": powered}
            self.draw_network()
            building_layer.draw_buildings()
        else:
            print("Network already exists, skipping.")

    def remove_network(self, cell):
        if cell not in network_map.network.keys():
            print("No network.")
        elif network_map.network[cell]["type"] == "start":
            print("Can't remove city core network.")
        else:
            del network_map.network[cell]
            for idx in range(0, 7):
                try:
                    self.network_batch.remove(f"{cell.q}_{cell.r}_{cell.s}_{idx}")
                except Exception:
                    pass  # This sprite must already exist, so we skip it.

            # And cleanup neighbours.
            # Code presently removes all but center sprite from neighbours, but they'll be redrawn. Todo: fix
            for x in range(6):
                n = hex_math.hex_neighbor(cell, x)
                for y in range(6):
                    try:
                        self.network_batch.remove(f"{n.q}_{n.r}_{n.s}_{y}")
                    except Exception:
                        pass  # This sprite must already exist, so we skip it.)
            self.draw_network()
            building_layer.draw_buildings()

    def set_focus(self, *args, **kwargs):
        super().set_focus(*args, **kwargs)


class InputScrolling(ScrollingManager):
    is_event_handler = True

    def __init__(self, center):
        super().__init__()
        self.center = list(center)
        self.scroll_inc = 32
        self.offset = [0, 0]
        self.visible_hexes = helpers.find_visible_hexes(sprite_width, layout, self, safe=True)

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
            self.update_visible()
            # Update the display layers when we scroll.
            terrain_layer.draw_terrain()
            building_layer.draw_buildings()
            overlay_layer.draw_safe()
            network_layer.draw_network()
            fog_layer.draw_fog()
            enemy_layer.spawn_enemies()
            enemy_layer.draw_enemies()
            # Generate more terrain chunks.
            terrain_map.fill_viewport_chunks()

    def set_focus(self, *args, **kwargs):
        super().set_focus(*args, **kwargs)

    def scroll(self, new_center):
        self.set_focus(*new_center)

    def update_visible(self):
        self.visible_hexes = helpers.find_visible_hexes(sprite_width, layout, self, safe=True)


class UnitLayer(ScrollableLayer):
    """
    Class to handle units.
    """
    is_event_handler = True

    def __init__(self):
        super().__init__()
        self.units = {}
        self.units_batch = BatchNode()
        self.units_batch.position = layout.origin.x, layout.origin.y

    def set_focus(self, *args, **kwargs):
        super().set_focus(*args, **kwargs)

    def add_unit(self, unit_position, unit_id, unit=None, move=False):
        """
        Instantiates a unit at the given position. Units can be on top of networks, but not on top ob buildings.
        Args:
            unit_id (int): if of the unit.
            unit_position (Hexagon): position to create the unit at.
            unit (Unit): unit if we're using this function with an existing unit.
            move (Bool): True is this is the add after a move, false otherwise.
        Returns:
            True if the unit was added, False otherwise.
        """
        # If there's a building here, we wan't place a unit.
        if unit_position in self.units.keys():
            print("Unit already exists here.")
            return False
        else:
            try:
                _ = terrain_map.buildings[unit_position]
                print("Can't spawn unit on buildings")
                return False
            except KeyError:
                if unit is None:
                    u = Unit(unit_position, unit_id)
                else:
                    u = unit
                self.units[unit_position] = u
                if not move:
                    fog_layer.add_visible_area(unit_position, 2, u.vision_range)
                self.draw_units()
                fog_layer.draw_fog()
        return True

    def remove_unit(self, unit_position, move=False):
        """
        Removes the unit at the given hex position.
        Args:
            unit_position (Hexagon): hexagon for the cell to remove the unit from.
            move (Bool): True is this is the add after a move, false otherwise.
        """
        try:
            u = self.units[unit_position]
            del self.units[unit_position]
            if not move:
                fog_layer.add_visible_area(unit_position, -2, u.vision_range)
            self.units_batch.remove(f"{unit_position.q}_{unit_position.r}_{unit_position.s}")
            self.draw_units()
            fog_layer.draw_fog()
        except KeyError:
            print("can't remove non-existent unit.")

    def move_unit(self, start_cell, end_cell):
        """
        Handles movement of a unit.
        Args:
            start_cell (Hexagon): cell the unit is moving from.
            end_cell (Hexagon): cell a unit is moving to.
        """
        u = self.units[start_cell]
        path = self.find_path(start_cell, end_cell, True)
        u.move_path = path
        self.remove_unit(start_cell, move=True)
        if not self.add_unit(end_cell, u.unit_id, u, move=True):
            self.add_unit(start_cell, u.unit_id, u, move=True)
            print("Unit move failed.")

    def draw_units(self):
        self.children = []
        for k, unit in self.units.items():
            if k not in scroller.visible_hexes:
                try:
                    self.units_batch.remove(f"{k.q}_{k.r}_{k.s}")
                except Exception:
                    pass
                continue
            position = hex_math.hex_to_pixel(layout, k, False)
            anchor = sprite_width / 2, sprite_height / 2
            if unit.move_path != []:
                end = unit.move_path[-1]
                start = unit.move_path[0]
                end_pos = hex_math.hex_to_pixel(layout, end, False)
                start_pos = hex_math.hex_to_pixel(layout, start, False)
                sprite = Sprite(sprite_images[f"{unit.sprite_id}"], position=start_pos, anchor=anchor)
                # Todo: Figure how to make this actually follow my path.
                sprite.do(UnitMover(unit.move_path, unit.speed, unit.vision_range))
                try:
                    self.units_batch.add(sprite, z=-k.r, name=f"{k.q}_{k.r}_{k.s}")
                except Exception:
                    self.units_batch.remove(f"{k.q}_{k.r}_{k.s}")
                    self.units_batch.add(sprite, z=-k.r, name=f"{k.q}_{k.r}_{k.s}")
                unit.move_path = []
            else:
                sprite = Sprite(sprite_images[f"{unit.sprite_id}"], position=position, anchor=anchor)
                try:
                    self.units_batch.add(sprite, z=-k.r, name=f"{k.q}_{k.r}_{k.s}")
                except Exception:
                    self.units_batch.remove(f"{k.q}_{k.r}_{k.s}")
                    self.units_batch.add(sprite, z=-k.r, name=f"{k.q}_{k.r}_{k.s}")
        self.add(self.units_batch)

    def find_path(self, start_cell, end_cell, include_start=False):
        """
        Finds a path between two hexagon cells.
        Args:
            start_cell (Hexagon): hex cell that we are starting from.
            end_cell (Hexagon): hex cell that we want to find a path to.
            include_start (bool): True if the start cell should be included in the list, false otherwise.
        Returns:
            A list of the hexes that need to be traversed to build a path.
        """
        visited = self.a_star(start_cell, end_cell)
        current = end_cell
        path = []
        while current != start_cell:
            path.append(current)
            current = visited[current]
        if include_start:
            path.append(start_cell)
        path.reverse()
        return path

    def a_star(self, start_cell, end_cell):
        """
        Determines if the start cell is connected to the end cell.
        Args:
            start_cell (Hexagon): hex cell that we are starting from.
            end_cell (Hexagon): hex cell that we want to find a path to.
        Returns:
            A list containing the hexes that were traversed to determine a path.
        """
        q = PriorityQueue()
        q.put((0, start_cell))
        visited = {}
        total_cost = {}
        visited[start_cell] = None
        total_cost[start_cell] = 0

        while not q.empty():
            _, current = q.get()
            if current == end_cell:
                break
            neighbours = [hex_math.hex_neighbor(current, x) for x in range(6)]
            for next_cell in neighbours:
                new_cost = total_cost[current] + 1
                if next_cell not in total_cost.keys() or new_cost < total_cost[next_cell]:
                    if next_cell in terrain_map.buildings.keys():
                        # Don't path over a building, go around.
                        continue
                    total_cost[next_cell] = new_cost
                    next_priority = new_cost + hex_math.hex_distance(end_cell, next_cell)
                    q.put((next_priority, next_cell))
                    visited[next_cell] = current
        return visited


class Unit:
    """
    Store information about a specific unit.
    """
    # Probably move this into a data file at some point.
    _unit_stats = {1: {"name": "hover tank", "speed": .25, "sprite_id": "tank", "vision": 3}}

    def __init__(self, position, unit_id):
        self.position = position
        self.unit_id = unit_id
        self.unit_stats = self._unit_stats[unit_id]
        self.sprite_id = self.unit_stats["sprite_id"]
        self.speed = self.unit_stats["speed"]
        self.name = self.unit_stats["name"]
        self.vision_range = self.unit_stats["vision"]
        self.move_path = []

    def __str__(self):
        return f"{self.name} at {self.position}"


class UnitMover(Action):
    def __init__(self, unit_path, unit_speed, vision_range):
        super().__init__()
        self.path = unit_path
        self.speed = unit_speed
        self.time = self.speed
        self.last = self.path[0]
        self.vision_range = vision_range

    def step(self, dt):
        self.time += dt
        if self.time >= self.speed:
            self.time = 0
            try:
                next_hex = self.path.pop(0)
                if self.vision_range != 0:
                    fog_layer.add_visible_area(self.last, -2, self.vision_range)
                    fog_layer.add_visible_area(next_hex, 2, self.vision_range)
                    fog_layer.draw_fog()
                    enemy_layer.draw_enemies()
                position = hex_math.hex_to_pixel(layout, next_hex, False)
                self.target.position = position
                self.last = next_hex
            except IndexError:
                pass
                # Todo: figure out how to remove this action now that it's done.


class EnemyLayer(ScrollableLayer):
    def __init__(self):
        super().__init__()
        self.enemies = {}
        self.enemy_batch = BatchNode()
        self.enemy_batch.position = layout.origin.x, layout.origin.y
        self.enemy_level = 1
        self.current_level = 0

    def set_focus(self, *args, **kwargs):
        super().set_focus(*args, **kwargs)

    def draw_enemies(self):
        """
        Handles drawing of all visible enemy units.
        """
        self.children = []
        for k, enemy in self.enemies.items():
            if k not in scroller.visible_hexes:
                try:
                    self.units_batch.remove(f"{k.q}_{k.r}_{k.s}")
                except Exception:
                    pass
                continue
            if terrain_map.hexagon_map[k].visible == 0:
                continue
            position = hex_math.hex_to_pixel(layout, k, False)
            anchor = sprite_width / 2, sprite_height / 2
            if enemy.move_path != []:
                start = enemy.move_path[0]
                start_pos = hex_math.hex_to_pixel(layout, start, False)
                sprite = Sprite(sprite_images[f"{enemy.sprite_id}"], position=start_pos, anchor=anchor)
                # Todo: Figure how to make this actually follow my path.
                sprite.do(UnitMover(enemy.move_path, enemy.speed, 0))
                try:
                    self.enemy_batch.add(sprite, z=-k.r, name=f"{k.q}_{k.r}_{k.s}")
                except Exception:
                    self.enemy_batch.remove(f"{k.q}_{k.r}_{k.s}")
                    self.enemy_batch.add(sprite, z=-k.r, name=f"{k.q}_{k.r}_{k.s}")
                enemy.move_path = []
            else:
                sprite = Sprite(sprite_images[f"{enemy.sprite_id}"], position=position, anchor=anchor)
                try:
                    self.enemy_batch.add(sprite, z=-k.r, name=f"{k.q}_{k.r}_{k.s}")
                except Exception:
                    self.enemy_batch.remove(f"{k.q}_{k.r}_{k.s}")
                    self.enemy_batch.add(sprite, z=-k.r, name=f"{k.q}_{k.r}_{k.s}")
        self.add(self.enemy_batch)

    def spawn_enemies(self):
        """
        Handles actual spawning of enemies.
        Right now, only spawns enemies for visible sections of the screen for testing, but they should be able to spawn and attack anywhere on the map.
        Enemies will only spawn if there aren't already too many enemies around, as denoted by enemy_level. This is subject to change, but is a way to limit difficulty for now.
        """
        enemy_cores = [k for k, v in terrain_map.city_cores.items() if v == "enemy"]
        # Only spawn an enemy if we've discovered another enemy core, otherwise give the player some time to expand, etc.
        if enemy_cores is not [] and self.current_level < self.enemy_level:
            window_center = Point(scroller.fx, scroller.fy)
            window_center_hex = hex_math.pixel_to_hex(layout, window_center)
            # find the closest enemy core to the view's center.
            distances = [hex_math.hex_distance(x, window_center_hex) for x in enemy_cores]
            closest = enemy_cores[distances.index(min(distances))]
            tries = 10
            while self.current_level < self.enemy_level and tries > 0:
                self.spawn_single_enemy(closest)
                tries -= 1

    def spawn_single_enemy(self, core):
        """
        Spawns a single enemy.
        Won't spawn enemies on safe areas, so this could technically result in a situation where enemies won't spawn. This'll need to be fixed.
        Todo: more complex spawning logic and checks.
        Args:
            core (Hexagon): coordinates for the core to spawn around.
        Returns:
            False if unable to spawn an enemy, otherwise True
        """
        if terrain_map.hexagon_map[core].safe == 0:
            new_q = randint(-2, 2) + core.q
            new_r = randint(-2, 2) + core.r
            new_s = -new_q - new_r
            new_position = Hexagon(new_q, new_r, new_s)
            if new_position in terrain_map.buildings.keys() or new_position in unit_layer.units.keys() or new_position == core:
                # Don't spawn on building or unit. Energy networks are fine.
                return False
            try:
                _ = self.enemies[new_position]
            except KeyError:
                print(f"Spawning enemy at {new_position}")
                e = Enemy(new_position, 1)
                self.enemies[new_position] = e
                self.current_level += e.level
            self.move_enemies()
            return True
        return False

    def move_enemies(self):
        """
        Moves the enemy creep towards a target to attack.
        Right now, it'll head for the closest network connection or building.
        """
        for e in self.enemies.values():
            print(e)
            if e.move_path is [] and e.target != e.position:
                print(e)
                self.find_target(e)
                print(e)
            else:
                pass
            print(e)

    def find_target(self, enemy):
        """
        Finds a target, and a path to a target, for a given enemy creep. Flips a coin (50/50 chance) of choosing a building or network connection to go after.
        Args:
            enemy (Enemy): enemy creep to find a target for.
        Returns:
            Nothing, but updates the move_path and target attributes of the enemy instance.
        """
        if randint(0, 1) == 0:
            buildings = list(terrain_map.buildings.keys())
            distances = [hex_math.hex_distance(x, enemy.position) for x in buildings]
            closest = buildings[distances.index(min(distances))]
        else:
            networks = list(network_map.network.keys())
            distances = [hex_math.hex_distance(x, enemy.position) for x in networks]
            closest = networks[distances.index(min(distances))]
        enemy.target = closest
        enemy.move_path = self.find_path(enemy.position, enemy.target, True)


    # Todo: generalize these two functions so that they can be pulled out.
    # Don't need a second copy of them here and in units.
    def find_path(self, start_cell, end_cell, include_start=False):
        """
        Finds a path between two hexagon cells.
        Args:
            start_cell (Hexagon): hex cell that we are starting from.
            end_cell (Hexagon): hex cell that we want to find a path to.
            include_start (bool): True if the start cell should be included in the list, false otherwise.
        Returns:
            A list of the hexes that need to be traversed to build a path.
        """
        visited = self.a_star(start_cell, end_cell)
        current = end_cell
        path = []
        while current != start_cell:
            path.append(current)
            current = visited[current]
        if include_start:
            path.append(start_cell)
        path.reverse()
        return path

    def a_star(self, start_cell, end_cell):
        """
        Determines if the start cell is connected to the end cell.
        Args:
            start_cell (Hexagon): hex cell that we are starting from.
            end_cell (Hexagon): hex cell that we want to find a path to.
        Returns:
            A list containing the hexes that were traversed to determine a path.
        """
        q = PriorityQueue()
        q.put((0, start_cell))
        visited = {}
        total_cost = {}
        visited[start_cell] = None
        total_cost[start_cell] = 0

        while not q.empty():
            _, current = q.get()
            if current == end_cell:
                break
            neighbours = [hex_math.hex_neighbor(current, x) for x in range(6)]
            for next_cell in neighbours:
                new_cost = total_cost[current] + 1
                if next_cell not in total_cost.keys() or new_cost < total_cost[next_cell]:
                    total_cost[next_cell] = new_cost
                    next_priority = new_cost + hex_math.hex_distance(end_cell, next_cell)
                    q.put((next_priority, next_cell))
                    visited[next_cell] = current
        return visited


class Enemy:
    """
    Class to store information related to enemy creeps.
    """
    _enemy_stats = settings.enemy_stats

    def __init__(self, position, enemy_id):
        self.position = position
        self.enemy_id = enemy_id
        self.name = self._enemy_stats[enemy_id]["name"]
        self.speed = self._enemy_stats[enemy_id]["speed"]
        self.sprite_id = self._enemy_stats[enemy_id]["sprite_id"]
        self.health = self._enemy_stats[enemy_id]["health"]
        self.level = self._enemy_stats[enemy_id]["level"]
        self.move_path = []
        self.target = None

    def __str__(self):
        return f"{self.name} at {self.position} has health {self.health} and is attacking {self.target}"


class MenuLayer(Menu):
    is_event_handler = True

    def __init__(self):
        super().__init__()


class TextOverlay(Layer):
    def __init__(self):
        super().__init__()
        self.text = Label(text="", font_size=24, font_name="Arial", anchor_x="left", anchor_y="center", x=20, y=20, color=(255, 255, 255, 255))
        self.update_label("Info")
        self.add(self.text)

    def update_label(self, label_text=''):
        self.text.element.text = label_text

    def set_view(self, *args, **kwargs):
        super().set_view(*args, **kwargs)


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
    terrain_map.city_cores[Hexagon(0, 0, 0)] = "friendly"
    input_layer = InputLayer()
    terrain_layer = MapLayer()
    terrain_layer.draw_terrain()
    terrain_layer.set_focus(*layout.origin)
    terrain_map.fill_viewport_chunks()
    terrain_map.add_safe_area(Hexagon(0, 0, 0), 1, 7)
    overlay_layer = OverlayLayer()
    network_map = Network()
    network_layer = NetworkLayer()
    text_layer = TextOverlay()
    unit_layer = UnitLayer()
    fog_layer = FogLayer()
    fog_layer.add_visible_area(Hexagon(0, 0, 0), 1, 9)
    fog_layer.draw_fog()
    enemy_layer = EnemyLayer()

    scroller.add(terrain_layer, z=0)
    scroller.add(network_layer, z=1)
    scroller.add(unit_layer, z=2)
    scroller.add(building_layer, z=2)
    scroller.add(enemy_layer, z=2)
    scroller.add(fog_layer, z=3)
    scroller.add(overlay_layer, z=4)
    scroller.add(input_layer, z=5)
    building_layer.draw_buildings()
    director.window.push_handlers(keyboard)
    director.run(Scene(scroller, text_layer))
