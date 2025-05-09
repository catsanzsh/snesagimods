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
            raise ValueError("SNES palettes are exactly 16 colours (including index 0).")
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
        # Basic bounds check for safety, though SNES might wrap or show garbage
        if 0 <= index < len(self.tiles):
            return self.tiles[index]
        # Return a default tile (e.g., transparent or first tile) if out of bounds
        # This prevents a crash if map data is incorrect.
        # For simplicity, let's return the first tile or handle error as preferred.
        # Returning the first tile:
        # if self.tiles: return self.tiles[0]
        # Or, to be more strict and match original behavior of crashing on bad index:
        return self.tiles[index]


    def __len__(self) -> int:
        return len(self.tiles)


class TileMap:
    """A 2‑D array of tile indices that can be any size."""

    __slots__ = ("width", "height", "map", "priority", "tileset") # Added tileset

    def __init__(self, width: int, height: int, tileset: TileSet, priority: int = 0): # Added tileset argument
        self.width, self.height = width, height
        self.priority = priority  # lower = drawn first
        self.tileset = tileset    # Store the TileSet instance
        # Fill with tile 0 (transparent) by default
        self.map: List[List[int]] = [[0] * width for _ in range(height)]

    def set_tile(self, x: int, y: int, index: int) -> None:
        self.map[y][x] = index

    def draw(self, screen: pygame.Surface, *, scale: int = 2) -> None: # Removed tileset from parameters
        ts = 8 * scale  # scaled tile size
        for y, row in enumerate(self.map):
            for x, index in enumerate(row):
                tile = self.tileset.get(index) # Use self.tileset
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
        # Pygame is initialized in the main block before asset loading,
        # which is good. Calling it again here is safe.
        pygame.init()
        self.scale = window_scale
        self.logical_size = (256, 224)  # SNES low‑res mode
        self.window = pygame.display.set_mode(
            (self.logical_size[0] * window_scale, self.logical_size[1] * window_scale)
        )
        pygame.display.set_caption("SNESRenderer Engine")
        self.clock = pygame.time.Clock()
        self.layers: List[object] = []  # TileMap or Sprite (anything with .draw and .priority)

    # ------------------------------------------------------------------ API --
    def add_layer(self, layer: object) -> None:
        """Add any drawable (with attrs draw & priority) to the render stack."""
        self.layers.append(layer)
        # Sort by priority: lower values drawn first (e.g., 0=background, 1=sprites)
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
            self.window.fill((0, 0, 0)) # Black background for the window
            for layer in self.layers:
                # Now all layers should have a compatible draw method:
                # draw(self, screen, *, scale)
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
    # * tilesheet.png – a 128×128 sheet of 8×8 tiles (16 × 16 tiles) with transparency
    # * mario.png – a 16×24 (or any size) sprite of Mario with transparency
    # * tilemap.txt – plain text rows of tile indices separated by spaces
    if len(sys.argv) != 4:
        print("Usage: python snes_renderer.py <tilesheet.png> <tilemap.txt> <mario.png>")
        sys.exit(1)

    tilesheet_path, tilemap_path, mario_path = map(Path, sys.argv[1:])

    pygame.init() # Initialize Pygame modules for image loading etc.
    tilesheet_surface = pygame.image.load(str(tilesheet_path)).convert_alpha() # Use str() for Path with older Pygame
    tileset = TileSet(tilesheet_surface)

    # --------------------------- load tilemap file
    tm_rows: List[List[int]] = []
    with tilemap_path.open() as f:
        for line in f:
            tm_rows.append([int(i) for i in line.strip().split()])
    
    if not tm_rows or not tm_rows[0]:
        print(f"Error: Tilemap file '{tilemap_path}' is empty or improperly formatted.")
        sys.exit(1)
        
    width, height = len(tm_rows[0]), len(tm_rows)
    # Pass the loaded tileset to the TileMap constructor
    tilemap = TileMap(width, height, tileset, priority=0)
    tilemap.map = tm_rows

    # --------------------------- sprite
    mario_surface = pygame.image.load(str(mario_path)).convert_alpha() # Use str() for Path with older Pygame
    mario_sprite = Sprite(mario_surface, x=120, y=120, priority=1)

    # --------------------------- renderer + layers
    renderer = SNESRenderer(window_scale=2)
    renderer.add_layer(tilemap)
    renderer.add_layer(mario_sprite)

    # --------------------------- simple input update
    def update():
        keys = pygame.key.get_pressed()
        move_speed = 2 
        if keys[pygame.K_LEFT]:
            mario_sprite.x -= move_speed
        if keys[pygame.K_RIGHT]:
            mario_sprite.x += move_speed
        if keys[pygame.K_UP]:
            mario_sprite.y -= move_speed
        if keys[pygame.K_DOWN]:
            mario_sprite.y += move_speed

        # Optional: Clamp Mario's position to stay within logical screen bounds
        # logical_width, logical_height = renderer.logical_size
        # mario_width, mario_height = mario_sprite.surface.get_size()
        # mario_sprite.x = max(0, min(mario_sprite.x, logical_width - mario_width))
        # mario_sprite.y = max(0, min(mario_sprite.y, logical_height - mario_height))


    renderer.run(update)
    # pygame.quit() is called by renderer.run(), so no need to call it again here.
    sys.exit(0)
