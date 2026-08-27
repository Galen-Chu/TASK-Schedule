"""Vector emblems for the seven divination systems.

Drawn with reportlab.graphics shapes only — no font glyphs, so they render
identically on any host (emoji like 📍/🎯 become .notdef boxes under the
CI CJK font). One emblem per system, in the system's brand colors:

  0 人類圖   abstract bodygraph (head square ▸ ajna triangle ▸ centers)
  1 西洋占星 sun disc with rays
  2 紫微斗數 five-pointed star in a frame (紫微星盤)
  3 八字     four pillars (年/月/日/時)
  4 梅花易數 plum blossom (five petals + center)
  5 易經六爻 hexagram lines with broken yao
  6 塔羅     tarot card with a star
"""
import math

from reportlab.graphics.shapes import Drawing, Circle, Rect, Polygon, Line


def _hex(color_obj):
    """'#rrggbb' from a reportlab color object."""
    return "#" + color_obj.hexval()[2:]


def _star_pts(cx, cy, r, ratio=0.42):
    pts = []
    for i in range(10):
        ang = math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * ratio
        pts += [cx + rad * math.cos(ang), cy + rad * math.sin(ang)]
    return pts


def system_emblem(index, primary, highlight, size=40):
    """Emblem Drawing for system ``index`` (0-6) in the given colors."""
    u = size / 10.0
    d = Drawing(size, size)

    def rect(x, y, w, h, fill=None, stroke=None, sw=1.3):
        d.add(Rect(x * u, y * u, w * u, h * u, fillColor=fill,
                   strokeColor=stroke, strokeWidth=sw))

    def circle(cx, cy, r, fill=None, stroke=None, sw=1.3):
        d.add(Circle(cx * u, cy * u, r * u, fillColor=fill,
                     strokeColor=stroke, strokeWidth=sw))

    def line(x1, y1, x2, y2, color, sw=1.0):
        d.add(Line(x1 * u, y1 * u, x2 * u, y2 * u,
                   strokeColor=color, strokeWidth=sw))

    if index == 0:      # 人類圖 — abstract bodygraph
        rect(3.2, 7.6, 1.6, 1.6, stroke=primary)
        d.add(Polygon([3.4, 7.4, 4.6, 7.4, 4.0, 6.3],
                      fillColor=None, strokeColor=primary, strokeWidth=1.3))
        circle(4.0, 4.9, 1.0, stroke=primary)
        circle(4.0, 2.6, 0.85, stroke=highlight)
        circle(6.4, 5.6, 0.75, stroke=highlight)
        line(4.0, 6.3, 4.0, 5.9, highlight)
        line(4.0, 3.9, 4.0, 3.45, highlight)
        line(4.85, 5.3, 5.65, 5.55, highlight)
    elif index == 1:    # 西洋占星 — sun
        circle(5.0, 5.0, 2.0, stroke=primary)
        circle(5.0, 5.0, 0.45, fill=primary)
        for k in range(8):
            a = k * math.pi / 4
            line(5.0 + 2.7 * math.cos(a), 5.0 + 2.7 * math.sin(a),
                 5.0 + 3.6 * math.cos(a), 5.0 + 3.6 * math.sin(a), highlight, 1.1)
    elif index == 2:    # 紫微斗數 — star in frame
        rect(1.4, 1.4, 7.2, 7.2, stroke=highlight, sw=0.9)
        d.add(Polygon(_star_pts(5.0 * u, 5.0 * u, 2.7 * u),
                      fillColor=primary, strokeColor=None))
    elif index == 3:    # 八字 — four pillars
        for i, h in enumerate((4.6, 6.4, 5.4, 7.2)):
            rect(1.6 + i * 1.9, 1.5, 1.3, h,
                 fill=primary if i % 2 == 0 else highlight)
    elif index == 4:    # 梅花易數 — plum blossom
        for k in range(5):
            a = math.pi / 2 + k * 2 * math.pi / 5
            circle(5.0 + 2.4 * math.cos(a), 5.0 + 2.4 * math.sin(a),
                   1.05, stroke=primary)
        circle(5.0, 5.0, 0.6, fill=highlight)
    elif index == 5:    # 易經六爻 — hexagram (third yao broken, yang else)
        for row in range(6):
            y = 1.7 + row * 1.35
            if row == 2:                      # 陰爻(斷)
                rect(2.0, y, 2.6, 0.75, fill=primary)
                rect(5.4, y, 2.6, 0.75, fill=primary)
            else:                             # 陽爻(整)
                rect(2.0, y, 6.0, 0.75, fill=highlight if row in (0, 5) else primary)
    else:               # 塔羅 — card with star
        d.add(Rect(2.8 * u, 1.2 * u, 4.4 * u, 7.6 * u, fillColor=None,
                   strokeColor=primary, strokeWidth=1.4, ry=0.6 * u))
        d.add(Polygon(_star_pts(5.0 * u, 5.6 * u, 1.5 * u),
                      fillColor=highlight, strokeColor=None))
        circle(5.0, 2.9, 0.5, fill=primary)
    return d
