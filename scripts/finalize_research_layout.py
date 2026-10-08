"""Apply template layout while preserving every authentic Cite tag and text."""
from pathlib import Path
from zipfile import ZipFile
import json
import re
import shutil
from lxml import etree as E

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'thesis/Phishing_Detection_Mendeley_Draft.docx'
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W = '{' + NS['w'] + '}'
with ZipFile(path) as z:
    entries = [(i, z.read(i.filename)) for i in z.infolist()]
parts = {i.filename: data for i, data in entries}
root = E.fromstring(parts['word/document.xml'])
styles = E.fromstring(parts['word/styles.xml'])
tags_before = root.xpath('.//w:sdtPr/w:tag/@w:val', namespaces=NS)
citation_text_before = [s.xpath('.//w:t/text()', namespaces=NS) for s in root.findall('.//w:sdt', NS)[:-1]]
shutil.copy2(path, ROOT / 'build/redesign_20261007/before_final_layout.docx')

def child(parent, name, attrs):
    node = parent.find(W + name)
    if node is None:
        node = E.SubElement(parent, W + name)
    node.attrib.clear()
    node.attrib.update({W + k: str(v) for k, v in attrs.items()})
    return node

def fonts(run, size):
    pr = run.find(W + 'rPr')
    if pr is None:
        pr = E.Element(W + 'rPr')
        run.insert(0, pr)
    child(pr, 'rFonts', {'ascii': 'Arial', 'hAnsi': 'Arial', 'cs': 'Arial'})
    child(pr, 'sz', {'val': size})
    child(pr, 'szCs', {'val': size})
    child(pr, 'color', {'val': '000000'})
    child(pr, 'lang', {'val': 'en-US'})

spacing_changes = 0
for sdt in root.findall('.//w:sdt', NS):
    tag = sdt.find('w:sdtPr/w:tag', NS)
    if tag is None or not tag.get(W + 'val', '').startswith('MENDELEY_CITATION_v3_'):
        continue
    following = sdt.getnext()
    if following is not None and following.tag == W + 'r':
        texts = following.findall(W + 't')
        if texts:
            text = texts[0].text or ''
            if re.match(r'^\s+[.,;:!?]', text) or text.isspace():
                texts[0].text = text.lstrip()
                spacing_changes += 1
    size = 20 if any(p.tag == W + 'tbl' for p in sdt.iterancestors()) else 22
    for run in sdt.findall('.//w:r', NS):
        fonts(run, size)

for style in styles.findall(W + 'style'):
    name = style.find(W + 'name').get(W + 'val', '').lower()
    if name not in {'toc 1', 'toc 2', 'toc 3'}:
        continue
    level = int(name[-1])
    pr = style.find(W + 'pPr')
    if pr is None:
        pr = E.SubElement(style, W + 'pPr')
    child(pr, 'spacing', {'before': 0, 'after': 0, 'line': 360, 'lineRule': 'auto'})
    child(pr, 'ind', {'left': (level - 1) * 240, 'firstLine': 0})
    child(pr, 'jc', {'val': 'left'})

toc_count = 0
for paragraph in root.findall('.//w:p', NS):
    style = paragraph.find('w:pPr/w:pStyle', NS)
    if style is None or style.get(W + 'val') not in {'TOC1', 'TOC2', 'TOC3'}:
        continue
    level = int(style.get(W + 'val')[-1])
    pr = paragraph.find(W + 'pPr')
    child(pr, 'spacing', {'before': 0, 'after': 0, 'line': 360, 'lineRule': 'auto'})
    child(pr, 'ind', {'left': (level - 1) * 240, 'firstLine': 0})
    child(pr, 'jc', {'val': 'left'})
    for run in paragraph.findall('.//w:r', NS):
        fonts(run, 22)
    toc_count += 1

bib = root.xpath('.//w:sdt[w:sdtPr/w:tag[@w:val="MENDELEY_BIBLIOGRAPHY"]]', namespaces=NS)
assert len(bib) == 1
bib_count = 0
for paragraph in bib[0].findall('.//w:p', NS):
    text = ''.join(paragraph.xpath('.//w:t/text()', namespaces=NS))
    if not re.match(r'^\[\d+\]', text):
        continue
    pr = paragraph.find(W + 'pPr')
    if pr is None:
        pr = E.Element(W + 'pPr')
        paragraph.insert(0, pr)
    child(pr, 'keepLines', {})
    child(pr, 'spacing', {'before': 0, 'after': 120, 'line': 360, 'lineRule': 'auto'})
    # Two-digit IEEE labels need a tab wider than their 11-point text.
    child(pr, 'ind', {'left': 540, 'hanging': 540})
    child(pr, 'jc', {'val': 'left'})
    tabs = child(pr, 'tabs', {})
    for item in list(tabs):
        tabs.remove(item)
    E.SubElement(tabs, W + 'tab', {W + 'val': 'left', W + 'pos': '540'})
    for run in paragraph.findall('.//w:r', NS):
        fonts(run, 22)
    bib_count += 1

assert tags_before == root.xpath('.//w:sdtPr/w:tag/@w:val', namespaces=NS)
assert citation_text_before == [s.xpath('.//w:t/text()', namespaces=NS) for s in root.findall('.//w:sdt', NS)[:-1]]
assert bib_count == 18 and toc_count == 48
parts['word/document.xml'] = E.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
parts['word/styles.xml'] = E.tostring(styles, xml_declaration=True, encoding='UTF-8', standalone=True)
with ZipFile(path, 'w') as z:
    for info, original in entries:
        z.writestr(info, parts.get(info.filename, original))
audit = {'citation_tags_preserved': 33, 'bibliography_tag_preserved': 1,
         'citation_display_text_preserved': True, 'spacing_changes_outside_citation_controls': spacing_changes,
         'template_toc_rows': toc_count, 'template_bibliography_entries': bib_count}
(ROOT / 'docs/research_mendeley_layout_audit.json').write_text(json.dumps(audit, indent=2) + '\n')
print(json.dumps(audit))
