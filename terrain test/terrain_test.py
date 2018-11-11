from PIL import Image

from random import randint
from collections import namedtuple
from math import sqrt
import os
import sys
sys.path.append('..')
import hex_math

Hexagon = namedtuple("Hex", ["q", "r", "s"])
Point = namedtuple("Point", ["x", "y"])

sprite_width = 8
sprite_height = 4
pointy_width = sprite_width // sqrt(3)  # This is the distance from the center to one of the corners.

window_width = 1920
window_height = 1200

layout_size = Point(pointy_width, sprite_height)
layout = hex_math.Layout(hex_math.layout_pointy, layout_size, Point(window_width // 2, window_height // 2))


def get_current_viewport():
    """
    Get the current viewport coordinates. I feel like Cocos2d should handle this, but I can't seem to find it.
    Returns:
        Dictionary with te key being one of "top_left", "bottom_right", "top_right" or "bottom_left".
        Values are (x, y) pixel coordinates.
    """
    x = window_width // 2
    y = window_height // 2

    tl = x - window_width // 2, y + window_height // 2
    bl = x - window_width // 2, y - window_height // 2
    tr = x + window_width // 2, y + window_height // 2
    br = x + window_width // 2, y - window_height // 2
    coords = {"top_left": tl, "bottom_right": br, "top_right": tr, "bottom_left": bl}
    return coords


def get_current_viewport_hexes():
    """
    Find the corner hexes for the viewport.
    Returns:
        A dictionary of the hegaxons corresponding to the corners of the viewport.
    """
    coordinates = get_current_viewport()
    return {k: hex_math.pixel_to_hex(layout, Point(*v)) for k, v in coordinates.items()}


def find_visible_hexes():
    """
    Finds all of the visible hexes in the current viewport.
    Returns:
        Set of all of the hexes visible in the current viewport.
    """
    corners = get_current_viewport_hexes()
    top_line = hex_math.hex_linedraw(corners["top_left"], corners["top_right"])
    bottom_line = hex_math.hex_linedraw(corners["bottom_left"], corners["bottom_right"])
    visible = []
    for x in zip(top_line, bottom_line):
        visible += hex_math.hex_linedraw(*x)
    #  Use a set to make sure we don't have any duplicates.
    return {x for x in visible}


class Terrain:
    """
    A class to store the terrain.
    """
    def __init__(self, chunk_size=31, random_seed=42):
        self.city_cores = []
        self.random_seed = random_seed
        self.chunk_size = chunk_size

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
        for c in chunks:
            self.generate_chunk(c)
        if len(self.chunk_list) > before_size:  # Only redraw map if we've added hexes.
            terrain_layer.draw_terrain(terrain_map)

    def find_visible_chunks(self):
        """
        Used to find the visible chunks in a viewport. May return chunks that aren't quite visible to be safe.
        Returns:
            A list of TerrainChunk objects that are visible in the current viewport.
        """
        # screen_center = hex_math.pixel_to_hex(layout, Point(window_width // 2, window_height // 2))
        # center = self.find_chunk_parent(screen_center)
        # all_visible_hexes = find_visible_hexes()
        # chunks = self.find_chunks(center)
        # for c in chunks:
        #     self.chunk_list[c] = None
        # return chunks
        # Algorithm works like this:
        # First,
        x = window_width // 2
        y = window_height // 2
        screen_center = hex_math.pixel_to_hex(layout, Point(x, y))
        center = self.find_chunk_parent(screen_center)
        return self.find_chunks(center)

    def chunk_get_next(self, center, direction="up"):
        q_offset = self.chunk_size // 2
        directions = {
            "up": (center.q - q_offset - 1,
                   center.r + self.chunk_size + 1,
                   -(center.q - q_offset - 1) - (center.r + self.chunk_size)),
            "down": (center.q + q_offset + 1,
                     center.r - self.chunk_size - 1,
                     -(center.q + q_offset + 1) - (center.r - self.chunk_size)),
            "left": (center.q - self.chunk_size,
                     center.r,
                     -(center.q - self.chunk_size) - center.r),
            "right": (center.q + self.chunk_size,
                      center.r,
                      -(center.q + self.chunk_size) - center.r),
        }
        return Hexagon(*directions[direction])

    def find_chunks(self, center):
        all_visible_hexes = find_visible_hexes()
        print(all_visible_hexes)
        ups = [center]
        while True:
            ups += [self.chunk_get_next(ups[-1], "up")]
            print(ups[-1])
            if ups[-1] not in all_visible_hexes:
                break
        downs = [center]
        while True:
            downs += [self.chunk_get_next(ups[-1], "down")]
            print(downs[-1])
            if downs[-1] not in all_visible_hexes:
                break

        # q_offset = self.chunk_size // 2
        # left = Hexagon(center.q - self.chunk_size, center.r, -(center.q - self.chunk_size) - center.r)
        # right = Hexagon(center.q + self.chunk_size, center.r, -(center.q + self.chunk_size) - center.r)
        # up = Hexagon(center.q - q_offset - 1, center.r + self.chunk_size + 1, -(center.q - q_offset - 1) - (center.r + self.chunk_size))
        # down = Hexagon(center.q + q_offset + 1, center.r - self.chunk_size -1, -(center.q + q_offset + 1) - (center.r - self.chunk_size))
        # # And the four diagonals, based on the previous ones.
        # up_left = Hexagon(up.q - self.chunk_size, up.r, -(up.q - self.chunk_size) - up.r)
        # up_right = Hexagon(up.q + self.chunk_size, up.r, -(up.q + self.chunk_size) - up.r)
        # down_left = Hexagon(down.q - self.chunk_size, down.r, -(down.q - self.chunk_size) - down.r)
        # down_right = Hexagon(down.q + self.chunk_size, down.r, -(down.q + self.chunk_size) - down.r)
        # chunks = up, down, left, right, up_left, up_right, down_left, down_right
        chunks = set()
        for x in [ups + downs]:
            chunks.add(x[0])
        print(chunks)
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
                # Todo: this is a hack, figure out why overlapping chunks are ever generated.
                if k in self.hexagon_map.keys():
                    print(f"duplicate hex: {k}.")
                    continue
                self.hexagon_map[k] = v
                if k == Hexagon(0, 0, 0):
                    self.hexagon_map[center].terrain_type = 14
                    self.hexagon_map[center].sprite_id = '14'

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
                terrain_type = str(randint(0, 12))
                sprite_id = terrain_type
                chunk_cells[h] = TerrainCell(terrain_type, sprite_id)
        return chunk_cells

    def __len__(self):
        return len(self.chunk_cells)

    def __str__(self):
        return f"Chunk at {self.center} contains {len(self.chunk_cells)} hexes"


class TerrainCell:
    """
    A class to store specific terrain cells and their associated properties. This is just a cell, and doesn't know coordinates, or anything.
    """
    def __init__(self, terrain_type=0, sprite_id=None):
        self.terrain_type = terrain_type
        self.sprite_id = sprite_id
        self.safe = 0
        self.visible = 0

    def __str__(self):
        return f"Terrain: {self.terrain_type}, id: {self.sprite_id}"


class TerrainImage:
    def __init__(self):
        self.image_width = window_width
        self.image_height = window_height
        self.image = Image.new('RGBA', (window_width, window_height), 0)

    def draw_terrain(self, terrain):
        print(f"{len(terrain.hexagon_map)} hexes drawn in {len(terrain.chunk_list)} chunks.")
        for hexagon, properties in terrain.hexagon_map.items():
            sprite_id = properties.sprite_id
            sprite = sprite_images[sprite_id]
            hex_pos = hex_math.hex_to_pixel(layout, hexagon)
            hex_pos = (int(hex_pos[0]), int(hex_pos[1]))
            self.image.paste(sprite, hex_pos, mask=sprite)

    def save_terrain(self):
        with open("terrain.png", 'wb') as f:
            self.image.save(f, format='png')


def load_spritesheet(path):
    """
    Loads the spritesheet from the given path.
    Args:
        path: Path to spritesheet file..
    Returns:
        Dictionary contraining the sprites. Key is the sprite's index extension, value is a Sprite object.
        Index goes Left t right, top to bottom.
    """
    images = {}
    spritesheet_path = os.path.join(path, "8x8 spritesheet.png")
    img = Image.open(spritesheet_path)
    images["select"] = Image.open(os.path.join(path, "../sprites/select.png"))
    for y in range(0, 32, 8):
        for x in range(0, 32, 8):
            sprite_id = str((x // 8) * 4 + (y // 8))
            box = (x, y, x + 8, y + 8)
            sprite = img.crop(box)
            images[sprite_id] = sprite
    return images


if __name__ == "__main__":
    sprite_images = load_spritesheet('')
    terrain_map = Terrain(7)
    terrain_map.generate_chunk(Hexagon(0, 0, 0))

    terrain_layer = TerrainImage()
    # terrain_map.fill_viewport_chunks()
    for x in find_visible_hexes():
        t = randint(1, 12)
        if x == Hexagon(0, 0, 0):
            t = '14'
        terrain_map.hexagon_map[x] = TerrainCell(t, str(t))
    terrain_layer.draw_terrain(terrain_map)
    terrain_layer.save_terrain()



