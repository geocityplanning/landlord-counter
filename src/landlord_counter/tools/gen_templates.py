"""生成扑克牌识别模板（无需手动截图，用 PIL 绘制标准牌面）。

用法: uv run python -m landlord_counter.tools.gen_templates
输出: assets/card_templates/<rank>.png
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..config import PROJECT_ROOT
from ..logic.tracker import ALL_RANKS

CARD_W, CARD_H = 120, 180
SUIT_COLORS = {"♠": "black", "♥": "red", "♣": "black", "♦": "red"}


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_card(rank: str, suit: str) -> Image.Image:
    """绘制一张牌: 左上角点数+花色"""
    img = Image.new("RGB", (CARD_W, CARD_H), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([1, 1, CARD_W - 2, CARD_H - 2], outline="black", width=2)
    color = SUIT_COLORS[suit]
    font_rank = _load_font(40)
    font_suit = _load_font(36)
    label = rank if rank != "10" else "10"
    draw.text((10, 8), label, fill=color, font=font_rank)
    draw.text((12, 52), suit, fill=color, font=font_suit)
    return img


def draw_joker(is_big: bool) -> Image.Image:
    """绘制大小王"""
    img = Image.new("RGB", (CARD_W, CARD_H), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([1, 1, CARD_W - 2, CARD_H - 2], outline="black", width=2)
    color = "red" if is_big else "black"
    font = _load_font(30)
    draw.text((12, 8), "大王" if is_big else "小王", fill=color, font=font)
    return img


def generate(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for rank in ALL_RANKS:
        if rank in ("BJ", "RJ"):
            img = draw_joker(rank == "RJ")
        else:
            suit = "♠"  # 用黑桃做模板（花色不影响记牌）
            img = draw_card(rank, suit)
        img.save(output_dir / f"{rank}.png")
        count += 1
    print(f"✓ 已生成 {count} 张模板到 {output_dir}")


def generate_cli():
    generate(PROJECT_ROOT / "assets" / "card_templates")


if __name__ == "__main__":
    generate_cli()
