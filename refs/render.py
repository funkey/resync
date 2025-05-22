import requests


def render_document(document):
    """Render a document into a PDF."""
    response = requests.get(f"http://10.11.99.1/download/{document.uid}/pdf")
    return response.content
