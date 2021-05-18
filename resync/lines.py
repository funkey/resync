from collections import namedtuple
from io import BytesIO
import logging
import os
import struct

logger = logging.getLogger(__name__)

Layer = namedtuple(
    'Layer',
    ['strokes', 'name', 'highlights']
)

Stroke = namedtuple(
  'Stroke',
  ['pen', 'color', 'unk1', 'width', 'unk2', 'segments']
)

Segment = namedtuple(
  'Segment',
  ['x', 'y', 'speed', 'direction', 'width', 'pressure']
)

HEADER_START = b'reMarkable .lines file, version='
S_HEADER_PAGE = struct.Struct('<{}ss10s'.format(len(HEADER_START)))
S_PAGE = struct.Struct('<BBH')
S_LAYER = struct.Struct('<I')
S_STROKE_V3 = struct.Struct('<IIIfI')
S_STROKE_V5 = struct.Struct('<IIIfII')
S_SEGMENT = struct.Struct('<ffffff')


class UnsupportedVersion(Exception):
    pass


class InvalidFormat(Exception):
    pass


def read_lines_document(fs, doc_uid, page_uid):

    logger.debug("reading page %s from document %s...", page_uid, doc_uid)

    try:
        content = fs.read_file(
            os.path.join(doc_uid, page_uid + '.rm'),
            binary=True)
    except FileNotFoundError:
        content = None

    return Lines(content)


def read_struct(fmt, source):

    buff = source.read(fmt.size)
    return fmt.unpack(buff)


def read_stroke_v3(source):

    pen, color, unk1, width, n_segments = read_struct(S_STROKE_V3, source)
    return (pen, color, unk1, width, 0, n_segments)


def read_stroke_v5(source):
    return read_struct(S_STROKE_V5, source)


class Lines:

    def __init__(self, content):

        if content is None:
            self.version = 5
            self.layers = []
            return

        try:
            source = BytesIO(content)
            logger.debug("Reading lines...")
            self.version, self.layers = self._read_from(source)
            logger.debug("...done.")
        except struct.error:
            raise InvalidFormat()

    def _read_from(self, source):

        header, version, *_ = read_struct(S_HEADER_PAGE, source)

        if not header.startswith(HEADER_START):
            raise InvalidFormat(f"Invalid header: {header}")

        version = int(version)
        if version == 3:
            read_stroke_fn = read_stroke_v3
        elif version == 5:
            read_stroke_fn = read_stroke_v5
        else:
            raise UnsupportedVersion(
                f"Enountered invalid version {version}, only 3 or 5 are "
                "supported")

        num_layers, _, _ = read_struct(S_PAGE, source)
        layers = []

        for _ in range(num_layers):

            layer = self._read_layer(source, read_stroke_fn)
            layers.append(layer)

        return (version, layers)

    def _read_layer(self, source, read_stroke_fn):

        num_strokes, = read_struct(S_LAYER, source)
        strokes = []

        for _ in range(num_strokes):

            stroke = self._read_stroke(source, read_stroke_fn)
            strokes.append(stroke)

        return Layer(strokes, 'unnamed', [])

    def _read_stroke(self, source, read_stroke_fn):

        pen, color, unk1, width, unk2, num_segments = read_stroke_fn(source)
        segments = []

        for _ in range(num_segments):

            segment = self._read_segment(source)
            segments.append(segment)

        return Stroke(pen, color, unk1, width, unk2, segments)

    def _read_segment(self, source):

        x, y, speed, direction, width, pressure = read_struct(
            S_SEGMENT,
            source)
        return Segment(x, y, speed, direction, width, pressure)
