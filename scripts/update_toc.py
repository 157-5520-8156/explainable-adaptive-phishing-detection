"""Update only cached PAGEREF values using the verified rendered PDF page map."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import argparse
import json
import re
from lxml import etree as E
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--pdf',required=True)
parser.add_argument('--docx',required=True);parser.add_argument('--build-dir',default='build');args=parser.parse_args()
reader=PdfReader(args.pdf);texts=[re.sub(r'\s+',' ',p.extract_text()).strip() for p in reader.pages]
start=next(i for i,t in enumerate(texts) if 'Table of Contents' not in t and t.count('Chapter 1. Introduction')>=1)
build=ROOT/args.build_dir
manifest=json.loads((build/'toc_manifest.json').read_text());mapping={}
for item in manifest:
 heading=item['heading'];matches=[i for i in range(start,len(texts)) if heading in texts[i]]
 if not matches:raise ValueError('Missing rendered heading: '+heading)
 mapping[item['bookmark']]=str(matches[0]-start+1)
docx=ROOT/args.docx
with ZipFile(docx) as z:parts={n:z.read(n) for n in z.namelist()}
root=E.fromstring(parts['word/document.xml']);ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
updated=0
for p in root.xpath('.//w:p',namespaces=ns):
 instruction=''.join(p.xpath('./w:r/w:instrText/text()',namespaces=ns))
 match=re.search(r'PAGEREF\s+(h_\d+)',instruction)
 if not match:continue
 name=match.group(1);active=False
 for r in p.findall('w:r',ns):
  field=r.find('w:fldChar',ns)
  if field is not None:
   kind=field.get('{'+ns['w']+'}fldCharType')
   if kind=='separate':active=True
   elif kind=='end':active=False
  elif active:
   for t in r.findall('w:t',ns):t.text=mapping[name];updated+=1
parts['word/document.xml']=E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
with ZipFile(docx,'w',ZIP_DEFLATED) as z:
 for n,b in parts.items():z.writestr(n,b)
(build/'toc_page_map.json').write_text(json.dumps({'body_physical_start':start+1,'updated_fields':updated,'pages':mapping},indent=2))
print('Updated cached page references:',updated)
