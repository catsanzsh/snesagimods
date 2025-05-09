import pygame
import sys
import math
import random

# Pure Vibes Super Mario RPG in Pygame
pygame.init()
screen = pygame.display.set_mode((640, 480))
clock = pygame.time.Clock()

# Colors
WHITE = (255, 255, 255)
MARIO_COLOR = (255, 0, 0)
ENEMY_COLOR = (0, 255, 0)
BG_COLOR = (30, 30, 60)

# Entities
mario = {'x': 320, 'y': 240, 'hp': 100, 'size': 20}
enemies = [{'x': random.randint(0, 620), 'y': random.randint(0, 460), 'size': 20, 'hp': 50} for _ in range(5)]

# Game Loop
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    keys = pygame.key.get_pressed()
    if keys[pygame.K_LEFT]: mario['x'] -= 5
    if keys[pygame.K_RIGHT]: mario['x'] += 5
    if keys[pygame.K_UP]: mario['y'] -= 5
    if keys[pygame.K_DOWN]: mario['y'] += 5

    screen.fill(BG_COLOR)

    # Draw Mario
    pygame.draw.circle(screen, MARIO_COLOR, (mario['x'], mario['y']), mario['size'])

    # Draw Enemies
    for enemy in enemies:
        pygame.draw.rect(screen, ENEMY_COLOR, (enemy['x'], enemy['y'], enemy['size'], enemy['size']))
        if math.hypot(mario['x'] - enemy['x'], mario['y'] - enemy['y']) < mario['size'] + enemy['size']:
            enemy['hp'] -= 1
            if enemy['hp'] <= 0:
                enemies.remove(enemy)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()
