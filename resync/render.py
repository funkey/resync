import skia
from .constants import \
    ERASE_AREA_TOOL, \
    HIGHLIGHTER_TOOL, \
    PENCIL_TOOL, \
    TOOL_ID


colors = [
    skia.Color(0, 0, 0),        # 0: black
    skia.Color(128, 128, 128),  # 1: gray
    skia.Color(255, 255, 255),  # 2: white
    skia.Color(255, 255, 0),    # 3: yellow
    skia.Color(0, 255, 0),      # 4: green
    skia.Color(255, 0, 255),    # 5: pink
    skia.Color(0, 0, 255),      # 6: blue
    skia.Color(255, 0, 0),      # 7: red
]


def render_lines(lines, canvas):

    for layer in lines.layers:
        render_layer(layer, canvas)


def render_layer(layer, canvas):

    for stroke in layer.strokes:
        tool = TOOL_ID.get(stroke.pen)
        if tool == ERASE_AREA_TOOL:
            continue
        elif tool == HIGHLIGHTER_TOOL:
            render_stroke_circles(stroke, canvas, 0.01)
        elif tool == PENCIL_TOOL:
            render_stroke_circles(stroke, canvas, 0.02)
        else:
            render_stroke_circles(stroke, canvas, 0.3)


def render_stroke_circles(stroke, canvas, opacity=1.0):

    paint = skia.Paint()
    paint.setStyle(skia.Paint.kFill_Style)
    paint.setColor(colors[stroke.color])
    paint.setAlpha(int(opacity * 255))
    paint.setStrokeWidth(0)

    for segment in stroke.segments:
        canvas.drawCircle(segment.x, segment.y, segment.width / 2, paint)
