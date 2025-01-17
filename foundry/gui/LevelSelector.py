from typing import Optional

from PySide6.QtCore import QMargins, QSize, Signal, SignalInstance
from PySide6.QtGui import QCloseEvent, QKeyEvent, QMouseEvent, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QScrollBar,
    QTabWidget,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from foundry.game.gfx.drawable.Block import Block
from foundry.game.level.Level import Level
from foundry.game.level.util import Level as LevelMeta
from foundry.game.level.util import get_world_levels
from foundry.game.level.WorldMap import WorldMap
from foundry.gui.Spinner import Spinner
from foundry.gui.WorldMapView import WorldMapView
from foundry.smb3parse.levels import WORLD_COUNT

WORLD_ITEMS = [
    "World Maps",
    "World 1",
    "World 2",
    "World 3",
    "World 4",
    "World 5",
    "World 6",
    "World 7",
    "World 8",
    "Lost Levels",
]

OBJECT_SET_ITEMS = [
    "0 Overworld",
    "1 Plains",
    "2 Dungeon",
    "3 Hilly",
    "4 Sky",
    "5 Piranha Plant",
    "6 Water",
    "7 Mushroom",
    "8 Pipe",
    "9 Desert",
    "A Ship",
    "B Giant",
    "C Ice",
    "D Cloudy",
    "E Underground",
    "F Spade Bonus",
]


OVERWORLD_MAPS_INDEX = 0
WORLD_1_INDEX = 1


def select_by_world_and_level(world: int, level: int) -> LevelMeta:
    return get_world_levels(world, Level.offsets)[level]


class LevelSelector(QDialog):
    def __init__(self, parent, *, start_level: Optional[tuple[int, int]] = None):
        super(LevelSelector, self).__init__(parent)

        self.setWindowTitle("Level Selector")
        self.setModal(True)

        self.level_name = ""

        self.object_set = 0
        self.object_data_offset = 0x0
        self.enemy_data_offset = 0x0

        self.world_label = QLabel(parent=self, text="World")
        self.world_list = QListWidget(parent=self)
        self.world_list.addItems(WORLD_ITEMS)

        self.world_list.itemDoubleClicked.connect(self.on_ok)
        self.world_list.itemSelectionChanged.connect(self.on_world_click)

        self.level_label = QLabel(parent=self, text="Level")
        self.level_list = QListWidget(parent=self)

        self.level_list.itemDoubleClicked.connect(self.on_ok)
        self.level_list.itemSelectionChanged.connect(self.on_level_click)

        self.enemy_data_label = QLabel(parent=self, text="Enemy Data")
        self.enemy_data_spinner = Spinner(parent=self)

        self.object_data_label = QLabel(parent=self, text="Object Data")
        self.object_data_spinner = Spinner(self)

        self.object_set_label = QLabel(parent=self, text="Object Set")
        self.object_set_dropdown = QComboBox(self)
        self.object_set_dropdown.addItems(OBJECT_SET_ITEMS)

        self.button_ok = QPushButton("Ok", self)
        self.button_ok.clicked.connect(self.on_ok)
        self.button_ok.setFocus()

        self.button_cancel = QPushButton("Cancel", self)
        self.button_cancel.clicked.connect(self.close)

        stock_level_widget = QWidget()
        stock_level_layout = QGridLayout(stock_level_widget)

        stock_level_layout.addWidget(self.world_label, 0, 0)
        stock_level_layout.addWidget(self.level_label, 0, 1)

        stock_level_layout.addWidget(self.world_list, 1, 0)
        stock_level_layout.addWidget(self.level_list, 1, 1)

        self.source_selector = QTabWidget()
        self.source_selector.addTab(stock_level_widget, "Stock Levels")

        for world_number in range(WORLD_COUNT - 1):
            world_number += 1

            world_map_select = WorldMapLevelSelect(world_number)
            world_map_select.level_selected.connect(self._on_level_selected_via_world_map)
            world_map_select.accepted.connect(self.on_ok)

            self.source_selector.addTab(world_map_select, f"W{world_number}")

        data_layout = QGridLayout()

        data_layout.addWidget(self.enemy_data_label, 0, 0)
        data_layout.addWidget(self.object_data_label, 0, 1)
        data_layout.addWidget(self.enemy_data_spinner, 1, 0)
        data_layout.addWidget(self.object_data_spinner, 1, 1)

        data_layout.addWidget(self.object_set_label, 2, 0)
        data_layout.addWidget(self.object_set_dropdown, 2, 1)

        data_layout.addWidget(self.button_ok, 3, 0)
        data_layout.addWidget(self.button_cancel, 3, 1)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.source_selector)
        main_layout.addLayout(data_layout)

        self.setLayout(main_layout)

        if start_level is None:
            self.world_list.setCurrentRow(1)  # select Level 1-1
            self.on_world_click()
        else:
            self.world_list.setCurrentRow(start_level[0])
            self.level_list.setCurrentRow(start_level[1])

    @property
    def current_level_index(self) -> tuple[int, int]:
        return self.world_list.currentRow(), self.level_list.currentRow()

    def keyPressEvent(self, key_event: QKeyEvent):
        if key_event.key() == Qt.Key_Escape:
            self.reject()

    def on_world_click(self):
        index = self.world_list.currentRow()

        assert index >= 0

        self.level_list.clear()

        self.level_list.addItems([level.display_information.name for level in get_world_levels(index, Level.offsets)])

        if self.level_list.count():
            self.level_list.setCurrentRow(0)

            self.on_level_click()

    def on_level_click(self):
        index = self.level_list.currentRow()

        assert index >= 0

        level_is_overworld = self.world_list.currentRow() == OVERWORLD_MAPS_INDEX

        level = get_world_levels(self.world_list.currentRow(), Level.offsets)[index]
        self.level_name = level.display_information.name

        object_data_for_lvl = level.generator_pointer

        if not level_is_overworld:
            object_data_for_lvl -= Level.HEADER_LENGTH

        if not level_is_overworld:
            enemy_data_for_lvl = level.enemy_pointer
        else:
            enemy_data_for_lvl = 0

        if enemy_data_for_lvl > 0:
            # data in look up table is off by one, since workshop ignores the first byte
            enemy_data_for_lvl -= 1

        self.enemy_data_spinner.setEnabled(not level_is_overworld)

        # if self.world_list.currentRow() >= WORLD_1_INDEX:
        object_set_index = level.tileset
        self.button_ok.setDisabled(level_is_overworld)

        self._fill_in_data(object_set_index, object_data_for_lvl, enemy_data_for_lvl)

    def _fill_in_data(self, object_set: int, layout_address: int, enemy_address: int):
        self.object_set_dropdown.setCurrentIndex(object_set)
        self.object_data_spinner.setValue(layout_address)
        self.enemy_data_spinner.setValue(enemy_address)

    def _on_level_selected_via_world_map(
        self, level_name: str, object_set: int, layout_address: int, enemy_address: int
    ):
        self.level_name = level_name

        self._fill_in_data(object_set, layout_address, enemy_address)

        level_is_overworld = object_set == OVERWORLD_MAPS_INDEX
        self.button_ok.setDisabled(level_is_overworld)
        self.enemy_data_spinner.setDisabled(level_is_overworld)

    def on_ok(self, _=None):
        self.object_set = self.object_set_dropdown.currentIndex()
        self.object_data_offset = self.object_data_spinner.value()
        # skip the first byte, because it seems useless
        self.enemy_data_offset = self.enemy_data_spinner.value() + 1

        self.accept()

    def closeEvent(self, _close_event: QCloseEvent):
        self.reject()


class WorldMapLevelSelect(QScrollArea):
    level_selected: SignalInstance = Signal(str, int, int, int)  # type: ignore
    accepted: SignalInstance = Signal()  # type: ignore

    def __init__(self, world_number: int):
        super(WorldMapLevelSelect, self).__init__()

        self.world = WorldMap(world_number)

        self.world_view = WorldMapView(self, self.world)
        self.world_view.setMouseTracking(True)

        self.setWidget(self.world_view)

        self.setMouseTracking(True)

    def mouseMoveEvent(self, event: QMouseEvent):
        x, y = self.world_view.mapFromParent(event.position().toPoint()).toTuple()

        x //= Block.WIDTH * 2
        y //= Block.HEIGHT * 2

        try:
            level_info = self.world.level_at_position(x, y)

            if level_info is None:
                self.setCursor(Qt.ArrowCursor)

                self.setToolTip("")
                QToolTip.hideText()
            else:
                self.setCursor(Qt.PointingHandCursor)

                level_name = self.world.level_name_at_position(x, y)

                object_set = level_info[0]
                object_set_name = OBJECT_SET_ITEMS[object_set].split(" ", 1)[1]
                layout_address, enemy_address = map(hex, level_info[1:])

                self.setToolTip(
                    f"<b>{level_name}</b><br/>"
                    f"<u>Type:</u> {object_set_name}<br/>"
                    f"<u>Objects:</u> {layout_address}<br/>"
                    f"<u>Enemies:</u> {enemy_address}"
                )
        except ValueError:
            pass

        return super(WorldMapLevelSelect, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        x, y = self.world_view.mapFromParent(event.position().toPoint()).toTuple()

        x //= Block.WIDTH * 2
        y //= Block.HEIGHT * 2

        try:
            level_info = self.world.level_at_position(x, y)
        except ValueError:
            level_info = None

        if level_info is not None:
            self.level_selected.emit(self.world.level_name_at_position(x, y), *level_info)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        self.mouseReleaseEvent(event)
        self.accepted.emit()

    def sizeHint(self) -> QSize:
        orig_size = super(WorldMapLevelSelect, self).sizeHint()

        scrollbar_width = QScrollBar().sizeHint().width()

        return orig_size.grownBy(QMargins(scrollbar_width, scrollbar_width, 0, 0))
