#!/usr/bin/env python3
"""Create a small original offline OOXML fixture, no macros or external links."""
from pathlib import Path
import sys
from zipfile import ZipFile, ZIP_DEFLATED
from xml.sax.saxutils import escape


def build(path: Path):
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    texts = ["Localzet OS — Offline document review",
             "This is an original local test document. No account or network is needed.",
             "Executive desktop compatibility · Native document editing",
             "The editor must render this page, not merely create a window."]
    paragraphs = []
    for i, line in enumerate(texts):
        color = "205EA8" if i == 0 else "263950"
        size = 44 if i == 0 else 26
        paragraphs.append(f'<w:p><w:r><w:rPr><w:color w:val="{color}"/><w:sz w:val="{size}"/></w:rPr><w:t>{escape(line)}</w:t></w:r></w:p>')
    content = f'<w:document xmlns:w="{ns}"><w:body>{"".join(paragraphs)}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body></w:document>'
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        archive.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        archive.writestr("word/document.xml", content)


if __name__ == "__main__":
    build(Path(sys.argv[1]))
