from PyQt5.QtGui import \
    QColor, QPen, QPainterPathStroker, \
    QImage, QBrush, QTransform, QPainterPath
from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtWidgets import \
    QGraphicsScene, QGraphicsItem, \
    QGraphicsRectItem, QGraphicsPathItem
import logging
from itertools import groupby
from .constants import \
    WIDTH_PX, HEIGHT_PX, \
    TOOL_ID, HIGHLIGHTER_TOOL, ERASER_TOOL, \
    PENCIL_TOOL, MECH_PENCIL_TOOL, BRUSH_TOOL, \
    MARKER_TOOL, FINELINER_TOOL

logger = logging.getLogger(__name__)


def lines_to_scene(lines):

    scene = QGraphicsScene()

    r = scene.addRect(0, 0, WIDTH_PX, HEIGHT_PX)
    r.setFlag(QGraphicsItem.ItemClipsChildrenToShape)

    PageGraphicsItem(lines, parent=r)
    scene.setSceneRect(r.rect())
    return scene


DEFAULT_COLORS = [Qt.black, QColor('#bbbbbb'), Qt.white]
DEFAULT_HIGHLIGHT = QColor(255, 235, 147, 80)
QUICK_ERASER = 0
IGNORE_ERASER = 1
ACCURATE_ERASER = 2
AUTO_ERASER = 4
AUTO_ERASER_IGNORE = 4
AUTO_ERASER_ACCURATE = 5
ERASER_MODE = {
    "quick": QUICK_ERASER,
    "ignore": IGNORE_ERASER,
    "accurate": ACCURATE_ERASER,
    "auto": AUTO_ERASER,
}

try:

    from simplification.cutil import simplify_coords

    def simpl(stroke, tolerance=10.0):
        return simplify_coords([[s.x, s.y] for s in stroke.segments], tolerance)

except Exception:
    simpl = None

def pencil_width(segment):
    return (round(segment.width*.55,2), pencilBrushes().getIndex(segment.pressure))

def mech_pencil_width(segment):
    return (round(segment.width/1.5,2), pencilBrushes().getIndex(segment.pressure))

def flat_pencil_width(segment):
    return (round(segment.width*.55,2), round(segment.pressure, 2))

def flat_mech_pencil_width(segment):
    return (round(segment.width/1.5,2), round(segment.pressure, 2))

def const_width(w):
    return lambda stroke, segment: (w, None)

def dynamic_width(segment):
    return (segment.width, None)

class PencilBrushes():

    def __init__(self, N=15, size=200):
        from random import randint
        self._textures = []
        img = QImage(size, size, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        for i in range(N):
            for j in range(int(size*size*(i+1)/N/2.5)):
                img.setPixelColor(randint(0,size-1),randint(0,size-1),Qt.black)
            self._textures.append(img.copy())

    def getIndex(self, i):
        i = int(i * (len(self._textures)-1))
        return max(0, min(i, len(self._textures)-1))

    def getTexture(self, i):
        return self._textures[max(0,min(i, len(self._textures)-1))]

    def getBrush(self, i, scale=.4):
        b = QBrush(self.getTexture(i))
        if scale != 1:
            tr = QTransform()
            tr.scale(scale,scale)
            b.setTransform(tr)
        return b

_pencilBrushes = None
def pencilBrushes(**kw):
    global _pencilBrushes
    if _pencilBrushes is None:
        _pencilBrushes = PencilBrushes(**kw)
    return _pencilBrushes

def bezierInterpolation(K, coord):
    n = len(K)-1
    p1=[0.]*n
    p2=[0.]*n

    a=[0.]*n
    b=[0.]*n
    c=[0.]*n
    r=[0.]*n

    a[0]=0.
    b[0]=2.
    c[0]=1.
    r[0] = K[0][coord]+2.*K[1][coord]

    for i in range(1,n-1):
        a[i]=1.
        b[i]=4.
        c[i]=1.
        r[i] = 4. * K[i][coord] + 2. * K[i+1][coord]

    a[n-1]=2.
    b[n-1]=7.
    c[n-1]=0.
    r[n-1] = 8. *K[n-1][coord] + K[n][coord]

    # Thomas algorithm
    for i in range(1,n):
        m = a[i]/b[i-1]
        b[i] = b[i] - m * c[i - 1]
        r[i] = r[i] - m * r[i-1]

    p1[n-1] = r[n-1]/b[n-1]
    for i in range(n-2,-1,-1):
        p1[i] = (r[i] - c[i] * p1[i+1]) / b[i]

    for i in range(n-1):
        p2[i]=2.*K[i+1][coord]-p1[i+1]

    p2[n-1]=0.5*(K[n][coord]+p1[n-1])

    return (p1,p2)

class PageGraphicsItem(QGraphicsRectItem):

    def __init__(
            self,
            page,
            colors=DEFAULT_COLORS,
            highlight=DEFAULT_HIGHLIGHT,
            pencil_resolution=.4,
            simplify=0,
            smoothen=False,
            eraser_mode=AUTO_ERASER,
            parent=None,
            exclude_layers=set()
    ):
        super().__init__(0, 0, WIDTH_PX, HEIGHT_PX, parent)

        if isinstance(eraser_mode, str):
            eraser_mode = ERASER_MODE.get(eraser_mode, AUTO_ERASER)
        if isinstance(colors, dict):
            highlight = colors.get('highlight', highlight)
            colors = [
                QColor(colors.get('black', DEFAULT_COLORS[0])),
                QColor(colors.get('gray', DEFAULT_COLORS[1])),
                QColor(colors.get('white', DEFAULT_COLORS[2])),
            ]

        if simpl is None:
            simplify = 0
            logger.warning("Simplification parameters ignored since the simplification library is not installed")

        noPen = QPen(Qt.NoPen)
        noPen.setWidth(0)
        self.setPen(noPen)
        eraserStroker = QPainterPathStroker()
        eraserStroker.setCapStyle(Qt.RoundCap)
        eraserStroker.setJoinStyle(Qt.RoundJoin)

        pen = QPen()
        pen.setWidth(1)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)

        for li, l in enumerate(page.layers):
            if li+1 in exclude_layers or l.name in exclude_layers:
                continue
            if (l.highlights
                    and l.name + "/highlights" not in exclude_layers
                    and str(li+1) + "/highlights" not in exclude_layers):
                # then
                h = QGraphicsRectItem(self)
                h.setPen(QPen(Qt.NoPen))
                for hi in l.highlights:
                    for r in hi.get('rects', []):
                        ri = QGraphicsRectItem(r.get('x',0),r.get('y',0),r.get('width',0), r.get('height',0), h)
                        ri.setPen(QPen(Qt.NoPen))
                        ri.setBrush(highlight)
                        ri.setToolTip(hi.get('text',''))
            group = QGraphicsPathItem()
            group.setPen(noPen)
            if eraser_mode >= AUTO_ERASER:
                eraser_mode = AUTO_ERASER_IGNORE

            for k in l.strokes:
                tool = TOOL_ID.get(k.pen)
                # print(TOOL_NAME.get(tool))

                # COLOR
                if tool == HIGHLIGHTER_TOOL:
                    pen.setColor(highlight)
                elif tool == ERASER_TOOL:
                    pen.setColor(Qt.white)
                else:
                    pen.setColor(colors[k.color])

                # WIDTH CALCULATION
                if tool == PENCIL_TOOL:
                    if pencil_resolution:
                        calcwidth = pencil_width
                    else:
                        calcwidth = flat_pencil_width
                elif tool == MECH_PENCIL_TOOL:
                    if pencil_resolution:
                        calcwidth = mech_pencil_width
                    else:
                        calcwidth = flat_mech_pencil_width
                # elif tool == BALLPOINT_TOOL:
                #     calcwidth = very_dynamic_width
                else:
                    calcwidth = dynamic_width

                # AUTO ERASER SETTINGS
                if tool == BRUSH_TOOL or tool == MARKER_TOOL:
                    if eraser_mode == AUTO_ERASER:
                        eraser_mode = AUTO_ERASER_ACCURATE
                elif tool == PENCIL_TOOL:
                    if eraser_mode == AUTO_ERASER:
                        if max(s.width for s in k.segments) > 2:
                            eraser_mode = AUTO_ERASER_ACCURATE

                pen.setWidthF(0)
                path = None

                if k.pen == 8:
                    # ERASE AREA
                    # The remarkable renderer seems to ignore these!
                    pass
                elif k.pen == 6 and eraser_mode % 3 == IGNORE_ERASER:
                    pass
                elif k.pen == 6 and eraser_mode % 3 == ACCURATE_ERASER:
                    # ERASER
                    T1 = time.perf_counter()
                    eraserStroker.setWidth(k.width)
                    area = QPainterPath(QPointF(0,0))
                    area.moveTo(0,0)
                    area.lineTo(0,HEIGHT_PX)
                    area.lineTo(WIDTH_PX,HEIGHT_PX)
                    area.lineTo(WIDTH_PX,0)
                    area.lineTo(0,0)
                    subarea = QPainterPath(QPointF(k.segments[0].x, k.segments[0].y))
                    for s in k.segments[1:]:
                        subarea.lineTo(s.x,s.y)
                    subarea = eraserStroker.createStroke(subarea)
                    logger.debug('A: %f', time.perf_counter() - T1); T1 = time.perf_counter()
                    subarea = subarea.simplified()    # this is expensive
                    logger.debug('B: %f', time.perf_counter() - T1); T1 = time.perf_counter()
                    # area = fullPageClip.subtracted(subarea)    # this alternative is also expensive
                    area.addPath(subarea)
                    group.setFlag(QGraphicsItem.ItemClipsChildrenToShape)
                    group.setPath(area)
                    ### good for testing:
                    # group.setPen(Qt.red)
                    # group.setBrush(QBrush(QColor(255,0,0,50)))
                    newgroup = QGraphicsPathItem()
                    newgroup.setPen(noPen)
                    group.setParentItem(newgroup)
                    group = newgroup
                else:
                    if (simplify > 0 or smoothen) and tool == FINELINER_TOOL:
                        pen.setWidthF(k.width)
                        if simplify > 0:
                            sk = simpl(k, simplify)
                        else:
                            sk = k.segments
                        path = QPainterPath(QPointF(sk[0][0], sk[0][1]))
                        if len(sk) == 2:
                            path.lineTo(sk[1][0],sk[1][1])
                        elif smoothen:
                            px1, px2 = bezierInterpolation(sk, 0)
                            py1, py2 = bezierInterpolation(sk, 1)
                            for i in range(1,len(sk)):
                                path.cubicTo(px1[i-1],py1[i-1],px2[i-1],py2[i-1],sk[i][0],sk[i][1])
                        else:
                            for i in range(1,len(sk)):
                                path.lineTo(sk[i][0],sk[i][1])
                        item=QGraphicsPathItem(path, group)
                        item.setPen(pen)
                    else:
                        # STANDARD
                        path = QPainterPath(QPointF(k.segments[0].x, k.segments[0].y))
                        path.setFillRule(Qt.WindingFill)
                        for (w,p), segments in groupby(k.segments[1:], calcwidth):
                            for s in segments:
                                path.lineTo(s.x,s.y)

                            if pencil_resolution and tool == PENCIL_TOOL and p:
                                # draw fuzzy edges
                                item=QGraphicsPathItem(path, group)
                                pen.setBrush(pencilBrushes().getBrush(int(p*.7), scale=pencil_resolution))
                                pen.setWidthF(w*1.15)
                                item.setPen(pen)

                            pen.setWidthF(w)
                            if p is not None:
                                if pencil_resolution:
                                    pen.setBrush(pencilBrushes().getBrush(p, scale=pencil_resolution))
                                else:
                                    pen.setColor(QColor(int(p*255),int(p*255),int(p*255)))
                            item=QGraphicsPathItem(path, group)
                            item.setPen(pen)
                            path = QPainterPath(path.currentPosition())
                            path.setFillRule(Qt.WindingFill)
                        # END STANDARD

            group.setParentItem(self)
