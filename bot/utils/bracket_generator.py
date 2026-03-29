"""
Bracket (setka) generatsiya moduli.
Pillow kutubxonasi yordamida chiroyli turnir sxemasi yaratadi.
"""
import io
import random
import math
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
from bot.config import FONTS_DIR, ASSETS_DIR
import os


DARK_BG = (10, 15, 30)
GOLD = (212, 175, 55)
SILVER = (192, 192, 192)
WHITE = (255, 255, 255)
LIGHT_GRAY = (200, 200, 200)
GREEN = (39, 174, 96)
ACCENT = (41, 128, 185)
CARD_BG = (20, 30, 55)
CARD_BORDER = (50, 70, 120)
LINE_COLOR = (80, 100, 160)


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    font_names = [
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "Arial-Bold.ttf" if bold else "Arial.ttf",
        "LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf",
    ]
    system_dirs = [
        FONTS_DIR,
        "/usr/share/fonts/truetype/dejavu",
        "/usr/share/fonts/truetype/liberation",
        "/usr/share/fonts",
        "/usr/local/share/fonts",
    ]
    for font_name in font_names:
        for directory in system_dirs:
            path = os.path.join(directory, font_name)
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    pass
    return ImageFont.load_default()


def draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple,
    fill: tuple,
    outline: tuple = None,
    radius: int = 8,
    width: int = 2,
):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=outline, width=width)


def draw_gradient_bg(img: Image.Image):
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for y in range(h):
        factor = y / h
        r = int(DARK_BG[0] + (20 - DARK_BG[0]) * factor)
        g = int(DARK_BG[1] + (25 - DARK_BG[1]) * factor)
        b = int(DARK_BG[2] + (50 - DARK_BG[2]) * factor)
        draw.line([(0, y), (w, y)], fill=(r, g, b))


def draw_stars(draw: ImageDraw.ImageDraw, width: int, height: int, count: int = 80):
    random.seed(42)
    for _ in range(count):
        x = random.randint(0, width)
        y = random.randint(0, height // 2)
        size = random.choice([1, 1, 1, 2])
        alpha = random.randint(100, 220)
        draw.ellipse([x, y, x + size, y + size], fill=(255, 255, 255, alpha))


def generate_playoff_bracket(
    participants: list,
    tournament_name: str,
    matches: list = None,
) -> bytes:
    n = len(participants)
    rounds = math.ceil(math.log2(n)) if n > 1 else 1
    slots = 2 ** rounds

    padded = list(participants) + [None] * (slots - n)
    random.shuffle(padded)

    CARD_W = 200
    CARD_H = 44
    CARD_GAP = 16
    ROUND_GAP = 70
    PADDING_LEFT = 60
    PADDING_TOP = 140
    HEADER_H = 120

    def get_round_y_positions(round_idx: int) -> list:
        pair_count = slots // (2 ** round_idx)
        spacing = (CARD_H * 2 + CARD_GAP) * (2 ** round_idx)
        positions = []
        for i in range(pair_count):
            top_y = PADDING_TOP + i * spacing + (spacing - CARD_H * 2 - CARD_GAP) // 2
            positions.append(top_y)
        return positions

    total_width = PADDING_LEFT + rounds * (CARD_W + ROUND_GAP) + PADDING_LEFT
    total_height = PADDING_TOP + slots // 2 * (CARD_H * 2 + CARD_GAP) + 80

    img = Image.new("RGBA", (total_width, total_height), DARK_BG)
    draw_gradient_bg(img)
    draw_stars(ImageDraw.Draw(img), total_width, total_height)
    draw = ImageDraw.Draw(img, "RGBA")

    font_title = load_font(28, bold=True)
    font_sub = load_font(14)
    font_team = load_font(13, bold=True)
    font_score = load_font(14, bold=True)
    font_round = load_font(12)

    draw.text(
        (total_width // 2, 30),
        "⚽ eFOOTBALL TURNIRI",
        font=font_title,
        fill=GOLD,
        anchor="mt",
    )
    draw.text(
        (total_width // 2, 68),
        tournament_name.upper(),
        font=load_font(18, bold=True),
        fill=WHITE,
        anchor="mt",
    )

    line_y = 100
    draw.line([(40, line_y), (total_width - 40, line_y)], fill=GOLD, width=2)

    round_names = ["1/16", "1/8", "Chorak final", "Yarim final", "Final", "G'olib"]
    all_round_participants = [padded[:]]

    for r in range(rounds):
        x = PADDING_LEFT + r * (CARD_W + ROUND_GAP)
        round_label = round_names[r] if r < len(round_names) else f"R{r+1}"
        draw.text(
            (x + CARD_W // 2, PADDING_TOP - 25),
            round_label,
            font=font_round,
            fill=GOLD,
            anchor="mt",
        )

        current_round = all_round_participants[r]
        next_round = []
        positions = get_round_y_positions(r)

        for i, top_y in enumerate(positions):
            idx1 = i * 2
            idx2 = i * 2 + 1
            p1 = current_round[idx1] if idx1 < len(current_round) else None
            p2 = current_round[idx2] if idx2 < len(current_round) else None

            score1_txt = ""
            score2_txt = ""
            p1_won = False
            p2_won = False

            if matches and p1 and p2:
                for m in matches:
                    pids = {m.get("participant1_id"), m.get("participant2_id")}
                    ep1 = p1.get("id") if isinstance(p1, dict) else getattr(p1, "id", None)
                    ep2 = p2.get("id") if isinstance(p2, dict) else getattr(p2, "id", None)
                    if ep1 in pids and ep2 in pids and m.get("status") == "confirmed":
                        score1_txt = str(m.get("score1", ""))
                        score2_txt = str(m.get("score2", ""))
                        winner = m.get("winner_id")
                        p1_won = winner == ep1
                        p2_won = winner == ep2
                        break

            for pi, (p, sy, score_txt, won) in enumerate(
                [(p1, top_y, score1_txt, p1_won), (p2, top_y + CARD_H + CARD_GAP, score2_txt, p2_won)]
            ):
                card_x = x
                card_y = sy
                border_color = GREEN if won else CARD_BORDER
                fill_color = (25, 40, 70) if won else CARD_BG
                draw_rounded_rect(
                    draw,
                    (card_x, card_y, card_x + CARD_W, card_y + CARD_H),
                    fill=fill_color,
                    outline=border_color,
                    radius=6,
                    width=2,
                )

                if p is None:
                    name = "BYE"
                    text_color = SILVER
                else:
                    name_val = p.get("team_name") if isinstance(p, dict) else getattr(p, "team_name", "?")
                    name = name_val[:20] if name_val else "?"
                    text_color = WHITE if not won else GOLD

                draw.text(
                    (card_x + 10, card_y + CARD_H // 2),
                    name,
                    font=font_team,
                    fill=text_color,
                    anchor="lm",
                )

                if score_txt:
                    draw.text(
                        (card_x + CARD_W - 10, card_y + CARD_H // 2),
                        score_txt,
                        font=font_score,
                        fill=GOLD if won else LIGHT_GRAY,
                        anchor="rm",
                    )

            if p1 is not None:
                next_round.append(p1)
            if p2 is not None:
                next_round.append(p2)

            if r < rounds - 1:
                next_x = x + CARD_W + ROUND_GAP
                next_positions = get_round_y_positions(r + 1)
                next_top_y = next_positions[i] if i < len(next_positions) else top_y

                mid1_y = top_y + CARD_H // 2
                mid2_y = top_y + CARD_H + CARD_GAP + CARD_H // 2
                center_y = (mid1_y + mid2_y) // 2
                next_card_y = next_top_y + CARD_H // 2

                draw.line([(x + CARD_W, mid1_y), (x + CARD_W + ROUND_GAP // 2, mid1_y)], fill=LINE_COLOR, width=2)
                draw.line([(x + CARD_W, mid2_y), (x + CARD_W + ROUND_GAP // 2, mid2_y)], fill=LINE_COLOR, width=2)
                draw.line(
                    [(x + CARD_W + ROUND_GAP // 2, mid1_y), (x + CARD_W + ROUND_GAP // 2, mid2_y)],
                    fill=LINE_COLOR,
                    width=2,
                )
                draw.line(
                    [(x + CARD_W + ROUND_GAP // 2, center_y), (next_x, next_card_y)],
                    fill=LINE_COLOR,
                    width=2,
                )

        all_round_participants.append(next_round)

    trophy_x = PADDING_LEFT + rounds * (CARD_W + ROUND_GAP)
    trophy_y = total_height // 2
    draw.text((trophy_x, trophy_y), "🏆", font=load_font(40), fill=GOLD, anchor="mm")

    buf = io.BytesIO()
    img = img.convert("RGB")
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()


def generate_group_stage_image(
    groups: dict,
    tournament_name: str,
    matches: list = None,
) -> bytes:
    group_names = sorted(groups.keys())
    n_groups = len(group_names)

    COL_W = 280
    ROW_H = 44
    GAP = 16
    PADDING = 40
    GROUP_GAP = 30
    HEADER_H = 120

    max_teams = max(len(v) for v in groups.values()) if groups else 4
    col_count = min(n_groups, 4)
    row_count = math.ceil(n_groups / col_count)

    total_w = PADDING * 2 + col_count * (COL_W + GAP)
    group_h = (max_teams + 1) * (ROW_H + 4) + GROUP_GAP
    total_h = HEADER_H + row_count * group_h + PADDING

    img = Image.new("RGBA", (total_w, total_h), DARK_BG)
    draw_gradient_bg(img)
    draw_stars(ImageDraw.Draw(img), total_w, total_h)
    draw = ImageDraw.Draw(img, "RGBA")

    font_title = load_font(26, bold=True)
    font_group = load_font(14, bold=True)
    font_team = load_font(12)

    draw.text((total_w // 2, 28), "⚽ eFOOTBALL TURNIRI — GURUHLAR", font=font_title, fill=GOLD, anchor="mt")
    draw.text((total_w // 2, 65), tournament_name.upper(), font=load_font(16, bold=True), fill=WHITE, anchor="mt")
    draw.line([(40, 98), (total_w - 40, 98)], fill=GOLD, width=2)

    for gi, gname in enumerate(group_names):
        col = gi % col_count
        row = gi // col_count
        x = PADDING + col * (COL_W + GAP)
        y = HEADER_H + row * group_h

        draw_rounded_rect(
            draw,
            (x, y, x + COL_W, y + (max_teams + 1) * (ROW_H + 4) + 10),
            fill=(15, 25, 50),
            outline=GOLD,
            radius=8,
            width=2,
        )

        draw.text(
            (x + COL_W // 2, y + 10),
            f"GURUH {gname}",
            font=font_group,
            fill=GOLD,
            anchor="mt",
        )

        header_y = y + ROW_H - 10
        draw.line([(x + 8, header_y), (x + COL_W - 8, header_y)], fill=CARD_BORDER, width=1)

        for ti, team in enumerate(groups[gname]):
            ty = y + ROW_H + 4 + ti * (ROW_H // 2 + 8)
            team_name = team.get("team_name") if isinstance(team, dict) else getattr(team, "team_name", "?")
            draw.text(
                (x + 14, ty),
                f"{ti + 1}. {team_name[:28]}",
                font=font_team,
                fill=WHITE,
            )

    buf = io.BytesIO()
    img = img.convert("RGB")
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()
