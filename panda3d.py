from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import Filename, Texture, OrthographicLens, PNMImage, Point2, NodePath, TextureStage, WindowProperties
from panda3d.core import TextNode, TransparencyAttrib, Lens, loadPrcFile, ConfigVariableString, CardMaker, \
    AntialiasAttrib, Filename
from datetime import datetime
import sys
from random import randint
from time import sleep
import hex_math


def load_sprite(texture_file=None):
    """
    Function to load and return a sprite.
    """
    print(texture_file)
    fn = Filename(texture_file)
    image = PNMImage(fn)
    w = image.getXSize()
    h = image.getYSize()
    new_w, new_h = convert_pixel_to_screen(w, h)
    sprite_image = Texture()
    sprite_image.load(image)

    # Needed to keep the textures from looking blurry.
    sprite_image.setMagfilter(Texture.FTNearest)
    sprite_image.setMinfilter(Texture.FTNearest)

    cm = CardMaker(texture_file)
    cm.setFrame(0, new_w, 0, new_h)
    card = render.attachNewNode(cm.generate())
    card.setTexture(sprite_image)
    card.setTransparency(TransparencyAttrib.MAlpha)
    card.setAntialias(AntialiasAttrib.MNone)
    return card, w

def convert_pixel_to_screen(x, y):
    """
    Converts pixel x/y coordinates to screen coordinates.
    """
    win_x, win_y = base.win.getSize()
    new_x = x / win_x
    new_y = y / win_y
    return new_x, new_y

def color_convert(r, g, b, a=255):
    """
    Converts from an 32b colour to a float colour.
    """
    return tuple(max(0, min(255, x)) / 255 for x in (r, g, b, a))


class Game(ShowBase):
    class Sprite:
        def __init__(self, sprite_path):
            self.sprite, w = load_sprite(sprite_path)
            self.width = w

        def getPos(self, *args):
            return self.sprite.getPos(*args)

        def setPos(self, *args):
            self.sprite.setPos(*args)

        def instanceTo(self, n):
            self.sprite.instanceTo(n)

    def __init__(self, sprites_dir):
        print(f"{datetime.now()}: Started init.")
        ShowBase.__init__(self)
        self.terrain_map = self.create_random_terrain(16, 16, 16)

        self.disableMouse()
        self.setBackgroundColor(color_convert(0, 0, 0))
        self.accept("escape", sys.exit)  # Escape quits
        self.gameTask = taskMgr.add(self.gameLoop, "gameLoop")
        self.camera_setup()
        self.is_down = base.mouseWatcherNode.is_button_down
        self.sprites = {}
        print(f"{datetime.now()}: Finished engine init..")
        self.load_sprites(sprites_dir)
        print(f"{datetime.now()}: {len(self.sprites)} sprites loaded.")
        self.draw_terrain()
        print(f"{datetime.now()}: {len(self.terrain_map)} terrain tiles drawn.")

    def load_sprites(self, sprites_dir):
        for sprite_id in range(1, 5):
            sprite = self.Sprite(f"{sprites_dir}/{sprite_id}.png")
            self.sprites[sprite_id] = sprite

    def camera_setup(self):
        lens = OrthographicLens()
        self.cam.node().setLens(lens)
        self.cam.setPos(0, 0, 0)

    def mover(self, to_move):
        curr = to_move.getPos()
        inc = 0.01
        if self.is_down('e'):
            to_move.setPos((curr[0], curr[1] - inc, curr[2]))
        elif self.is_down('q'):
            to_move.setPos((curr[0], curr[1] + inc, curr[2]))
        elif self.is_down('a'):
            to_move.setPos((curr[0] - inc, curr[1], curr[2]))
        elif self.is_down('d'):
            to_move.setPos((curr[0] + inc, curr[1], curr[2]))
        elif self.is_down('s'):
            to_move.setPos((curr[0], curr[1], curr[2] - inc))
        elif self.is_down('w'):
            to_move.setPos((curr[0], curr[1], curr[2] + inc))
        elif self.is_down('z'):
            to_move.setPos((0, 0, 0))
        elif self.is_down('x'):
            print(to_move.getPos())

    def click(self):
        if self.is_down("mouse3"):
            screen_x = base.mouseWatcherNode.getMouseX()
            screen_y = base.mouseWatcherNode.getMouseY()
            print(screen_x, screen_y)

    def create_random_terrain(self, x, y, z):
        out = {}
        for i in range(0, x):
            for j in range(0, y):
                for k in range(0, z):
                    k = (i, j, k)
                    out[k] = randint(1, 4)
        return out

    def draw_terrain(self):
        for tile_coords, sprite_id in self.terrain_map.items():
            sprite = self.sprites[sprite_id]
            node = render.attachNewNode(f"{tile_coords}: {sprite_id}")
            print(tile_coords)
            screen_x, screen_y = hex_math.tile_coords_to_screen(tile_coords)
            print(screen_x, screen_y)
            p = (screen_x, 1, screen_y)
            node.setPos(p)
            sprite.instanceTo(node)


    def gameLoop(self, task):
        self.mover(self.camera)
        self.click()
        return Task.cont

if __name__ == "__main__":
    sprites_dir = "sprites"
    app = Game(sprites_dir)
    app.run()