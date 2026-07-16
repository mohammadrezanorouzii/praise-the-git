"""Dark Souls style terminal banner — "CODE PUSHED" and friends.

Usage:
    code-pushed                     # shows "CODE PUSHED" (gold)
    code-pushed "VICTORY ACHIEVED"  # any text
    code-pushed --red "YOU DIED"    # blood-red theme
    code-pushed --theme silver "UNDEAD BURG"  # gold / red / silver
    code-pushed --souls 1247 ...    # souls counter under the banner
    code-pushed --no-sound ...      # silent
    code-pushed --dump ...          # print one static frame (for testing)
    code-pushed --png out.png ...   # render a frame to an image (for testing)

Rendering: if PIL is available, the text is rasterized with a real serif
font (Cinzel — the Trajan-style face Dark Souls uses — falling back to a
system serif) and drawn with quadrant block characters, giving a 2x2 grid
of antialiased pixels per terminal cell. Without PIL it falls back to a
5x7 bitmap font.

Supported on Linux, macOS, and Windows 10+ (cmd / Windows Terminal).
"""

import argparse
import math
import os
import shutil
import subprocess
import sys
import time

PKG_DIR = os.path.dirname(os.path.realpath(__file__))


def _data_dir():
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        return os.path.join(base, "code-pushed")
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library",
                            "Application Support", "code-pushed")
    base = os.environ.get("XDG_DATA_HOME",
                          os.path.join(os.path.expanduser("~"), ".local", "share"))
    return os.path.join(base, "code-pushed")


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

    tracking = int(S * 0.13)  # Dark Souls style wide letter-spacing
    tmp = ImageDraw.Draw(Image.new("L", (8, 8)))
    widths = [tmp.textlength(ch, font=font) for ch in text]
    W = int(sum(widths)) + tracking * max(0, len(text) - 1) + 2 * S
    img = Image.new("L", (W, S * 2), 0)
    d = ImageDraw.Draw(img)
    x = float(S // 2)
    for ch, w in zip(text, widths):
        d.text((x, S // 2), ch, font=font, fill=255)
        x += w + tracking
    bbox = img.getbbox()
    if bbox is None:
        return None
    img = img.crop(bbox)

    scale = target_h / img.height
    tw = max(1, int(img.width * scale * xscale))
    th = target_h
    if tw > max_px:
        tw = max_px
        th = max(8, int(img.height * tw / (img.width * xscale)))
    if th % 2:
        th += 1
    if tw % 2:
        tw += 1
    img = img.resize((tw, th), Image.LANCZOS)

    px = img.load()
    return [[px[c, r] for c in range(tw)] for r in range(th)]


def fgbg(top, bot):
    return "\x1b[38;2;%d;%d;%dm\x1b[48;2;%d;%d;%dm" % (
        int(top[0]), int(top[1]), int(top[2]),
        int(bot[0]), int(bot[1]), int(bot[2]))


# quadrant glyph for each 4-bit pixel mask (bit0=TL, bit1=TR, bit2=BL, bit3=BR)
QUADS = " ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█"


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
    for r in range(H):
        u = (r + 0.5) / H
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

    def avg(colors):
        n = len(colors)
        return (sum(c[0] for c in colors) / n,
                sum(c[1] for c in colors) / n,
                sum(c[2] for c in colors) / n)

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
            thr = (max(lum) + min(lum)) / 2
            mask = 0
            hi, lo = [], []
            for b, (p, l) in enumerate(zip(px, lum)):
                if l >= thr:
                    mask |= 1 << b
                    hi.append(p)
                else:
                    lo.append(p)
            code = fgbg(avg(hi), avg(lo) if lo else (0, 0, 0))
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


def get_coverage(text, cols, rows):
    max_cols = cols - 4
    text_rows = min(16, max(7, rows // 3))
    cov = rasterize(text, max_cols * 2, text_rows * 2, xscale=2)
    if cov is None:
        cov = bitmap_coverage(text.upper(), max_cols)
    return cov


# -------------------------------------------------------------- sound ----
def sound_path():
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, "chime.wav")


def synth_chime(path):
    """Synthesize a solemn orchestral-swell style chime (pure stdlib)."""
    import struct
    import wave
    rate = 22050
    dur = 3.0
    n = int(rate * dur)
    partials = [
        (110.00, 1.00), (164.81, 0.65), (220.00, 0.55),
        (261.63, 0.35), (329.63, 0.18),
    ]
    samples = []
    for i in range(n):
        t = i / rate
        if t < 0.5:
            env = (t / 0.5) ** 2
        else:
            env = math.exp(-(t - 0.5) / 1.1)
        v = 0.0
        for f, a in partials:
            vib = 1.0 + 0.002 * math.sin(2 * math.pi * 5.0 * t)
            v += a * math.sin(2 * math.pi * f * vib * t)
        v += 0.9 * math.exp(-t / 0.25) * math.sin(2 * math.pi * 55.0 * t)
        samples.append(v * env)
    # normalize to 95% of full scale — as loud as possible without clipping
    gain = 0.95 / (max(abs(s) for s in samples) or 1.0)
    pcm = [int(max(-1.0, min(1.0, s * gain)) * 32767) for s in samples]
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<%dh" % n, *pcm))


def play_sound():
    path = sound_path()
    try:
        if not os.path.exists(path):
            synth_chime(path)
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
    except Exception:
        pass  # sound is best-effort, never break the banner


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


def animate(text, theme, sound, souls=None):
    size = shutil.get_terminal_size((80, 24))
    cols, rows = size.columns, size.lines
    cov = get_coverage(text, cols, rows)
    width = len(cov[0])

    pad_rows = 2
    band_rows = len(cov) // 2 + 2 * pad_rows
    top = max(1, (rows - band_rows) // 2 + 1)

    fade_in, hold, fade_out = 0.55, 1.5, 0.9
    total = fade_in + hold + fade_out
    fps = 30.0

    w = sys.stdout
    w.write("\x1b[?1049h\x1b[?25l\x1b[2J")  # alt screen, hide cursor, clear
    w.flush()
    if sound:
        play_sound()
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
            lines = hires_frame(cov, cols, theme, b, shine)
            out = []
            draw_band(out, top, cols, lines, pad_rows)
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


def dump_png(text, theme, out_path, shine=True):
    """Render one frame to a PNG (pixel-accurate preview) — for testing."""
    from PIL import Image
    size = shutil.get_terminal_size((80, 24))
    cov = get_coverage(text, size.columns, size.lines)
    dark, bright, glow = THEMES[theme]
    H, W = len(cov), len(cov[0])
    pad = 8
    img = Image.new("RGB", (W + 2 * pad, H + 2 * pad), (0, 0, 0))
    px = img.load()
    sigma = max(20.0, H * 2.2)
    shine_x = W * 0.55 if shine else None
    for r in range(H):
        u = (r + 0.5) / H
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
    # pixels are half as wide as tall on screen: stretch 2x/4x to match
    img = img.resize((img.width * 2, img.height * 4), Image.NEAREST)
    img.save(out_path)
    print("wrote", out_path)


def main():
    ap = argparse.ArgumentParser(description="Dark Souls style terminal banner")
    ap.add_argument("text", nargs="*", help='banner text (default: "CODE PUSHED")')
    ap.add_argument("--red", action="store_true", help="blood-red theme (YOU DIED)")
    ap.add_argument("--theme", choices=sorted(THEMES),
                    help="color theme (gold, red, silver); overrides --red")
    ap.add_argument("--no-sound", action="store_true", help="skip the chime")
    ap.add_argument("--souls", type=int, metavar="N",
                    help="show a souls counter under the banner (e.g. commit count)")
    ap.add_argument("--dump", action="store_true",
                    help="print one static frame and exit (testing)")
    ap.add_argument("--png", metavar="PATH",
                    help="render one frame to a PNG and exit (testing)")
    args = ap.parse_args()

    text = " ".join(args.text) if args.text else "CODE PUSHED"
    theme = args.theme or ("red" if args.red else "gold")

    enable_vt()
    if args.png:
        dump_png(text, theme, args.png)
        return
    if args.dump:
        dump(text, theme, souls=args.souls)
        return
    if not sys.stdout.isatty():
        return  # non-interactive (scripts, CI): stay silent
    try:
        animate(text, theme, sound=not args.no_sound, souls=args.souls)
    except KeyboardInterrupt:
        sys.stdout.write("\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
