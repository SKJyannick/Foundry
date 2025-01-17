from functools import lru_cache

from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QImage, QPainter, Qt

from foundry.core.graphics_set.GraphicsSet import GraphicsSetProtocol
from foundry.core.palette import NESPalette
from foundry.core.palette.PaletteGroup import MutablePaletteGroup
from foundry.game.File import ROM
from foundry.game.gfx.drawable import MASK_COLOR, apply_selection_overlay
from foundry.game.gfx.drawable.Tile import Tile

TSA_BANK_0 = 0 * 256
TSA_BANK_1 = 1 * 256
TSA_BANK_2 = 2 * 256
TSA_BANK_3 = 3 * 256


@lru_cache(2**10)
def get_block(block_index: int, palette_group: MutablePaletteGroup, graphics_set: GraphicsSetProtocol, tsa_data: bytes):
    if block_index > 0xFF:
        rom_block_index = ROM().get_byte(block_index)  # block_index is an offset into the graphic memory
        block = Block(rom_block_index, palette_group, graphics_set, tsa_data)
    else:
        block = Block(block_index, palette_group, graphics_set, tsa_data)

    return block


class Block:
    SIDE_LENGTH = 2 * Tile.SIDE_LENGTH
    WIDTH = SIDE_LENGTH
    HEIGHT = SIDE_LENGTH

    PIXEL_COUNT = WIDTH * HEIGHT

    tsa_data = bytes()

    _block_cache = {}

    def __init__(
        self,
        block_index: int,
        palette_group: tuple[tuple[int, ...], ...],
        graphics_set: GraphicsSetProtocol,
        tsa_data: bytes,
        mirrored: bool = False,
    ):
        self.index = block_index
        self.palette_group = palette_group
        self.palette_index = (block_index & 0b1100_0000) >> 6

        # can't hash list, so turn it into a string instead
        self._block_id = hash((block_index, palette_group, graphics_set))

        lu = tsa_data[TSA_BANK_0 + block_index]
        ld = tsa_data[TSA_BANK_1 + block_index]
        ru = tsa_data[TSA_BANK_2 + block_index]
        rd = tsa_data[TSA_BANK_3 + block_index]

        self.lu_tile = Tile(lu, self.palette_group, self.palette_index, graphics_set)
        self.ld_tile = Tile(ld, self.palette_group, self.palette_index, graphics_set)

        if mirrored:
            self.ru_tile = Tile(lu, self.palette_group, self.palette_index, graphics_set, mirrored=True)
            self.rd_tile = Tile(ld, self.palette_group, self.palette_index, graphics_set, mirrored=True)
        else:
            self.ru_tile = Tile(ru, self.palette_group, self.palette_index, graphics_set)
            self.rd_tile = Tile(rd, self.palette_group, self.palette_index, graphics_set)

        self.image = QImage(Block.WIDTH, Block.HEIGHT, QImage.Format_RGB888)
        painter = QPainter(self.image)

        painter.drawImage(QPoint(0, 0), self.lu_tile.as_image())
        painter.drawImage(QPoint(Tile.WIDTH, 0), self.ru_tile.as_image())
        painter.drawImage(QPoint(0, Tile.HEIGHT), self.ld_tile.as_image())
        painter.drawImage(QPoint(Tile.WIDTH, Tile.HEIGHT), self.rd_tile.as_image())

        painter.end()

        if _image_only_one_color(self.image) and self.image.pixelColor(0, 0) == QColor(*MASK_COLOR):
            self._whole_block_is_transparent = True
        else:
            self._whole_block_is_transparent = False

    @classmethod
    def clear_cache(cls):
        cls._block_cache.clear()

    def draw(self, painter: QPainter, x, y, block_length, selected=False, transparent=False):
        block_attributes = (self._block_id, block_length, selected, transparent)

        if block_attributes not in Block._block_cache:
            image = self.image.copy()

            if block_length != Block.WIDTH:
                image = image.scaled(block_length, block_length)

            # mask out the transparent pixels first
            mask = image.createMaskFromColor(QColor(*MASK_COLOR).rgb(), Qt.MaskOutColor)
            image.setAlphaChannel(mask)

            if not transparent:  # or self._whole_block_is_transparent:
                image = self._replace_transparent_with_background(image)

            if selected:
                apply_selection_overlay(image, mask)

            Block._block_cache[block_attributes] = image

        painter.drawImage(x, y, Block._block_cache[block_attributes])

    def _replace_transparent_with_background(self, image: QImage):
        # draw image on background layer, to fill transparent pixels
        background = image.copy()
        color = NESPalette[self.palette_group[self.palette_index][0]]
        background.fill(color)

        _painter = QPainter(background)
        _painter.drawImage(QPoint(), image)
        _painter.end()

        return background


def _image_only_one_color(image):
    copy = image.copy()

    copy.convertTo(QImage.Format_Indexed8)

    return copy.colorCount() == 1
