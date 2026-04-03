# ============================================================
#  FREE-FOR-ALL FPS GAME  (top-down 2D shooter)
#  Requirements: Python 3.8+  |  pip install pygame
#  Run: python fps_game.py
# ============================================================

import pygame
import math
import random
import sys

# ── SETTINGS ────────────────────────────────────────────────
SCREEN_W, SCREEN_H = 900, 650   # window size in pixels
FPS            = 60              # frames per second
PLAYER_SPEED   = 3               # how fast the human player moves
BOT_SPEED      = 1.5             # how fast enemy bots move
BULLET_SPEED   = 7               # bullet travel speed
PLAYER_HEALTH  = 100             # starting health for everyone
BULLET_DAMAGE  = 25              # hp lost per bullet hit
BOT_SHOOT_RATE = 90              # bot fires every N frames (lower = faster)
NUM_BOTS       = 4               # number of enemy bots
RESPAWN_TIME   = 120             # frames to wait before respawning (2 sec)

# ── COLOURS ─────────────────────────────────────────────────
BLACK      = (  0,   0,   0)
WHITE      = (255, 255, 255)
RED        = (220,  50,  50)
GREEN      = ( 50, 200,  80)
BLUE       = ( 60, 120, 220)
YELLOW     = (240, 200,  40)
ORANGE     = (230, 130,  30)
DARK_GRAY  = ( 30,  30,  35)
MID_GRAY   = ( 60,  60,  70)
LIGHT_GRAY = (160, 160, 170)
CYAN       = ( 80, 220, 220)
PURPLE     = (160,  80, 220)
PINK       = (230,  80, 160)

# Unique colour for each bot so they're easy to tell apart
BOT_COLORS = [ORANGE, CYAN, PURPLE, PINK,
              (180, 220, 60), (220, 160, 60)]


# ════════════════════════════════════════════════════════════
#  BULLET CLASS
# ════════════════════════════════════════════════════════════
class Bullet:
    """A small circle that travels in a straight line."""

    RADIUS = 5

    def __init__(self, x, y, target_x, target_y, owner):
        self.x = float(x)
        self.y = float(y)
        self.owner = owner          # which player/bot fired this

        # work out direction toward the target point
        dx = target_x - x
        dy = target_y - y
        dist = math.hypot(dx, dy) or 1  # avoid divide-by-zero
        self.vx = dx / dist * BULLET_SPEED
        self.vy = dy / dist * BULLET_SPEED

        self.alive = True           # set to False to remove it

    def update(self):
        """Move the bullet one step."""
        self.x += self.vx
        self.y += self.vy

        # remove if it flies off-screen
        if not (0 <= self.x <= SCREEN_W and 0 <= self.y <= SCREEN_H):
            self.alive = False

    def draw(self, screen):
        if self.alive:
            pygame.draw.circle(screen, YELLOW,
                               (int(self.x), int(self.y)), self.RADIUS)


# ════════════════════════════════════════════════════════════
#  PLAYER CLASS  (used for both human player AND bots)
# ════════════════════════════════════════════════════════════
class Player:
    """Represents one fighter in the arena."""

    RADIUS       = 18   # circle size on screen
    GUN_LENGTH   = 22   # length of the gun barrel drawn on the sprite

    def __init__(self, name, color, x, y, is_bot=False):
        self.name    = name
        self.color   = color
        self.x       = float(x)
        self.y       = float(y)
        self.is_bot  = is_bot

        # stats
        self.health  = PLAYER_HEALTH
        self.kills   = 0
        self.deaths  = 0

        # facing direction in radians (0 = right)
        self.angle   = 0.0

        # cooldown counter so we can't shoot every frame
        self.shoot_cooldown  = 0
        self.shoot_delay     = 20   # frames between shots (human)
        self.bot_shoot_timer = random.randint(0, BOT_SHOOT_RATE)

        # respawn timer (when > 0 the player is "dead" and invisible)
        self.respawn_timer   = 0
        self.alive           = True

    # ── PROPERTIES ──────────────────────────────────────────

    @property
    def kd_ratio(self):
        """Kill/death ratio, safely avoiding division by zero."""
        return self.kills / max(self.deaths, 1)

    # ── MOVEMENT ────────────────────────────────────────────

    def move(self, dx, dy):
        """Move by (dx, dy), clamped to screen edges."""
        self.x = max(self.RADIUS,
                     min(SCREEN_W - self.RADIUS, self.x + dx))
        self.y = max(self.RADIUS,
                     min(SCREEN_H - self.RADIUS, self.y + dy))

    # ── TAKING DAMAGE ───────────────────────────────────────

    def take_damage(self, amount):
        """Reduce health; return True if this hit was fatal."""
        if not self.alive:
            return False
        self.health -= amount
        if self.health <= 0:
            self.health = 0
            self.alive  = False
            self.deaths += 1
            self.respawn_timer = RESPAWN_TIME
            return True         # died
        return False            # survived

    # ── RESPAWNING ──────────────────────────────────────────

    def respawn(self):
        """Put the player back in a random safe spot."""
        margin = 60
        self.x      = float(random.randint(margin, SCREEN_W - margin))
        self.y      = float(random.randint(margin, SCREEN_H - margin))
        self.health = PLAYER_HEALTH
        self.alive  = True

    # ── UPDATE (called every frame) ─────────────────────────

    def update(self, bullets, all_players):
        """Tick down timers; bot AI logic lives here."""
        # count down shoot cooldown
        if self.shoot_cooldown > 0:
            self.shoot_cooldown -= 1

        # count down respawn timer
        if not self.alive:
            self.respawn_timer -= 1
            if self.respawn_timer <= 0:
                self.respawn()
            return []   # dead players produce no bullets

        new_bullets = []

        if self.is_bot:
            new_bullets = self._bot_ai(all_players)

        return new_bullets

    def _bot_ai(self, all_players):
        """Simple bot: chase nearest living enemy and shoot at them."""
        # find nearest human or other bot that isn't us and is alive
        target = None
        best_dist = float('inf')
        for p in all_players:
            if p is self or not p.alive:
                continue
            d = math.hypot(p.x - self.x, p.y - self.y)
            if d < best_dist:
                best_dist = d
                target = p

        if target is None:
            return []

        # face the target
        dx = target.x - self.x
        dy = target.y - self.y
        self.angle = math.atan2(dy, dx)

        # walk toward target (stop when very close)
        if best_dist > 80:
            self.move(math.cos(self.angle) * BOT_SPEED,
                      math.sin(self.angle) * BOT_SPEED)

        # shoot periodically
        self.bot_shoot_timer -= 1
        if self.bot_shoot_timer <= 0:
            self.bot_shoot_timer = BOT_SHOOT_RATE + random.randint(-20, 20)
            return [self._fire_bullet(target.x, target.y)]

        return []

    def _fire_bullet(self, tx, ty):
        """Create a bullet from the gun tip toward (tx, ty)."""
        # muzzle position: tip of the gun barrel
        tip_x = self.x + math.cos(self.angle) * self.GUN_LENGTH
        tip_y = self.y + math.sin(self.angle) * self.GUN_LENGTH
        return Bullet(tip_x, tip_y, tx, ty, owner=self)

    # ── DRAWING ─────────────────────────────────────────────

    def draw(self, screen, font_small):
        if not self.alive:
            return

        cx, cy = int(self.x), int(self.y)

        # body circle
        pygame.draw.circle(screen, self.color, (cx, cy), self.RADIUS)
        # white outline
        pygame.draw.circle(screen, WHITE, (cx, cy), self.RADIUS, 2)

        # gun barrel line
        gun_tip_x = cx + int(math.cos(self.angle) * self.GUN_LENGTH)
        gun_tip_y = cy + int(math.sin(self.angle) * self.GUN_LENGTH)
        pygame.draw.line(screen, WHITE, (cx, cy),
                         (gun_tip_x, gun_tip_y), 4)

        # health bar  (above the player)
        bar_w  = 36
        bar_h  = 5
        bar_x  = cx - bar_w // 2
        bar_y  = cy - self.RADIUS - 10
        # background (empty)
        pygame.draw.rect(screen, MID_GRAY,
                         (bar_x, bar_y, bar_w, bar_h))
        # filled portion
        filled = int(bar_w * self.health / PLAYER_HEALTH)
        bar_color = GREEN if self.health > 50 else (
                    YELLOW if self.health > 25 else RED)
        pygame.draw.rect(screen, bar_color,
                         (bar_x, bar_y, filled, bar_h))

        # name label
        label = font_small.render(self.name, True, WHITE)
        screen.blit(label, (cx - label.get_width() // 2,
                             cy - self.RADIUS - 22))


# ════════════════════════════════════════════════════════════
#  HUD  –  draws kills / deaths / health for the human player
# ════════════════════════════════════════════════════════════
def draw_hud(screen, player, font, font_small):
    # semi-transparent panel top-left
    panel = pygame.Surface((210, 90), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 160))
    screen.blit(panel, (10, 10))

    # player name
    name_surf = font.render(player.name, True, player.color)
    screen.blit(name_surf, (18, 15))

    # health
    hp_text = font_small.render(f"HP:     {player.health}", True, GREEN)
    screen.blit(hp_text, (18, 42))

    # kills / deaths
    kd_text = font_small.render(
        f"Kills: {player.kills}   Deaths: {player.deaths}", True, LIGHT_GRAY)
    screen.blit(kd_text, (18, 62))

    # health bar across top
    bar_w = 200
    bar_h = 8
    pygame.draw.rect(screen, MID_GRAY, (10, 102, bar_w, bar_h))
    filled = int(bar_w * player.health / PLAYER_HEALTH)
    bar_color = GREEN if player.health > 50 else (
                YELLOW if player.health > 25 else RED)
    pygame.draw.rect(screen, bar_color, (10, 102, filled, bar_h))


# ════════════════════════════════════════════════════════════
#  LEADERBOARD  –  sorted panel on the right side
# ════════════════════════════════════════════════════════════
def draw_leaderboard(screen, all_players, font, font_small):
    # sort by kills descending, deaths ascending on tie
    sorted_players = sorted(all_players,
                            key=lambda p: (-p.kills, p.deaths))

    panel_w = 230
    row_h   = 28
    padding = 10
    panel_h = padding * 2 + 24 + row_h * len(sorted_players)
    panel_x = SCREEN_W - panel_w - 10
    panel_y = 10

    # panel background
    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel.fill((0, 0, 0, 170))
    screen.blit(panel, (panel_x, panel_y))

    # title
    title = font.render("LEADERBOARD", True, YELLOW)
    screen.blit(title, (panel_x + padding, panel_y + padding))

    # column headers
    header = font_small.render("Name          K    D    K/D", True, LIGHT_GRAY)
    screen.blit(header, (panel_x + padding,
                         panel_y + padding + 22))

    # one row per player
    for i, p in enumerate(sorted_players):
        row_y = panel_y + padding + 22 + 18 + i * row_h + 4

        # highlight the human player's row
        if not p.is_bot:
            highlight = pygame.Surface((panel_w - 4, row_h - 2), pygame.SRCALPHA)
            highlight.fill((255, 255, 100, 30))
            screen.blit(highlight, (panel_x + 2, row_y))

        # rank number
        rank_surf = font_small.render(f"#{i+1}", True, LIGHT_GRAY)
        screen.blit(rank_surf, (panel_x + padding, row_y + 4))

        # name (truncate if long)
        name_str = p.name[:9]
        name_surf = font_small.render(name_str, True, p.color)
        screen.blit(name_surf, (panel_x + padding + 28, row_y + 4))

        # stats
        stats_str = f"{p.kills:>3}  {p.deaths:>3}  {p.kd_ratio:>4.1f}"
        stats_surf = font_small.render(stats_str, True, WHITE)
        screen.blit(stats_surf, (panel_x + panel_w - 108, row_y + 4))

        # dead indicator
        if not p.alive:
            dead_surf = font_small.render("DEAD", True, RED)
            screen.blit(dead_surf, (panel_x + panel_w - 48, row_y + 4))


# ════════════════════════════════════════════════════════════
#  KILL FEED  –  scrolling log of recent kills (top center)
# ════════════════════════════════════════════════════════════
class KillFeed:
    """Stores recent kill messages and fades them out."""

    MAX_ENTRIES = 5
    DURATION    = 240   # frames each message stays

    def __init__(self):
        self.entries = []   # list of [message_str, color, timer]

    def add(self, killer_name, victim_name, killer_color):
        msg = f"{killer_name}  ✕  {victim_name}"
        self.entries.append([msg, killer_color, self.DURATION])
        # keep only the most recent MAX_ENTRIES
        if len(self.entries) > self.MAX_ENTRIES:
            self.entries.pop(0)

    def update(self):
        for entry in self.entries:
            entry[2] -= 1
        self.entries = [e for e in self.entries if e[2] > 0]

    def draw(self, screen, font_small):
        x = SCREEN_W // 2
        y = 14
        for msg, color, timer in reversed(self.entries):
            # fade out in the last 60 frames
            alpha = min(255, timer * 4)
            surf = font_small.render(msg, True, color)
            surf.set_alpha(alpha)
            screen.blit(surf, (x - surf.get_width() // 2, y))
            y += 20


# ════════════════════════════════════════════════════════════
#  GRID BACKGROUND  –  simple arena floor tiles
# ════════════════════════════════════════════════════════════
def draw_background(screen):
    screen.fill(DARK_GRAY)
    # subtle grid lines
    grid_size = 60
    for gx in range(0, SCREEN_W, grid_size):
        pygame.draw.line(screen, MID_GRAY, (gx, 0), (gx, SCREEN_H), 1)
    for gy in range(0, SCREEN_H, grid_size):
        pygame.draw.line(screen, MID_GRAY, (0, gy), (SCREEN_W, gy), 1)

    # arena border
    pygame.draw.rect(screen, LIGHT_GRAY, (0, 0, SCREEN_W, SCREEN_H), 3)


# ════════════════════════════════════════════════════════════
#  RESPAWN OVERLAY  –  shown while human player is dead
# ════════════════════════════════════════════════════════════
def draw_respawn_overlay(screen, player, font, font_big):
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 140))
    screen.blit(overlay, (0, 0))

    msg1 = font_big.render("YOU DIED", True, RED)
    msg2 = font.render(
        f"Respawning in {math.ceil(player.respawn_timer / FPS)}s ...",
        True, WHITE)

    screen.blit(msg1, (SCREEN_W // 2 - msg1.get_width() // 2,
                        SCREEN_H // 2 - 60))
    screen.blit(msg2, (SCREEN_W // 2 - msg2.get_width() // 2,
                        SCREEN_H // 2 + 10))


# ════════════════════════════════════════════════════════════
#  MAIN  –  puts everything together
# ════════════════════════════════════════════════════════════
def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Free-For-All FPS  |  WASD to move  |  Click to shoot")
    clock = pygame.time.Clock()

    # ── fonts ────────────────────────────────────────────────
    font_big   = pygame.font.SysFont("consolas", 48, bold=True)
    font       = pygame.font.SysFont("consolas", 20, bold=True)
    font_small = pygame.font.SysFont("consolas", 15)

    # ── create human player ──────────────────────────────────
    human = Player(
        name   = "YOU",
        color  = GREEN,
        x      = SCREEN_W // 2,
        y      = SCREEN_H // 2,
        is_bot = False,
    )

    # ── create bots ─────────────────────────────────────────
    bot_names = ["Alpha", "Bravo", "Delta", "Echo", "Foxtrot", "Ghost"]
    bots = []
    for i in range(NUM_BOTS):
        margin = 80
        bots.append(Player(
            name   = bot_names[i % len(bot_names)],
            color  = BOT_COLORS[i % len(BOT_COLORS)],
            x      = random.randint(margin, SCREEN_W - margin),
            y      = random.randint(margin, SCREEN_H - margin),
            is_bot = True,
        ))

    all_players = [human] + bots
    bullets     = []
    kill_feed   = KillFeed()

    # ── game loop ────────────────────────────────────────────
    running = True
    while running:

        # ── 1. HANDLE EVENTS ────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # human player shoots on left mouse button
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1 and human.alive:
                    if human.shoot_cooldown <= 0:
                        mx, my = pygame.mouse.get_pos()
                        # update facing angle
                        human.angle = math.atan2(my - human.y,
                                                 mx - human.x)
                        bullets.append(human._fire_bullet(mx, my))
                        human.shoot_cooldown = human.shoot_delay

        # ── 2. HUMAN MOVEMENT ───────────────────────────────
        if human.alive:
            keys = pygame.key.get_pressed()
            dx = dy = 0
            if keys[pygame.K_w] or keys[pygame.K_UP]:    dy -= PLAYER_SPEED
            if keys[pygame.K_s] or keys[pygame.K_DOWN]:  dy += PLAYER_SPEED
            if keys[pygame.K_a] or keys[pygame.K_LEFT]:  dx -= PLAYER_SPEED
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx += PLAYER_SPEED
            human.move(dx, dy)

            # human always faces mouse cursor
            mx, my = pygame.mouse.get_pos()
            human.angle = math.atan2(my - human.y, mx - human.x)
            human.shoot_cooldown = max(0, human.shoot_cooldown - 1)

        # ── 3. UPDATE BOTS + COLLECT THEIR BULLETS ──────────
        for bot in bots:
            new_b = bot.update(bullets, all_players)
            bullets.extend(new_b)

        human.update(bullets, all_players)   # handles respawn timer

        # ── 4. UPDATE BULLETS ───────────────────────────────
        for bullet in bullets:
            bullet.update()

        # ── 5. COLLISION DETECTION ──────────────────────────
        for bullet in bullets:
            if not bullet.alive:
                continue
            for player in all_players:
                if player is bullet.owner:
                    continue   # can't shoot yourself
                if not player.alive:
                    continue
                # simple circle collision
                dist = math.hypot(player.x - bullet.x,
                                  player.y - bullet.y)
                if dist < player.RADIUS + bullet.RADIUS:
                    bullet.alive = False
                    killed = player.take_damage(BULLET_DAMAGE)
                    if killed:
                        bullet.owner.kills += 1
                        kill_feed.add(bullet.owner.name,
                                      player.name,
                                      bullet.owner.color)

        # remove dead bullets
        bullets = [b for b in bullets if b.alive]

        # kill-feed timer
        kill_feed.update()

        # ── 6. DRAW EVERYTHING ──────────────────────────────
        draw_background(screen)

        # bullets
        for bullet in bullets:
            bullet.draw(screen)

        # players
        for player in all_players:
            player.draw(screen, font_small)

        # HUD (top-left) + leaderboard (top-right) + kill feed (top-center)
        draw_hud(screen, human, font, font_small)
        draw_leaderboard(screen, all_players, font, font_small)
        kill_feed.draw(screen, font_small)

        # respawn overlay when human is dead
        if not human.alive:
            draw_respawn_overlay(screen, human, font, font_big)

        # ── 7. FLIP THE DISPLAY ─────────────────────────────
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


# ── entry point ─────────────────────────────────────────────
if __name__ == "__main__":
    main()