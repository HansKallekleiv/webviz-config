from pathlib import Path
import dash_html_components as html
from ..webviz_assets import webviz_assets


class PdfViewer:
    '''### Pdf file

This container adds a Pdf viewer

* `pdf_file`: Path to the pdf you want to add. Either absolute path or
  relative to the configuration file.
'''

    def __init__(self, pdf_file: Path):
        self.pdf_url = webviz_assets.add(pdf_file)

    @property
    def layout(self):
        return html.Embed(width='100%', style={'height':'100vw'},
                          src=self.pdf_url)
