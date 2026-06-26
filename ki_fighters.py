"""
KI FIGHTERS
-----------
An original anime-style 1v1 fighting game. Build up your Ki (energy)
meter, fire energy blasts, and unleash a POWER-UP TRANSFORMATION when
your meter is full for a temporary speed & damage boost. Best of 3
rounds against the CPU.

HOW TO RUN THIS GAME:
1. Make sure Python is installed (python.org)
2. Install pygame:
       pip install pygame
3. Save this file as ki_fighters.py
4. Run it with:
       python ki_fighters.py

CONTROLS:
- A / D       : move left / right
- W           : jump
- S           : block (reduces damage taken)
- J           : punch (fast, low damage)
- K           : kick (slower, more damage)
- L           : fire energy blast (costs Ki, ranged attack)
- HOLD SPACE  : charge Ki faster (can't move while charging)
- T           : TRANSFORM when Ki is full (temporary power boost)
- R           : restart after match ends
- ESC         : quit
"""

import pygame
import random
import math

pygame.init()

# ---------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------
WIDTH, HEIGHT = 900, 500
GROUND_Y = HEIGHT - 90
FPS = 60

GRAVITY = 1.0
JUMP_STRENGTH = -16
MOVE_SPEED = 5
TRANSFORMED_SPEED_MULT = 1.6
TRANSFORMED_DAMAGE_MULT = 1.7
TRANSFORM_DURATION = FPS * 8   # 8 seconds of power-up

MAX_HEALTH = 100
MAX_KI = 100
KI_REGEN = 0.15
KI_CHARGE_RATE = 0.9
BLAST_KI_COST = 25
TRANSFORM_KI_COST = MAX_KI  # uses the whole bar

PUNCH_DAMAGE = 5
KICK_DAMAGE = 9
BLAST_DAMAGE = 14
ATTACK_RANGE = 90
PUNCH_COOLDOWN = 16
KICK_COOLDOWN = 26
BLAST_COOLDOWN = 35

ROUNDS_TO_WIN = 2

BG_TOP = (25, 18, 45)
BG_BOTTOM = (60, 30, 70)
GROUND_COLOR = (40, 35, 55)
P1_COLOR = (90, 190, 255)
P1_AURA = (160, 230, 255)
P2_COLOR = (255, 110, 100)
P2_AURA = (255, 180, 140)
BLAST_COLOR = (255, 230, 120)
WHITE = (240, 240, 245)
HEALTH_COLOR = (90, 220, 130)
HEALTH_BG = (60, 25, 30)
KI_COLOR = (120, 190, 255)
KI_BG = (30, 40, 60)
GOLD = (255, 210, 80)

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Ki Fighters")
clock = pygame.time.Clock()
font = pygame.font.SysFont("consolas", 22)
big_font = pygame.font.SysFont("consolas", 50)
name_font = pygame.font.SysFont("consolas", 20, bold=True)


# ---------------------------------------------------------
# PARTICLES (used for blast trails and transformation aura)
# ---------------------------------------------------------
class Particle:
    def __init__(self, x, y, color, vel=None, life=24, radius=4):
        self.x, self.y = x, y
        self.color = color
        self.vx, self.vy = vel if vel else (random.uniform(-1, 1), random.uniform(-2, -0.5))
        self.life = life
        self.max_life = life
        self.radius = radius

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1

    def draw(self, surface):
        if self.life <= 0:
            return
        fade = self.life / self.max_life
        r = max(1, int(self.radius * fade))
        alpha_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        color_with_alpha = (*self.color, int(255 * fade))
        pygame.draw.circle(alpha_surf, color_with_alpha, (r, r), r)
        surface.blit(alpha_surf, (self.x - r, self.y - r))


# ---------------------------------------------------------
# ENERGY BLAST PROJECTILE
# ---------------------------------------------------------
class Blast:
    def __init__(self, x, y, direction, damage):
        self.x = x
        self.y = y
        self.direction = direction   # 1 = moving right, -1 = moving left
        self.speed = 11
        self.damage = damage
        self.radius = 12
        self.alive = True

    def update(self, particles):
        self.x += self.speed * self.direction
        particles.append(Particle(self.x, self.y, BLAST_COLOR, vel=(0, 0), life=14, radius=8))
        if self.x < -50 or self.x > WIDTH + 50:
            self.alive = False

    def get_rect(self):
        return pygame.Rect(self.x - self.radius, self.y - self.radius, self.radius * 2, self.radius * 2)

    def draw(self, surface):
        pygame.draw.circle(surface, BLAST_COLOR, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(surface, WHITE, (int(self.x), int(self.y)), self.radius // 2)


# ---------------------------------------------------------
# FIGHTER
# ---------------------------------------------------------
class Fighter:
    def __init__(self, x, color, aura_color, facing, name):
        self.x = x
        self.y = GROUND_Y
        self.vel_y = 0
        self.on_ground = True
        self.facing = facing          # 1 = facing right, -1 = facing left
        self.color = color
        self.aura_color = aura_color
        self.name = name

        self.width, self.height = 46, 110

        self.health = MAX_HEALTH
        self.ki = 30

        self.is_blocking = False
        self.is_charging = False
        self.is_transformed = False
        self.transform_timer = 0

        self.punch_cd = 0
        self.kick_cd = 0
        self.blast_cd = 0
        self.hit_flash = 0          # brief red flash when hit
        self.action_label = ""      # text like "PUNCH!" shown briefly above fighter
        self.action_label_timer = 0

    def get_rect(self):
        return pygame.Rect(int(self.x - self.width / 2), int(self.y - self.height), self.width, self.height)

    def speed(self):
        return MOVE_SPEED * (TRANSFORMED_SPEED_MULT if self.is_transformed else 1)

    def damage_mult(self):
        return TRANSFORMED_DAMAGE_MULT if self.is_transformed else 1

    def take_damage(self, amount):
        if self.is_blocking:
            amount *= 0.35
        self.health = max(0, self.health - amount)
        self.hit_flash = 8

    def show_label(self, text):
        self.action_label = text
        self.action_label_timer = 30

    def update_physics(self):
        self.vel_y += GRAVITY
        self.y += self.vel_y
        if self.y >= GROUND_Y:
            self.y = GROUND_Y
            self.vel_y = 0
            self.on_ground = True
        else:
            self.on_ground = False

        self.x = max(self.width, min(WIDTH - self.width, self.x))

        for cd_name in ("punch_cd", "kick_cd", "blast_cd"):
            val = getattr(self, cd_name)
            if val > 0:
                setattr(self, cd_name, val - 1)

        if self.hit_flash > 0:
            self.hit_flash -= 1
        if self.action_label_timer > 0:
            self.action_label_timer -= 1

        if self.is_transformed:
            self.transform_timer -= 1
            if self.transform_timer <= 0:
                self.is_transformed = False

        # Ki regenerates slowly on its own, faster while charging
        if self.is_charging:
            self.ki = min(MAX_KI, self.ki + KI_CHARGE_RATE)
        else:
            self.ki = min(MAX_KI, self.ki + KI_REGEN)

    def try_transform(self):
        if self.ki >= TRANSFORM_KI_COST and not self.is_transformed:
            self.is_transformed = True
            self.transform_timer = TRANSFORM_DURATION
            self.ki = 0
            self.show_label("POWER UP!!")
            return True
        return False

    def draw(self, surface, particles):
        rect = self.get_rect()

        # Aura glow while transformed
        if self.is_transformed:
            glow_radius = 60 + int(8 * math.sin(pygame.time.get_ticks() * 0.02))
            glow_surf = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (*self.aura_color, 70), (glow_radius, glow_radius), glow_radius)
            surface.blit(glow_surf, (rect.centerx - glow_radius, rect.centery - glow_radius))
            if random.random() < 0.5:
                particles.append(Particle(
                    rect.centerx + random.randint(-20, 20), rect.bottom,
                    self.aura_color, vel=(random.uniform(-0.5, 0.5), random.uniform(-2, -1)),
                    life=20, radius=5
                ))

        body_color = WHITE if self.hit_flash % 4 >= 2 else self.color

        # Simple humanoid shape: head + torso + limbs, all rectangles/circles
        head_radius = 14
        torso_top = rect.top + head_radius * 2
        pygame.draw.circle(surface, body_color, (rect.centerx, rect.top + head_radius), head_radius)
        pygame.draw.rect(surface, body_color, (rect.left + 8, torso_top, rect.width - 16, rect.height - head_radius * 2 - 18))

        # Legs (slightly spread for a "stance" look)
        leg_w = 10
        pygame.draw.rect(surface, body_color, (rect.centerx - 14, rect.bottom - 22, leg_w, 22))
        pygame.draw.rect(surface, body_color, (rect.centerx + 4, rect.bottom - 22, leg_w, 22))

        # Arm pointing forward when blocking, otherwise neutral
        arm_y = torso_top + 12
        arm_dir = self.facing
        if self.is_blocking:
            pygame.draw.rect(surface, body_color, (rect.centerx, arm_y, 22 * arm_dir, 9))
        else:
            pygame.draw.rect(surface, body_color, (rect.centerx - 6, arm_y, 12, 26))

        # Name + action label above the fighter
        name_text = name_font.render(self.name, True, WHITE)
        surface.blit(name_text, (rect.centerx - name_text.get_width() // 2, rect.top - 28))

        if self.action_label_timer > 0:
            label_color = GOLD if "POWER" in self.action_label else WHITE
            label_text = font.render(self.action_label, True, label_color)
            surface.blit(label_text, (rect.centerx - label_text.get_width() // 2, rect.top - 50))


# ---------------------------------------------------------
# DRAWING HELPERS
# ---------------------------------------------------------
def draw_background():
    for y in range(HEIGHT):
        t = y / HEIGHT
        color = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3))
        pygame.draw.line(screen, color, (0, y), (WIDTH, y))
    pygame.draw.rect(screen, GROUND_COLOR, (0, GROUND_Y, WIDTH, HEIGHT - GROUND_Y))
    pygame.draw.line(screen, (90, 80, 100), (0, GROUND_Y), (WIDTH, GROUND_Y), 3)


def draw_bar(x, y, width, height, ratio, fg_color, bg_color, label):
    pygame.draw.rect(screen, bg_color, (x, y, width, height), border_radius=4)
    pygame.draw.rect(screen, fg_color, (x, y, int(width * max(ratio, 0)), height), border_radius=4)
    pygame.draw.rect(screen, WHITE, (x, y, width, height), 2, border_radius=4)
    text = font.render(label, True, WHITE)
    screen.blit(text, (x, y - 22))


def draw_hud(p1, p2, round_num, p1_wins, p2_wins):
    draw_bar(30, 30, 320, 18, p1.health / MAX_HEALTH, HEALTH_COLOR, HEALTH_BG, f"{p1.name}")
    draw_bar(30, 60, 320, 10, p1.ki / MAX_KI, KI_COLOR, KI_BG, "")

    draw_bar(WIDTH - 350, 30, 320, 18, p2.health / MAX_HEALTH, HEALTH_COLOR, HEALTH_BG, f"{p2.name}")
    draw_bar(WIDTH - 350, 60, 320, 10, p2.ki / MAX_KI, KI_COLOR, KI_BG, "")

    round_text = font.render(f"Round {round_num}  |  Wins: {p1_wins} - {p2_wins}", True, WHITE)
    screen.blit(round_text, (WIDTH // 2 - round_text.get_width() // 2, 14))

    if p1.ki >= MAX_KI:
        ready_text = font.render("T: TRANSFORM!", True, GOLD)
        screen.blit(ready_text, (30, 78))


def show_message(lines, color):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((10, 8, 16, 200))
    screen.blit(overlay, (0, 0))
    for i, text in enumerate(lines):
        rendered = (big_font if i == 0 else font).render(text, True, color if i == 0 else WHITE)
        screen.blit(rendered, (WIDTH // 2 - rendered.get_width() // 2, HEIGHT // 2 - 60 + i * 50))


# ---------------------------------------------------------
# SIMPLE CPU "AI"
# ---------------------------------------------------------
def cpu_decide(cpu, opponent, blasts, particles):
    distance = opponent.x - cpu.x
    cpu.facing = 1 if distance > 0 else -1

    in_melee_range = abs(distance) < ATTACK_RANGE
    in_blast_range = abs(distance) >= ATTACK_RANGE

    # Defensive transform when health is low and Ki is ready
    if cpu.health < 40 and cpu.ki >= TRANSFORM_KI_COST and random.random() < 0.04:
        cpu.try_transform()
        return

    if in_melee_range:
        if cpu.punch_cd == 0 and random.random() < 0.05:
            do_punch(cpu, opponent)
        elif cpu.kick_cd == 0 and random.random() < 0.03:
            do_kick(cpu, opponent)
        elif random.random() < 0.02:
            cpu.is_blocking = True
        else:
            cpu.is_blocking = False
    else:
        cpu.is_blocking = False
        # Move toward opponent, but keep a little distance to use blasts sometimes
        if abs(distance) > 250 or random.random() < 0.85:
            cpu.x += cpu.speed() * (1 if distance > 0 else -1)

        if cpu.blast_cd == 0 and cpu.ki >= BLAST_KI_COST and random.random() < 0.02:
            do_blast(cpu, blasts, particles)


# ---------------------------------------------------------
# ATTACK ACTIONS (shared by player & CPU)
# ---------------------------------------------------------
def do_punch(attacker, defender):
    attacker.punch_cd = PUNCH_COOLDOWN
    attacker.show_label("PUNCH!")
    if abs(attacker.x - defender.x) < ATTACK_RANGE:
        defender.take_damage(PUNCH_DAMAGE * attacker.damage_mult())


def do_kick(attacker, defender):
    attacker.kick_cd = KICK_COOLDOWN
    attacker.show_label("KICK!")
    if abs(attacker.x - defender.x) < ATTACK_RANGE:
        defender.take_damage(KICK_DAMAGE * attacker.damage_mult())


def do_blast(attacker, blasts, particles):
    attacker.blast_cd = BLAST_COOLDOWN
    attacker.ki -= BLAST_KI_COST
    attacker.show_label("ENERGY BLAST!")
    direction = attacker.facing
    blast_y = attacker.y - attacker.height // 2
    blast_x = attacker.x + 30 * direction
    damage = BLAST_DAMAGE * attacker.damage_mult()
    blasts.append(Blast(blast_x, blast_y, direction, damage))
    for _ in range(6):
        particles.append(Particle(blast_x, blast_y, BLAST_COLOR, life=16, radius=6))


# ---------------------------------------------------------
# MAIN GAME
# ---------------------------------------------------------
def main():
    p1 = Fighter(WIDTH * 0.25, P1_COLOR, P1_AURA, facing=1, name="RYU-KEN")
    p2 = Fighter(WIDTH * 0.75, P2_COLOR, P2_AURA, facing=-1, name="ZENTAR")

    blasts = []
    particles = []

    round_num = 1
    p1_wins, p2_wins = 0, 0
    state = "playing"      # "playing", "round_end", "match_end"
    pause_timer = 0
    round_winner = None

    def reset_round():
        p1.health = MAX_HEALTH
        p2.health = MAX_HEALTH
        p1.ki = 30
        p2.ki = 30
        p1.x, p2.x = WIDTH * 0.25, WIDTH * 0.75
        p1.is_transformed = p2.is_transformed = False
        blasts.clear()
        particles.clear()

    running = True
    while running:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if state == "match_end" and event.key == pygame.K_r:
                    return main()
                if state == "playing" and event.key == pygame.K_t:
                    p1.try_transform()
                if state == "playing" and event.key == pygame.K_j and p1.punch_cd == 0:
                    do_punch(p1, p2)
                if state == "playing" and event.key == pygame.K_k and p1.kick_cd == 0:
                    do_kick(p1, p2)
                if state == "playing" and event.key == pygame.K_l and p1.blast_cd == 0 and p1.ki >= BLAST_KI_COST:
                    do_blast(p1, blasts, particles)

        keys = pygame.key.get_pressed()

        if state == "playing":
            # ---- Player 1 controls ----
            p1.is_charging = keys[pygame.K_SPACE]
            p1.is_blocking = keys[pygame.K_s]

            if not p1.is_charging and not p1.is_blocking:
                if keys[pygame.K_a]:
                    p1.x -= p1.speed()
                    p1.facing = -1
                if keys[pygame.K_d]:
                    p1.x += p1.speed()
                    p1.facing = 1
                if keys[pygame.K_w] and p1.on_ground:
                    p1.vel_y = JUMP_STRENGTH

            # Always face the opponent for clarity (purely visual, doesn't affect movement keys)
            p1.facing = 1 if p2.x > p1.x else -1
            p2.facing = 1 if p1.x > p2.x else -1

            # ---- CPU behaviour ----
            cpu_decide(p2, p1, blasts, particles)

            # ---- Physics ----
            p1.update_physics()
            p2.update_physics()

            # ---- Blasts ----
            for blast in blasts[:]:
                blast.update(particles)
                target = p2 if blast.direction == 1 else p1
                # only check collision against whichever fighter the blast is heading toward
                shooter_is_p1 = blast.direction == p1.facing and blast.x < p2.x if blast.direction == 1 else True
                if blast.get_rect().colliderect(target.get_rect()):
                    target.take_damage(blast.damage)
                    blast.alive = False
                if not blast.alive:
                    blasts.remove(blast)

            # ---- Particles ----
            for particle in particles[:]:
                particle.update()
                if particle.life <= 0:
                    particles.remove(particle)

            # ---- Round end check ----
            if p1.health <= 0 or p2.health <= 0:
                round_winner = p1.name if p2.health <= 0 and p1.health > 0 else (
                    p2.name if p1.health <= 0 and p2.health > 0 else "DRAW"
                )
                if round_winner == p1.name:
                    p1_wins += 1
                elif round_winner == p2.name:
                    p2_wins += 1
                state = "round_end"
                pause_timer = 90

        elif state == "round_end":
            pause_timer -= 1
            for particle in particles[:]:
                particle.update()
                if particle.life <= 0:
                    particles.remove(particle)
            if pause_timer <= 0:
                if p1_wins >= ROUNDS_TO_WIN or p2_wins >= ROUNDS_TO_WIN:
                    state = "match_end"
                else:
                    round_num += 1
                    reset_round()
                    state = "playing"

        # ---- DRAW ----
        draw_background()

        for blast in blasts:
            blast.draw(screen)
        for particle in particles:
            particle.draw(screen)

        p1.draw(screen, particles)
        p2.draw(screen, particles)

        draw_hud(p1, p2, round_num, p1_wins, p2_wins)

        if state == "round_end":
            color = GOLD if round_winner != "DRAW" else WHITE
            show_message([f"{round_winner} WINS THE ROUND!" if round_winner != "DRAW" else "DRAW ROUND"], color)
        elif state == "match_end":
            champion = p1.name if p1_wins > p2_wins else p2.name
            show_message(["MATCH OVER", f"{champion} WINS THE MATCH!", "Press R to Restart or ESC to Quit"], GOLD)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
