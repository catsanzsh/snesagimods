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

    __slots__ = ("tiles", "tile_size_px") # Added tile_size_px to store tile dimension

    def __init__(self, surface: pygame.Surface, tile_size: int = 8):
        self.tiles: List[pygame.Surface] = []
        self.tile_size_px = tile_size  # Store the tile size
        w, h = surface.get_size()

        num_tiles_x = w // tile_size
        num_tiles_y = h // tile_size

        for ty_idx in range(num_tiles_y):
            for tx_idx in range(num_tiles_x):
                tx = tx_idx * tile_size
                ty = ty_idx * tile_size
                # Create subsurface for each tile
                tile = surface.subsurface((tx, ty, tile_size, tile_size)).convert_alpha()
                self.tiles.append(tile)

    def get(self, index: int) -> pygame.Surface:
        if not self.tiles:
            # Tileset is empty or failed to load tiles. Return a placeholder.
            # print(f"Warning: TileSet is empty. Returning a dummy transparent tile.", file=sys.stderr) # Optional warning
            dummy_tile = pygame.Surface((self.tile_size_px, self.tile_size_px), pygame.SRCALPHA)
            dummy_tile.fill((0, 0, 0, 0))  # Fully transparent
            return dummy_tile

        if 0 <= index < len(self.tiles):
            return self.tiles[index]
        else:
            # Index is out of bounds, return a default tile (e.g., the first tile)
            # This prevents crashing if map data refers to a non-existent tile index.
            # print(f"Warning: Tile index {index} is out of bounds (0-{len(self.tiles)-1}). Returning tile 0.", file=sys.stderr) # Optional warning
            return self.tiles[0]


    def __len__(self) -> int:
        return len(self.tiles)


class TileMap:
    """A 2‑D array of tile indices that can be any size."""

    __slots__ = ("width", "height", "map", "priority", "tileset")

    def __init__(self, width: int, height: int, tileset: TileSet, priority: int = 0):
        self.width, self.height = width, height
        self.priority = priority  # lower = drawn first
        self.tileset = tileset    # Store the TileSet instance
        # Fill with tile 0 (transparent or default) by default
        self.map: List[List[int]] = [[0] * width for _ in range(height)]

    def set_tile(self, x: int, y: int, index: int) -> None:
        self.map[y][x] = index

    def draw(self, screen: pygame.Surface, *, scale: int = 2) -> None:
        # Assuming 8x8 tiles as per engine description, could use self.tileset.tile_size_px if variable
        tile_render_size = 8 * scale  # scaled tile size
        for y, row in enumerate(self.map):
            for x, index in enumerate(row):
                tile = self.tileset.get(index) # Use self.tileset
                if scale != 1:
                    # Scale the tile if needed
                    tile = pygame.transform.scale(tile, (tile_render_size, tile_render_size))
                screen.blit(tile, (x * tile_render_size, y * tile_render_size))


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
            s = pygame.transform.scale(s, (int(s.get_width() * scale), int(s.get_height() * scale)))
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
        self.layers: List[object] = []

    def add_layer(self, layer: object) -> None:
        """Add any drawable (with attrs draw & priority) to the render stack."""
        self.layers.append(layer)
        self.layers.sort(key=lambda l: getattr(l, "priority", 0))

    def run(self, update_cb=None, fps: int = 60):
        """Enter the game loop. *update_cb* is called every frame before draw."""
        running = True
        while running:
            for evt in pygame.event.get():
                if evt.type == pygame.QUIT:
                    running = False
            
            if update_cb:
                update_cb()
            
            self.window.fill((0, 0, 0))
            for layer in self.layers:
                layer.draw(self.window, scale=self.scale)
            
            pygame.display.flip()
            self.clock.tick(fps)
        pygame.quit()


# -----------------------------------------------------------------------------
# Example usage (invoke the script directly)
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python snes_renderer.py <tilesheet.png> <tilemap.txt> <mario.png>")
        sys.exit(1)

    tilesheet_path, tilemap_path, mario_path = map(Path, sys.argv[1:])

    pygame.init() 
    tilesheet_surface = pygame.image.load(str(tilesheet_path)).convert_alpha()
    tileset = TileSet(tilesheet_surface) # Default 8x8 tiles

    tm_rows: List[List[int]] = []
    try:
        with tilemap_path.open() as f:
            for line in f:
                stripped_line = line.strip()
                if stripped_line: # Ensure line is not empty
                    tm_rows.append([int(i) for i in stripped_line.split()])
    except FileNotFoundError:
        print(f"Error: Tilemap file '{tilemap_path}' not found.")
        sys.exit(1)
    except ValueError:
        print(f"Error: Tilemap file '{tilemap_path}' contains non-integer values.")
        sys.exit(1)
    
    if not tm_rows or not tm_rows[0]: # Check if tilemap is effectively empty
        print(f"Error: Tilemap file '{tilemap_path}' is empty or improperly formatted.")
        sys.exit(1)
        
    width, height = len(tm_rows[0]), len(tm_rows)
    tilemap = TileMap(width, height, tileset, priority=0)
    tilemap.map = tm_rows

    mario_surface = pygame.image.load(str(mario_path)).convert_alpha()
    mario_sprite = Sprite(mario_surface, x=120, y=120, priority=1)

    renderer = SNESRenderer(window_scale=2)
    renderer.add_layer(tilemap)
    renderer.add_layer(mario_sprite)

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

        # Optional clamping for Mario sprite
        # logical_width, logical_height = renderer.logical_size
        # sprite_width, sprite_height = mario_sprite.surface.get_size()
        # mario_sprite.x = max(0, min(mario_sprite.x, logical_width - sprite_width))
        # mario_sprite.y = max(0, min(mario_sprite.y, logical_height - sprite_height))

    renderer.run(update)
    sys.exit(0)
