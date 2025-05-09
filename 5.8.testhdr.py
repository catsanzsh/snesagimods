from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Tuple

import pygame

# -----------------------------------------------------------------------------
# Core data structures
# -----------------------------------------------------------------------------

Color = Tuple[int, int, int]

# --- Palette Colors (RGB) ---
BLACK: Color = (0, 0, 0)
WHITE: Color = (255, 255, 255)
RED: Color = (200, 0, 0)
GREEN: Color = (0, 180, 0)
BLUE: Color = (0, 0, 200)
LIGHT_GRAY: Color = (200, 200, 200)
DARK_GRAY: Color = (100, 100, 100)
YELLOW: Color = (220, 220, 0)
TRANSPARENT_COLOR_KEY: Color = (255, 0, 255) # Magenta for transparency


class SNESPalette:
    """A simple 16‑color palette (RGB tuples in 0‑255 space)."""

    __slots__ = ("colors",)

    def __init__(self, colors: List[Color]):
        if len(colors) != 16:
            raise ValueError("SNES palettes are exactly 16 colours (including index 0).")
        self.colors: List[Color] = colors


class TileSet:
    """Loads tiles from a surface (e.g., a paletted PNG or any Pygame‑loadable Surface)."""

    __slots__ = ("tiles", "tile_size_px")

    def __init__(self, surface: pygame.Surface, tile_size: int = 8):
        self.tiles: List[pygame.Surface] = []
        self.tile_size_px = tile_size
        w, h = surface.get_size()

        num_tiles_x = w // tile_size
        num_tiles_y = h // tile_size

        for ty_idx in range(num_tiles_y):
            for tx_idx in range(num_tiles_x):
                tx = tx_idx * tile_size
                ty = ty_idx * tile_size
                # Create subsurface for each tile
                # Using convert_alpha() for potential per-pixel alpha in tiles.
                tile_surface = surface.subsurface((tx, ty, tile_size, tile_size)).convert_alpha()
                self.tiles.append(tile_surface)

    def get(self, index: int) -> pygame.Surface:
        if not self.tiles:
            # Tileset is empty or failed to load tiles. Return a placeholder.
            # print(f"Warning: TileSet is empty. Returning a dummy transparent tile.", file=sys.stderr)
            dummy_tile = pygame.Surface((self.tile_size_px, self.tile_size_px), pygame.SRCALPHA)
            dummy_tile.fill((0, 0, 0, 0))  # Fully transparent
            return dummy_tile

        if 0 <= index < len(self.tiles):
            return self.tiles[index]
        else:
            # Index is out of bounds, return a default tile (e.g., the first tile or a specific error tile)
            # print(f"Warning: Tile index {index} is out of bounds (0-{len(self.tiles)-1}). Returning tile 0.", file=sys.stderr)
            return self.tiles[0] # Default to first tile if out of bounds

    def __len__(self) -> int:
        return len(self.tiles)


class TileMap:
    """A 2‑D array of tile indices that can be any size."""

    __slots__ = ("width", "height", "map_data", "priority", "tileset") # Renamed 'map' to 'map_data'

    def __init__(self, width: int, height: int, tileset: TileSet, priority: int = 0):
        self.width, self.height = width, height
        self.priority = priority  # lower = drawn first
        self.tileset = tileset    # Store the TileSet instance
        # Fill with tile 0 (transparent or default) by default
        self.map_data: List[List[int]] = [[0] * width for _ in range(height)]

    def set_tile(self, x: int, y: int, index: int) -> None:
        if 0 <= y < self.height and 0 <= x < self.width:
            self.map_data[y][x] = index
        else:
            print(f"Warning: Tile coordinates ({x}, {y}) are out of map bounds.", file=sys.stderr)


    def get_tile_index(self, x: int, y: int) -> int:
        """Gets the tile index at the given map coordinates (tile units)."""
        if 0 <= y < self.height and 0 <= x < self.width:
            return self.map_data[y][x]
        return -1 # Or some other indicator for out-of-bounds

    def draw(self, screen: pygame.Surface, *, scale: int = 2) -> None:
        tile_render_size = self.tileset.tile_size_px * scale  # scaled tile size
        for y, row in enumerate(self.map_data):
            for x, index in enumerate(row):
                tile_surface = self.tileset.get(index)
                if scale != 1:
                    # Scale the tile if needed
                    scaled_tile_surface = pygame.transform.scale(tile_surface, (tile_render_size, tile_render_size))
                else:
                    scaled_tile_surface = tile_surface
                screen.blit(scaled_tile_surface, (x * tile_render_size, y * tile_render_size))


class Sprite:
    """A movable graphic with a priority (higher = in front)."""

    __slots__ = ("surface", "x", "y", "width", "height", "priority")

    def __init__(self, surface: pygame.Surface, x: int, y: int, priority: int = 1):
        self.surface = surface.convert_alpha() # Ensure per-pixel alpha
        self.x, self.y = x, y
        self.width = surface.get_width()
        self.height = surface.get_height()
        self.priority = priority

    def draw(self, screen: pygame.Surface, *, scale: int = 2) -> None:
        s = self.surface
        scaled_width = int(self.width * scale)
        scaled_height = int(self.height * scale)
        
        if scale != 1:
            s = pygame.transform.scale(s, (scaled_width, scaled_height))
        
        screen.blit(s, (self.x * scale, self.y * scale))

    def get_rect(self) -> pygame.Rect:
        """Returns the sprite's rectangle in logical coordinates."""
        return pygame.Rect(self.x, self.y, self.width, self.height)

# -----------------------------------------------------------------------------
# The main renderer & game‑loop helper
# -----------------------------------------------------------------------------

class SNESRenderer:
    """Keeps a layer list and handles a fixed‑timed main loop."""

    def __init__(self, window_scale: int = 2, logical_width: int = 256, logical_height: int = 224):
        pygame.init()
        self.scale = window_scale
        self.logical_size = (logical_width, logical_height)
        self.window = pygame.display.set_mode(
            (self.logical_size[0] * window_scale, self.logical_size[1] * window_scale)
        )
        pygame.display.set_caption("SNESRenderer Engine Demo")
        self.clock = pygame.time.Clock()
        self.layers: List[object] = [] # List of drawable objects (TileMap, Sprite)

    def add_layer(self, layer: object) -> None:
        """Add any drawable (with attrs draw & priority) to the render stack."""
        if not hasattr(layer, 'draw') or not hasattr(layer, 'priority'):
            raise ValueError("Layer must have 'draw' method and 'priority' attribute.")
        self.layers.append(layer)
        self.layers.sort(key=lambda l: getattr(l, "priority", 0))

    def run(self, update_cb=None, fps: int = 60):
        """Enter the game loop. *update_cb* is called every frame before draw."""
        running = True
        while running:
            for evt in pygame.event.get():
                if evt.type == pygame.QUIT:
                    running = False
                if evt.type == pygame.KEYDOWN:
                    if evt.key == pygame.K_ESCAPE:
                        running = False
            
            if update_cb:
                update_cb() # Call the user-defined update function
            
            self.window.fill(BLACK) # Clear screen
            for layer in self.layers:
                layer.draw(self.window, scale=self.scale)
            
            pygame.display.flip()
            self.clock.tick(fps)
        pygame.quit()


# -----------------------------------------------------------------------------
# Example usage (self-contained demo)
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    pygame.init() # Ensure Pygame is initialized

    # --- Game Parameters ---
    TILE_SIZE = 16 # Pixel size of a single tile
    PLAYER_SIZE = TILE_SIZE - 8 # Make player slightly smaller than a tile
    MOVE_SPEED = 2 # Player movement speed in logical pixels per frame

    # --- Define Tile Types (for map data) ---
    TILE_FLOOR = 0
    TILE_WALL = 1

    # --- Programmatically Create Tileset Surface ---
    # Create a surface for our tileset: 2 tiles wide (floor, wall), 1 tile high
    tilesheet_surface = pygame.Surface((TILE_SIZE * 2, TILE_SIZE), pygame.SRCALPHA)
    
    # Tile 0: Floor (Green)
    floor_tile_img = pygame.Surface((TILE_SIZE, TILE_SIZE))
    floor_tile_img.fill(GREEN)
    tilesheet_surface.blit(floor_tile_img, (0, 0))

    # Tile 1: Wall (Blue)
    wall_tile_img = pygame.Surface((TILE_SIZE, TILE_SIZE))
    wall_tile_img.fill(BLUE)
    tilesheet_surface.blit(wall_tile_img, (TILE_SIZE * 1, 0))
    
    # Create TileSet instance
    tileset = TileSet(tilesheet_surface, tile_size=TILE_SIZE)

    # --- Define Tilemap Data ---
    # 0 = Floor, 1 = Wall
    # Map dimensions will be inferred from this data.
    # The renderer's logical_size is 256x224.
    # A 16x14 map of 16x16 tiles would be 256x224.
    map_layout = [
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
        [1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1],
        [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
        [1, 0, 1, 0, 0, 1, 1, 1, 1, 0, 1, 0, 0, 1, 0, 1],
        [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
        [1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 0, 1],
        [1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
        [1, 0, 1, 0, 0, 1, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1],
        [1, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1],
        [1, 0, 1, 1, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 1],
        [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
        [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    ]
    map_height = len(map_layout)
    map_width = len(map_layout[0])

    tilemap = TileMap(width=map_width, height=map_height, tileset=tileset, priority=0)
    tilemap.map_data = map_layout # Directly assign the layout

    # --- Programmatically Create Player Sprite Surface ---
    player_surface = pygame.Surface((PLAYER_SIZE, PLAYER_SIZE))
    player_surface.fill(RED) # Player is a red square
    
    # Initial player position (place on a floor tile)
    # Ensure x, y are in logical pixels
    player_start_x = TILE_SIZE * 1 + (TILE_SIZE - PLAYER_SIZE) // 2
    player_start_y = TILE_SIZE * 1 + (TILE_SIZE - PLAYER_SIZE) // 2
    player_sprite = Sprite(player_surface, x=player_start_x, y=player_start_y, priority=1)

    # --- Initialize Renderer ---
    # Logical size of the SNES screen is 256x224.
    # Our tilemap is 16 tiles wide * 16px/tile = 256px
    # Our tilemap is 14 tiles high * 16px/tile = 224px
    renderer = SNESRenderer(window_scale=3, logical_width=map_width * TILE_SIZE, logical_height=map_height * TILE_SIZE)
    renderer.add_layer(tilemap)
    renderer.add_layer(player_sprite)

    # --- Game Update Logic ---
    def update_game_state():
        keys = pygame.key.get_pressed()
        
        prev_x, prev_y = player_sprite.x, player_sprite.y
        
        if keys[pygame.K_LEFT]:
            player_sprite.x -= MOVE_SPEED
        if keys[pygame.K_RIGHT]:
            player_sprite.x += MOVE_SPEED
        if keys[pygame.K_UP]:
            player_sprite.y -= MOVE_SPEED
        if keys[pygame.K_DOWN]:
            player_sprite.y += MOVE_SPEED

        # --- Collision Detection with Tilemap ---
        player_rect = player_sprite.get_rect()
        
        # Determine tile coordinates the player is trying to move into
        # Check all four corners of the player's bounding box
        corners_to_check = [
            (player_rect.left, player_rect.top),        # Top-left
            (player_rect.right -1, player_rect.top),    # Top-right
            (player_rect.left, player_rect.bottom -1),  # Bottom-left
            (player_rect.right-1, player_rect.bottom-1) # Bottom-right
        ]

        collided = False
        for px, py in corners_to_check:
            tile_x = px // TILE_SIZE
            tile_y = py // TILE_SIZE

            # Check if within map boundaries before accessing tilemap
            if 0 <= tile_x < tilemap.width and 0 <= tile_y < tilemap.height:
                tile_type = tilemap.get_tile_index(tile_x, tile_y)
                if tile_type == TILE_WALL:
                    collided = True
                    break
            else: # Player is trying to move outside the map (can be treated as collision)
                collided = True
                break
        
        if collided:
            player_sprite.x = prev_x # Revert horizontal movement
            player_sprite.y = prev_y # Revert vertical movement
            
            # More refined collision response: Try to revert only the axis of collision
            # For simplicity, this example reverts both if any corner collides after a move.
            # A more complex approach would test X and Y movement separately.
            # Test X-axis collision
            player_rect_x_moved = pygame.Rect(player_sprite.x, prev_y, player_sprite.width, player_sprite.height)
            collided_x = False
            corners_x = [ (player_rect_x_moved.left, player_rect_x_moved.top), (player_rect_x_moved.right -1, player_rect_x_moved.top),
                          (player_rect_x_moved.left, player_rect_x_moved.bottom -1), (player_rect_x_moved.right-1, player_rect_x_moved.bottom-1)]
            for px_c, py_c in corners_x:
                tx, ty = px_c // TILE_SIZE, py_c // TILE_SIZE
                if not (0 <= tx < tilemap.width and 0 <= ty < tilemap.height) or tilemap.get_tile_index(tx, ty) == TILE_WALL:
                    collided_x = True; break
            if collided_x: player_sprite.x = prev_x

            # Test Y-axis collision
            player_rect_y_moved = pygame.Rect(prev_x, player_sprite.y, player_sprite.width, player_sprite.height) # use current x or prev_x based on above
            collided_y = False
            corners_y = [ (player_rect_y_moved.left, player_rect_y_moved.top), (player_rect_y_moved.right -1, player_rect_y_moved.top),
                          (player_rect_y_moved.left, player_rect_y_moved.bottom -1), (player_rect_y_moved.right-1, player_rect_y_moved.bottom-1)]
            for px_c, py_c in corners_y:
                tx, ty = px_c // TILE_SIZE, py_c // TILE_SIZE
                if not (0 <= tx < tilemap.width and 0 <= ty < tilemap.height) or tilemap.get_tile_index(tx, ty) == TILE_WALL:
                    collided_y = True; break
            if collided_y: player_sprite.y = prev_y


        # --- Screen Boundary Clamping ---
        # Ensure player stays within the logical screen dimensions
        logical_width, logical_height = renderer.logical_size
        player_sprite.x = max(0, min(player_sprite.x, logical_width - player_sprite.width))
        player_sprite.y = max(0, min(player_sprite.y, logical_height - player_sprite.height))

    # --- Run the Game ---
    renderer.run(update_cb=update_game_state, fps=60) proceed
