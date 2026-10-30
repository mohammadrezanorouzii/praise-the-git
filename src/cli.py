"""Praise the Git \\[T]/ — Dark Souls style terminal banners.

Usage:
    praise                     # shows "CODE PUSHED" (gold)
    praise "VICTORY ACHIEVED"  # any text
    praise --red "YOU DIED"    # blood-red theme
    praise --theme silver "UNDEAD BURG"  # gold / red / silver
    praise --souls 1247 ...    # souls counter under the banner
    praise --no-sound ...      # silent
    praise --dump ...          # print one static frame (for testing)
    praise --png out.png ...   # render a frame to an image (for testing)

Banners use the bundled Cinzel font via Pillow, rendered with antialiased
terminal block characters.

Supported on Linux, macOS, and Windows 10+ (cmd / Windows Terminal).
"""

import argparse
import base64
import io
import math
import os
import secrets
import shutil
import subprocess
import sys
import time

PKG_DIR = os.path.dirname(os.path.realpath(__file__))


def _data_dir():
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        return os.path.join(base, "praise-the-git")
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library",
                            "Application Support", "praise-the-git")
    base = os.environ.get("XDG_DATA_HOME",
                          os.path.join(os.path.expanduser("~"), ".local", "share"))
    return os.path.join(base, "praise-the-git")


DATA_DIR = _data_dir()

FONT_CANDIDATES = [
    os.path.join(PKG_DIR, "assets", "Cinzel.ttf"),
    os.path.join(DATA_DIR, "Cinzel.ttf"),
]
if os.name == "nt":
    _windir = os.environ.get("WINDIR", r"C:\Windows")
    FONT_CANDIDATES += [os.path.join(_windir, "Fonts", f)
                        for f in ("georgiab.ttf", "timesbd.ttf", "georgia.ttf")]
elif sys.platform == "darwin":
    FONT_CANDIDATES += [
        "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    ]
else:
    FONT_CANDIDATES += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]

# ------------------------------------------------------------- themes ----
THEMES = {
    # (dark edge color, bright core color, glow color)
    'gold':   ((150, 96, 18),  (255, 224, 130), (255, 246, 200)),
    'red':    ((96, 6, 4),     (205, 38, 30),   (255, 120, 100)),
    # area-name banner style ("UNDEAD BURG"): cold white/silver
    'silver': ((105, 108, 122), (232, 235, 242), (255, 255, 255)),
}

RESET = "\x1b[0m"
BG_BLACK = "\x1b[48;2;0;0;0m"


def enable_vt():
    """Enable ANSI escape processing in the classic Windows console (cmd)."""
    if os.name != "nt":
        return
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        for std in (-11, -12):  # stdout, stderr
            h = k32.GetStdHandle(std)
            mode = ctypes.c_uint32()
            if k32.GetConsoleMode(h, ctypes.byref(mode)):
                # 0x0004 = ENABLE_VIRTUAL_TERMINAL_PROCESSING
                k32.SetConsoleMode(h, mode.value | 0x0004)
    except Exception:
        pass


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t,
            a[1] + (b[1] - a[1]) * t,
            a[2] + (b[2] - a[2]) * t)


# --------------------------------------------------- hi-res rasterizer ----
def load_truetype(size):
    try:
        from PIL import ImageFont
    except ImportError:
        return None
    for path in FONT_CANDIDATES:
        if not os.path.exists(path):
            continue
        try:
            f = ImageFont.truetype(path, size)
            try:
                f.set_variation_by_axes([700])
            except Exception:
                pass
            return f
        except Exception:
            continue
    return None


def rasterize(text, max_px, target_h, xscale=1):
    """Rasterize text with a real font -> list of pixel rows (coverage 0-255).

    Rendered large, then LANCZOS-downscaled to target_h pixels tall, so the
    antialiasing survives. xscale stretches the output horizontally to
    compensate for non-square terminal pixels (quadrant pixels are 2x
    taller than wide). Returns None if PIL / fonts are unavailable.
    """
    S = 128  # supersample size
    font = load_truetype(S)
    if font is None:
        return None
    from PIL import Image, ImageDraw

    # Moderate tracking leaves room for fine serifs at small grid sizes.
    # Pair advances preserve the font's kerning (e.g. AV and WA).
    tracking = S * 0.08
    tmp = ImageDraw.Draw(Image.new("L", (8, 8)))
    positions = [0.0]
    for i, ch in enumerate(text[:-1]):
        advance = (tmp.textlength(ch + text[i + 1], font=font)
                   - tmp.textlength(text[i + 1], font=font))
        positions.append(positions[-1] + advance + tracking)
    W = int(positions[-1] + tmp.textlength(text[-1], font=font) + 2 * S) if text else 2 * S
    img = Image.new("L", (W, S * 2), 0)
    d = ImageDraw.Draw(img)
    for ch, x in zip(text, positions):
        d.text((S // 2 + x, S // 2), ch, font=font, fill=255)
    bbox = img.getbbox()
    if bbox is None:
        return None
    img = img.crop(bbox)

    scale = target_h / img.height
    tw = max(1, int(img.width * scale * xscale))
    th = target_h
    if tw > max_px:
        tw = max_px
        th = max(2, int(img.height * tw / (img.width * xscale)))
    # Round down within the limits; never overflow the available columns.
    th = max(2, th - th % 2)
    tw = max(2, tw - tw % 2)
    img = img.resize((tw, th), Image.LANCZOS)

    px = img.load()
    return [[px[c, r] for c in range(tw)] for r in range(th)]


def fgbg(top, bot):
    return "\x1b[38;2;%d;%d;%dm\x1b[48;2;%d;%d;%dm" % (
        int(top[0]), int(top[1]), int(top[2]),
        int(bot[0]), int(bot[1]), int(bot[2]))


# quadrant glyph for each 4-bit pixel mask (bit0=TL, bit1=TR, bit2=BL, bit3=BR)
QUADS = " ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█"


def split_cell(pixels):
    """Choose the two colors that best approximate four pixel colors.

    Quadrant characters can only represent two colors in a cell. Try each
    possible split in brightness order and choose the least squared RGB error.
    """
    order = sorted(range(4), key=lambda i: sum(pixels[i]))
    best = None
    for cut in range(1, 5):
        low, high = order[:cut], order[cut:]
        def average(group):
            return tuple(sum(pixels[i][c] for i in group) / len(group)
                         for c in range(3)) if group else (0, 0, 0)
        lo, hi = average(low), average(high)
        error = sum((pixels[i][c] - (lo if i in low else hi)[c]) ** 2
                    for i in range(4) for c in range(3))
        if best is None or error < best[0]:
            best = (error, sum(1 << i for i in high), hi, lo)
    _, mask, fg, bg = best
    return mask, fg, bg


def gradient_positions(cov):
    """Restart the metallic gradient for each line of a wrapped banner."""
    positions = [0.5] * len(cov)
    start = 0
    while start < len(cov):
        if not any(cov[start]):
            start += 1
            continue
        end = start + 1
        while end < len(cov) and any(cov[end]):
            end += 1
        for r in range(start, end):
            positions[r] = (r - start + 0.5) / (end - start)
        start = end
    return positions


def hires_frame(cov, cols, theme, brightness, shine_x):
    """Render coverage rows into terminal lines using quadrant blocks.

    Each terminal cell shows a 2x2 grid of pixels: the four pixels are split
    into a bright and a dark group, drawn as the matching quadrant glyph with
    fg = bright group average, bg = dark group average. Returns list of
    len(cov)//2 strings.
    """
    dark, bright, glow = THEMES[theme]
    H = len(cov)
    width = len(cov[0]) // 2  # terminal cells; 2 px per cell horizontally
    left = max(0, (cols - width) // 2)
    sigma = max(20.0, H * 2.2)

    # metallic vertical gradient, brightest slightly above center
    row_base = []
    for u in gradient_positions(cov):
        wgt = 0.40 + 0.60 * math.exp(-((u - 0.40) / 0.30) ** 2)
        row_base.append(lerp(dark, bright, wgt))

    def px_color(r, c):
        a = cov[r][c]
        if a == 0:
            return (0.0, 0.0, 0.0)
        color = row_base[r]
        if shine_x is not None:
            g = math.exp(-((c - shine_x) / sigma) ** 2)
            if g > 0.02:
                color = lerp(color, glow, 0.9 * g)
        f = (a / 255.0) * brightness
        return (min(255.0, color[0] * f),
                min(255.0, color[1] * f),
                min(255.0, color[2] * f))

    lines = []
    for i in range(H // 2):
        rt, rb = 2 * i, 2 * i + 1
        parts = [BG_BLACK, " " * left]
        last = None
        blanks = 0
        for c in range(width):
            cl, cr = 2 * c, 2 * c + 1
            px = (px_color(rt, cl), px_color(rt, cr),
                  px_color(rb, cl), px_color(rb, cr))
            lum = [p[0] + p[1] + p[2] for p in px]
            if max(lum) < 3.0:
                blanks += 1
                continue
            if blanks:
                if last is not None:
                    parts.append(BG_BLACK)
                    last = None
                parts.append(" " * blanks)
                blanks = 0
            mask, fg, bg = split_cell(px)
            code = fgbg(fg, bg)
            if code != last:
                parts.append(code)
                last = code
            parts.append(QUADS[mask])
        if last is not None:
            parts.append(BG_BLACK)
        parts.append(" " * (blanks + cols - left - width))
        lines.append("".join(parts) + RESET)
    return lines


# ------------------------------------------- bitmap fallback (no PIL) ----
FONT = {
    'A': [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    'B': ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    'C': [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    'D': ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    'E': ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    'F': ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    'G': [".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."],
    'H': ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    'I': ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"],
    'J': [".####", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    'K': ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    'L': ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    'M': ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    'N': ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    'O': [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    'P': ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    'Q': [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    'R': ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    'S': [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    'T': ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    'U': ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    'V': ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    'W': ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"],
    'X': ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
    'Y': ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    'Z': ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    '0': [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    '1': ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", "#####"],
    '2': [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    '3': [".###.", "#...#", "....#", "..##.", "....#", "#...#", ".###."],
    '4': ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    '5': ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    '6': [".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."],
    '7': ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    '8': [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    '9': [".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."],
    '/': ["....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."],
    '_': [".....", ".....", ".....", ".....", ".....", ".....", "#####"],
    '!': ["#", "#", "#", "#", "#", ".", "#"],
    '?': [".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."],
    '.': [".", ".", ".", ".", ".", ".", "#"],
    '-': ["...", "...", "...", "###", "...", "...", "..."],
    "'": ["#", "#", ".", ".", ".", ".", "."],
    ' ': ["...", "...", "...", "...", "...", "...", "..."],
}
GLYPH_ROWS = 7


def bitmap_coverage(text, max_cols):
    """Fallback: expand the 5x7 font into a coverage array (hard pixels)."""
    for hstretch in (2, 1):
        rows = ["" for _ in range(GLYPH_ROWS)]
        for i, ch in enumerate(text):
            glyph = FONT.get(ch.upper(), FONT['?'])
            for r in range(GLYPH_ROWS):
                if i:
                    rows[r] += ".."
                rows[r] += glyph[r]
        if hstretch > 1:
            rows = ["".join(p * hstretch for p in row) for row in rows]
        if len(rows[0]) <= max_cols:
            break
    rows = [row[:max_cols] for row in rows]
    # double each pixel both ways so the quadrant renderer can consume it
    cov = []
    for row in rows:
        line = [255 if p == '#' else 0 for p in row for _ in (0, 1)]
        cov.append(line)
        cov.append(list(line))
    return cov


def get_coverage(text, cols, rows, scale=1):
    """Fit a large, antialiased banner into the terminal, wrapping words.

    Wrapping retains detail for long messages rather than shrinking the whole
    sentence to a few pixels. Leave space for the band and souls counter.
    """
    max_cols = max(1, cols - 4)
    max_px = max_cols * 2 * scale
    max_rows = max(1, rows - 4)
    words = text.split()
    if not words:
        return [[0] * (2 * scale) for _ in range(2 * scale)]

    # Try the largest height first, reducing it only if the wrapped banner
    # would exceed the available screen height.
    for text_rows in range(min(8, max_rows), 0, -1):
        lines = []
        line = ""
        word_too_wide = False
        for word in words:
            candidate = (line + " " + word).strip()
            # Measure at the requested height before applying the width limit.
            measured = rasterize(candidate, 10000000, text_rows * 2 * scale, xscale=2)
            if measured is None:
                fallback = bitmap_coverage(text.upper(), max_cols)
                if len(fallback) > max_rows * 2:
                    height = max_rows * 2
                    fallback = [fallback[i * len(fallback) // height]
                                for i in range(height)]
                return fallback
            if line and len(measured[0]) > max_px:
                lines.append(line)
                line = word
                single = rasterize(word, 10000000, text_rows * 2 * scale, xscale=2)
                word_too_wide |= len(single[0]) > max_px
            elif not line and len(measured[0]) > max_px:
                line = word
                word_too_wide = True
            else:
                line = candidate
        lines.append(line)
        if word_too_wide and text_rows > 1:
            continue
        images = [rasterize(line, max_px, text_rows * 2 * scale, xscale=2)
                  for line in lines]
        images = [image for image in images if image is not None]
        height = sum(len(image) for image in images) + 2 * scale * (len(images) - 1)
        if height <= max_rows * 2 * scale:
            break
        if text_rows == 1:
            # Extremely small terminals or very long input: fit one line.
            images = [rasterize(text, max_px, max_rows * 2 * scale, xscale=2)]
            break

    # Center each line on a common canvas. Each blank separator is one cell high.
    width = max(len(image[0]) for image in images)
    result = []
    for i, image in enumerate(images):
        if i:
            result.extend([[0] * width for _ in range(2 * scale)])
        left = (width - len(image[0])) // 2
        right = width - len(image[0]) - left
        result.extend([[0] * left + row + [0] * right for row in image])
    unit = 2 * scale
    padded_width = ((width + unit - 1) // unit) * unit
    result = [row + [0] * (padded_width - width) for row in result]
    while len(result) % unit:
        result.append([0] * padded_width)
    return result


def graphics_supported():
    """Conservatively detect direct terminals with kitty graphics support."""
    if os.environ.get("TMUX") or os.environ.get("STY"):
        return False
    return (bool(os.environ.get("KITTY_WINDOW_ID"))
            or os.environ.get("TERM") == "xterm-kitty"
            or os.environ.get("TERM_PROGRAM", "").lower() in ("wezterm", "ghostty"))


def graphics_image(cov, theme):
    """Create a full-resolution RGB banner, without quadrant quantization."""
    from PIL import Image
    dark, bright, _ = THEMES[theme]
    height, width = len(cov), len(cov[0])
    img = Image.new("RGB", (width, height))
    px = img.load()
    for row, u in enumerate(gradient_positions(cov)):
        weight = 0.40 + 0.60 * math.exp(-((u - 0.40) / 0.30) ** 2)
        color = lerp(dark, bright, weight)
        for col, alpha in enumerate(cov[row]):
            if alpha:
                px[col, row] = tuple(int(value * alpha / 255) for value in color)
    # Terminal cells are approximately twice as tall as they are wide.
    return img.resize((width, height * 2), Image.Resampling.LANCZOS
                      if hasattr(Image, "Resampling") else Image.LANCZOS)


def kitty_frame(img, brightness, image_id, cols, rows):
    """Encode a graphics-protocol frame in bounded base64 chunks."""
    table = [int(i * brightness) for i in range(256)] * 3
    frame = img.point(table)
    buf = io.BytesIO()
    frame.save(buf, format="PNG")
    payload = base64.b64encode(buf.getvalue()).decode("ascii")
    chunks = [payload[i:i + 4096] for i in range(0, len(payload), 4096)]
    parts = []
    for index, chunk in enumerate(chunks):
        more = int(index < len(chunks) - 1)
        control = ("a=T,f=100,i=%d,c=%d,r=%d,C=1,q=2," %
                   (image_id, cols, rows)) if index == 0 else ""
        parts.append("\x1b_G%sm=%d;%s\x1b\\" % (control, more, chunk))
    return "".join(parts)


# -------------------------------------------------------------- sound ----
SOUNDS = {
    "push": "push.wav", "victory": "victory.wav",
    "fail": "fail.wav", "branch": "branch.wav", "stash": "stash.wav",
}


def play_sound(kind):
    path = os.path.join(PKG_DIR, "assets", "sounds", SOUNDS[kind])
    try:
        if os.name == "nt":
            import winsound
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            return
        players = []
        if sys.platform == "darwin":
            players.append(["afplay", path])
        players += [["paplay", path], ["aplay", "-q", path],
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path]]
        for player in players:
            if shutil.which(player[0]):
                subprocess.Popen(player, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                return
    except OSError:
        pass


# ----------------------------------------------------------- animation ----
def souls_label(souls):
    return "✦ SOULS: {:,}".format(souls)


def souls_sgr(theme, brightness):
    dark, bright, _ = THEMES[theme]
    color = lerp(dark, bright, 0.45)
    return "\x1b[38;2;%d;%d;%dm" % (int(color[0] * brightness),
                                    int(color[1] * brightness),
                                    int(color[2] * brightness))


def draw_band(out, top, cols, text_lines, pad_rows):
    blank = BG_BLACK + " " * cols + RESET
    row = top
    for _ in range(pad_rows):
        out.append("\x1b[%d;1H%s" % (row, blank)); row += 1
    for line in text_lines:
        out.append("\x1b[%d;1H%s" % (row, line)); row += 1
    for _ in range(pad_rows):
        out.append("\x1b[%d;1H%s" % (row, blank)); row += 1


def animate(text, theme, sound, souls=None, graphics=False):
    size = shutil.get_terminal_size((80, 24))
    cols, rows = size.columns, size.lines
    scale = 4 if graphics else 1
    cov = get_coverage(text, cols, rows, scale=scale)
    width = len(cov[0])
    image = graphics_image(cov, theme) if graphics else None
    image_id = secrets.randbelow(2**31 - 1) + 1 if graphics else None
    cell_width = len(cov[0]) // (2 * scale)
    cell_height = len(cov) // (2 * scale)
    pad_rows = 2
    band_rows = cell_height + 2 * pad_rows
    top = max(1, (rows - band_rows) // 2 + 1)

    fade_in, hold, fade_out = 0.55, 1.5, 0.9
    total = fade_in + hold + fade_out
    fps = 30.0

    w = sys.stdout
    w.write("\x1b[?1049h\x1b[?25l\x1b[2J")  # alt screen, hide cursor, clear
    w.flush()
    if sound:
        play_sound(sound)
    try:
        start = time.monotonic()
        while True:
            t = time.monotonic() - start
            if t >= total:
                break
            if t < fade_in:
                b = t / fade_in
                shine = None
            elif t < fade_in + hold:
                b = 1.0
                p = (t - fade_in) / hold
                shine = -30 + (width + 60) * p
            else:
                b = 1.0 - (t - fade_in - hold) / fade_out
                shine = None
            b = b * b * (3 - 2 * b)  # smoothstep
            if graphics:
                lines = [BG_BLACK + " " * cols + RESET] * cell_height
            else:
                lines = hires_frame(cov, cols, theme, b, shine)
            out = []
            draw_band(out, top, cols, lines, pad_rows)
            if graphics:
                # Delete only our previous frame, then place the next at the
                # same coordinates without moving the cursor.
                left = max(1, (cols - cell_width) // 2 + 1)
                out.append("\x1b_Ga=d,d=I,i=%d,q=2\x1b\\" % image_id)
                out.append("\x1b[%d;%dH" % (top + pad_rows, left))
                out.append(kitty_frame(image, b, image_id, cell_width, cell_height))
            if souls is not None:
                # counter sits on the band's bottom padding row
                label = souls_label(souls)
                col = max(1, (cols - len(label)) // 2 + 1)
                out.append("\x1b[%d;%dH%s%s%s%s" % (
                    top + band_rows - 1, col, BG_BLACK,
                    souls_sgr(theme, b), label, RESET))
            w.write("".join(out))
            w.flush()
            time.sleep(max(0.0, 1.0 / fps - ((time.monotonic() - start) % (1.0 / fps))))
    finally:
        if graphics:
            w.write("\x1b_Ga=d,d=I,i=%d,q=2\x1b\\" % image_id)
        w.write("\x1b[?25h\x1b[?1049l")  # restore cursor + screen
        w.flush()


def dump(text, theme, souls=None):
    """Print a single fully-lit frame (no alt screen) — for testing."""
    size = shutil.get_terminal_size((80, 24))
    cols = size.columns
    cov = get_coverage(text, cols, size.lines)
    blank = BG_BLACK + " " * cols + RESET
    print(blank)
    print(blank)
    for line in hires_frame(cov, cols, theme, 1.0, None):
        print(line)
    print(blank)
    if souls is None:
        print(blank)
        return
    label = souls_label(souls)
    left = max(0, (cols - len(label)) // 2)
    print(BG_BLACK + " " * left + souls_sgr(theme, 1.0) + label
          + BG_BLACK + " " * (cols - left - len(label)) + RESET)


def dump_png(text, theme, out_path, shine=True, graphics=False):
    """Render one frame to a PNG (pixel-accurate preview) — for testing."""
    from PIL import Image
    size = shutil.get_terminal_size((80, 24))
    if graphics:
        image = graphics_image(get_coverage(text, size.columns, size.lines, scale=4), theme)
        image.save(out_path)
        print("wrote", out_path)
        return
    cov = get_coverage(text, size.columns, size.lines)
    dark, bright, glow = THEMES[theme]
    H, W = len(cov), len(cov[0])
    pad = 8
    img = Image.new("RGB", (W + 2 * pad, H + 2 * pad), (0, 0, 0))
    px = img.load()
    sigma = max(20.0, H * 2.2)
    shine_x = W * 0.55 if shine else None
    for r, u in enumerate(gradient_positions(cov)):
        wgt = 0.40 + 0.60 * math.exp(-((u - 0.40) / 0.30) ** 2)
        base = lerp(dark, bright, wgt)
        for c in range(W):
            a = cov[r][c]
            if not a:
                continue
            color = base
            if shine_x is not None:
                g = math.exp(-((c - shine_x) / sigma) ** 2)
                if g > 0.02:
                    color = lerp(color, glow, 0.9 * g)
            f = a / 255.0
            px[c + pad, r + pad] = (int(color[0] * f), int(color[1] * f),
                                    int(color[2] * f))
    # Match the terminal's two-color quadrant approximation, not the
    # unquantized source image, so the preview shows actual grid detail.
    for r in range(0, H, 2):
        for c in range(0, W, 2):
            coords = ((c, r), (c + 1, r), (c, r + 1), (c + 1, r + 1))
            colors = [px[x + pad, y + pad] for x, y in coords]
            mask, fg, bg = split_cell(colors)
            for bit, (x, y) in enumerate(coords):
                color = fg if mask & (1 << bit) else bg
                px[x + pad, y + pad] = tuple(int(v) for v in color)
    # pixels are half as wide as tall on screen: stretch 2x/4x to match
    img = img.resize((img.width * 2, img.height * 4), Image.NEAREST)
    img.save(out_path)
    print("wrote", out_path)


def main():
    ap = argparse.ArgumentParser(
        prog="praise",
        description="Praise the Git \\[T]/ — Dark Souls style terminal banner")
    ap.add_argument("text", nargs="*", help='banner text (default: "CODE PUSHED")')
    ap.add_argument("--red", action="store_true", help="blood-red theme (YOU DIED)")
    ap.add_argument("--theme", choices=sorted(THEMES),
                    help="color theme (gold, red, silver); overrides --red")
    ap.add_argument("--graphics", choices=("auto", "blocks", "kitty"),
                    default=os.environ.get("PRAISE_GRAPHICS", "auto"),
                    help="rendering mode (default: auto; PRAISE_GRAPHICS also supported)")
    ap.add_argument("--sound", choices=sorted(SOUNDS), help="choose an effect")
    ap.add_argument("--no-sound", action="store_true", help="skip the sound")
    ap.add_argument("--souls", type=int, metavar="N",
                    help="show a souls counter under the banner (e.g. commit count)")
    ap.add_argument("--dump", action="store_true",
                    help="print one static frame and exit (testing)")
    ap.add_argument("--png", metavar="PATH",
                    help="render one frame to a PNG and exit (testing)")
    args = ap.parse_args()

    text = " ".join(args.text) if args.text else "CODE PUSHED"
    theme = args.theme or ("red" if args.red else "gold")

    if args.graphics not in ("auto", "blocks", "kitty"):
        ap.error("PRAISE_GRAPHICS must be auto, blocks, or kitty")
    graphics = (args.graphics == "kitty" or
                (args.graphics == "auto" and graphics_supported()))
    if graphics and load_truetype(128) is None:
        graphics = False

    enable_vt()
    if args.png:
        dump_png(text, theme, args.png, graphics=graphics)
        return
    if args.dump:
        dump(text, theme, souls=args.souls)
        return
    if not sys.stdout.isatty():
        return  # non-interactive (scripts, CI): stay silent
    try:
        kind = args.sound or ({"CODE PUSHED": "push", "VICTORY ACHIEVED": "victory",
                               "YOU DIED": "fail", "HUMANITY RESTORED": "stash"}.get(text.upper(), "branch" if theme == "silver" else "push"))
        animate(text, theme, sound=None if args.no_sound else kind, souls=args.souls, graphics=graphics)
    except KeyboardInterrupt:
        sys.stdout.write("\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
