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

DOCUMENT =  NOTEBOOK | PDF | EPUB
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
PDF_BASE_CONTENT  = {
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

WIDTH_MM = 206
HEIGHT_MM = 154.5
