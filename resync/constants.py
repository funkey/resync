FOLDER_TYPE = "CollectionType"
DOCUMENT_TYPE = "DocumentType"

NOTEBOOK = 1
PDF = 2
EPUB = 4
FOLDER = 8
DELETED_NOTEBOOK = NOTEBOOK << 4
DELETED_PDF = PDF << 4
DELETED_EPUB = EPUB << 4
DELETED_FOLDER = FOLDER << 4

NOTEBOOK = NOTEBOOK | DELETED_NOTEBOOK
PDF = PDF | DELETED_PDF
EPUB = EPUB | DELETED_EPUB
FOLDER = FOLDER | DELETED_FOLDER

DOCUMENT = NOTEBOOK | PDF | EPUB
DELETED = (DOCUMENT | FOLDER) << 4
NOT_DELETED = DELETED >> 4
NOTHING = 0
ANYTHING = 0xff

ROOT_ID = ''
TRASH_ID = 'trash'

PDF_BASE_METADATA = {
    "deleted": False,
    "metadatamodified": True,
    "modified": True,
    "parent": "",
    "pinned": False,
    "synced": False,
    "type": "DocumentType",
    "version": 0,
}
PDF_BASE_CONTENT = {
    "dummyDocument": False,
    "extraMetadata": {},
    "fileType": "pdf",
    "fontName": "",
    "lastOpenedPage": 0,
    "legacyEpub": False,
    "lineHeight": -1,
    "margins": 100,
    "orientation": "portrait",
    "pageCount": 0,
    "textAlignment": "left",
    "textScale": 1,
    "transform": {
      "m11": 1, "m12": 0, "m13": 0,
      "m21": 0, "m22": 1, "m23": 0,
      "m31": 0, "m32": 0, "m33": 1
    }
}
FOLDER_BASE_METADATA = {
    'deleted': False,
    'metadatamodified': True,
    'modified': True,
    'parent': '',
    'pinned': False,
    'synced': False,
    'type': 'CollectionType',
    'version': 1
}
FOLDER_BASE_CONTENT = {}

WIDTH_PX = 1404
HEIGHT_PX = 1872
WIDTH_MM = 206
HEIGHT_MM = 154.5
WIDTH_PT = 583.937
HEIGHT_PT = 437.953

# normalised ids
BRUSH_TOOL = 12
MECH_PENCIL_TOOL = 13
PENCIL_TOOL = 14
BALLPOINT_TOOL = 15
MARKER_TOOL = 16
FINELINER_TOOL = 17
HIGHLIGHTER_TOOL = 18
ERASER_TOOL = 6
ERASE_AREA_TOOL = 8
CALLIGRAPHY_TOOL = 21
UNKNOWN_TOOL = None

TOOL_ID = {
   0: BRUSH_TOOL,
   1: PENCIL_TOOL,
   2: BALLPOINT_TOOL,
   3: MARKER_TOOL,
   4: FINELINER_TOOL,
   5: HIGHLIGHTER_TOOL,
   6: ERASER_TOOL,
   7: MECH_PENCIL_TOOL,
   8: ERASE_AREA_TOOL,
   9: CALLIGRAPHY_TOOL,  # guesswork
   12: BRUSH_TOOL,
   13: MECH_PENCIL_TOOL,
   14: PENCIL_TOOL,
   15: BALLPOINT_TOOL,
   16: MARKER_TOOL,
   17: FINELINER_TOOL,
   18: HIGHLIGHTER_TOOL,
   19: ERASER_TOOL,
   21: CALLIGRAPHY_TOOL,
}
