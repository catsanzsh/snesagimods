"""
SNESRenderer Engine
-------------------
A minimal Super Nintendo–style rendering engine in Python using Pygame.

Features
========
* 256 × 224 logical resolution (2× scaled to 512 × 448 by default)
* 8 × 8‑tile backgrounds with unlimited map size
* 16‑color palettes (one palette per tileset for simplicity)
* Ordered sprite layer with basic priority handling (0 = background‑back, higher = drawn later)
* Plug‑and‑play architecture so backgrounds / sprites are just Python objects with a ``draw`` method
* Clean, documented source built for extending to true SNES modes (mode‑7, HDMA, etc.)

This is **not** a byte‑perfect SNES PPU clone. Instead it gives you an ergonomic API to *use* SNES‑style assets (paletted tilesheets, tile‑maps, and OAM‑style sprites) inside any modern Pygame project.

Quick start
===========
>>> python snes_renderer.py assets/tilesheet.png assets/tilemap.txt assets/mario.png

The example at the bottom shows a tiled grassland background and a Mario sprite that you can move with the arrow keys.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

import pygame

# -----------------------------------------------------------------------------
# Core data structures
# -----------------------------------------------------------------------------

Color = Tuple[int, int, int]


class SNESPalette:
    """A simple 16‑color palette (RGB tuples in 0‑255 space)."""

    __slots__ = ("colors",)

    def __init__(self, colors: List[Color]):
        if len(colors) != 16:
            raise ValueError("SNES palettes are exactly 16 colours (including index 0).")
        self.colors: List[Color] = colors


class TileSet:
    """Loads 8×8 tiles from a paletted PNG (or any Pygame‑loadable Surface)."""

    __slots__ = ("tiles",)

    def __init__(self, surface: pygame.Surface, tile_size: int = 8):
        self.tiles: List[pygame.Surface] = []
        w, h = surface.get_size()
        for ty in range(0, h, tile_size):
            for tx in range(0, w, tile_size):
                tile = surface.subsurface((tx, ty, tile_size, tile_size)).convert_alpha()
                self.tiles.append(tile)

    def get(self, index: int) -> pygame.Surface:
        return self.tiles[index]

    def __len__(self) -> int:
        return len(self.tiles)


class TileMap:
    """A 2‑D array of tile indices that can be any size."""

    __slots__ = ("width", "height", "map", "priority")

    def __init__(self, width: int, height: int, priority: int = 0):
        self.width, self.height = width, height
        self.priority = priority  # lower = drawn first
        # Fill with tile 0 (transparent) by default
        self.map: List[List[int]] = [[0] * width for _ in range(height)]

    def set_tile(self, x: int, y: int, index: int) -> None:
        self.map[y][x] = index

    def draw(self, screen: pygame.Surface, tileset: TileSet, *, scale: int = 2) -> None:
        ts = 8 * scale  # scaled tile size
        for y, row in enumerate(self.map):
            for x, index in enumerate(row):
                tile = tileset.get(index)
                if scale != 1:
                    tile = pygame.transform.scale(tile, (ts, ts))
                screen.blit(tile, (x * ts, y * ts))


class Sprite:
    """A movable graphic with a priority (higher = in front)."""

    __slots__ = ("surface", "x", "y", "priority")

    def __init__(self, surface: pygame.Surface, x: int, y: int, priority: int = 1):
        self.surface = surface.convert_alpha()
        self.x, self.y = x, y
        self.priority = priority

    def draw(self, screen: pygame.Surface, *, scale: int = 2) -> None:
        s = self.surface
        if scale != 1:
            s = pygame.transform.scale(s, (s.get_width() * scale, s.get_height() * scale))
        screen.blit(s, (self.x * scale, self.y * scale))


# -----------------------------------------------------------------------------
# The main renderer & game‑loop helper
# -----------------------------------------------------------------------------

class SNESRenderer:
    """Keeps a layer list and handles a fixed‑timed main loop."""

    def __init__(self, window_scale: int = 2):
        pygame.init()
        self.scale = window_scale
        self.logical_size = (256, 224)  # SNES low‑res mode
        self.window = pygame.display.set_mode(
            (self.logical_size[0] * window_scale, self.logical_size[1] * window_scale)
        )
        pygame.display.set_caption("SNESRenderer Engine")
        self.clock = pygame.time.Clock()
        self.layers: List[object] = []  # TileMap or Sprite (anything with .draw)

    # ------------------------------------------------------------------ API --
    def add_layer(self, layer: object) -> None:
        """Add any drawable (with attrs draw & priority) to the render stack."""
        self.layers.append(layer)
        self.layers.sort(key=lambda l: getattr(l, "priority", 0))

    def run(self, update_cb=None, fps: int = 60):
        """Enter the game loop. *update_cb* is called every frame before draw."""
        running = True
        while running:
            # --------------- events
            for evt in pygame.event.get():
                if evt.type == pygame.QUIT:
                    running = False
            # --------------- update
            if update_cb:
                update_cb()
            # --------------- draw
            self.window.fill((0, 0, 0))
            for layer in self.layers:
                # TileMap draws need a tileset parameter. Sprites don't.
                if isinstance(layer, TileMap):
                    layer.draw(self.window, tileset, scale=self.scale)  # tileset provided later
                else:  # Sprite / other
                    layer.draw(self.window, scale=self.scale)
            pygame.display.flip()
            self.clock.tick(fps)
        pygame.quit()


# -----------------------------------------------------------------------------
# Example usage (invoke the script directly)
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    # ---------------------------------------------------------------- assets --
    # These are simple PNGs you create:
    # * tilesheet.png – a 128×128 sheet of 8×8 tiles (16 × 16 tiles) with transparency
    # * mario.png – a 16×24 (or any size) sprite of Mario with transparency
    # * tilemap.txt – plain text rows of tile indices separated by spaces
    if len(sys.argv) != 4:
        print("Usage: snes_renderer.py <tilesheet.png> <tilemap.txt> <mario.png>")
        sys.exit(1)

    tilesheet_path, tilemap_path, mario_path = map(Path, sys.argv[1:])

    pygame.init()
    tilesheet_surface = pygame.image.load(tilesheet_path).convert_alpha()
    tileset = TileSet(tilesheet_surface)

    # --------------------------- load tilemap file
    tm_rows: List[List[int]] = []
    with tilemap_path.open() as f:
        for line in f:
            tm_rows.append([int(i) for i in line.strip().split()])
    width, height = len(tm_rows[0]), len(tm_rows)
    tilemap = TileMap(width, height, priority=0)
    tilemap.map = tm_rows

    # --------------------------- sprite
    mario_surface = pygame.image.load(mario_path).convert_alpha()
    mario_sprite = Sprite(mario_surface, x=120, y=120, priority=1)

    # --------------------------- renderer + layers
    renderer = SNESRenderer(window_scale=2)
    renderer.add_layer(tilemap)
    renderer.add_layer(mario_sprite)

    # --------------------------- simple input update
    def update():
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            mario_sprite.x -= 2
        if keys[pygame.K_RIGHT]:
            mario_sprite.x += 2
        if keys[pygame.K_UP]:
            mario_sprite.y -= 2
        if keys[pygame.K_DOWN]:
            mario_sprite.y += 2

    renderer.run(update)
