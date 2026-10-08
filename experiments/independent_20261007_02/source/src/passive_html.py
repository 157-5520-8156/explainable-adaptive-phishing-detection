"""Versioned passive page aggregation shared by archived HTML and inert DOM data.

No scripts, links, redirects, DNS or external resources are executed or fetched.
This is a new feature contract, not a renaming of either creator's measurements.
"""
from urllib.parse import urljoin,urlsplit
import hashlib,json,re
from lxml import html as LH
from features import domain_group
from safe_dom_pickle import DomRecord

VERSION='passive_html_v1'
MAX_NODES=250000

def clean_text(text):return re.sub(r'\s+',' ',text or '').strip()

def nodes_from_html(markup):
    if not isinstance(markup,str) or not markup.strip():raise ValueError('Missing archived HTML')
    if len(markup.encode('utf-8'))>25000000:raise ValueError('HTML byte limit exceeded')
    parser=LH.HTMLParser(no_network=True,recover=True,remove_comments=True)
    root=LH.fromstring(markup,parser=parser)
    nodes=[];visible=[]
    for node in root.iter():
        if not isinstance(node.tag,str):continue
        if len(nodes)>=MAX_NODES:raise ValueError('HTML node limit exceeded')
        tag=node.tag.lower();attrs={str(k).lower():str(v) for k,v in node.attrib.items()}
        text=''.join(node.itertext()) if tag in {'title','script'} else ''
        nodes.append({'tag':tag,'attrs':attrs,'text':text})
        parent_tags=[str(p.tag).lower() for p in node.iterancestors() if isinstance(p.tag,str)]
        if tag not in {'script','style','head'} and not set(parent_tags)&{'script','style','head'}:
            if node.text:visible.append(node.text)
        if node.tail and not set(parent_tags)&{'script','style','head'}:visible.append(node.tail)
    return nodes,clean_text(' '.join(visible))

def nodes_from_inert_dom(dom):
    if not isinstance(dom,DomRecord) or dom.kind!='htmldom.htmldom HtmlDom':raise ValueError('Expected inert creator DOM')
    index=dom.state.get('domNodes')
    records=([node for group in index.values() for node in group] if isinstance(index,dict) else dom.state.get('domNodesList'))
    if isinstance(records,list):records=list({id(node):node for node in records}.values())
    if not isinstance(records,list) or len(records)>MAX_NODES:raise ValueError('Invalid DOM node list')
    records=sorted(records,key=lambda n:n.state.get('pos',0))
    def descendants(record):
        pending=[record];seen=set();text=[]
        while pending:
            current=pending.pop()
            if id(current) in seen:raise ValueError('Cyclic child graph')
            seen.add(id(current));s=current.state
            if s.get('nodeType')==3:text.append(str(s.get('text','')))
            else:pending.extend(reversed(s.get('children',[])))
        return ''.join(text)
    nodes=[];visible=[]
    for record in records:
        if not isinstance(record,DomRecord) or not isinstance(record.state,dict):raise ValueError('Invalid inert DOM node')
        s=record.state;tag=str(s.get('nodeName','')).lower()
        if s.get('nodeType')==1:
            attrs=s.get('attributes',{})
            if not isinstance(attrs,dict):raise ValueError('Invalid DOM attributes')
            nodes.append({'tag':tag,'attrs':{str(k).lower():'' if v is None else str(v) for k,v in attrs.items()},
                          'text':descendants(record) if tag in {'title','script'} else ''})
        elif s.get('nodeType')==3:
            ancestors={str(n.state.get('nodeName','')).lower() for n in s.get('ancestorList',[]) if isinstance(n,DomRecord)}
            if not ancestors&{'script','style','head'}:visible.append(str(s.get('text','')))
    return nodes,clean_text(' '.join(visible))

def aggregate_page(url,nodes,visible_text):
    if not nodes:raise ValueError('No archived page elements')
    page_domain=domain_group(url)
    if not page_domain:raise ValueError('Missing page hostname')
    base=next((urljoin(url,n['attrs']['href']) for n in nodes if n['tag']=='base' and n['attrs'].get('href')),url)
    anchors=[n for n in nodes if n['tag']=='a'];forms=[n for n in nodes if n['tag']=='form'];inputs=[n for n in nodes if n['tag']=='input']
    resources=[n for n in nodes if n['attrs'].get('src') or (n['tag']=='link' and 'href' in n['attrs'])]
    scripts=[n for n in nodes if n['tag']=='script'];title=clean_text(next((n['text'] for n in nodes if n['tag']=='title'),''))
    def null(value):return not str(value or '').strip() or str(value).strip().lower().startswith(('#','javascript:'))
    def external(value):
        if null(value) or str(value).lower().startswith(('mailto:','data:','tel:')):return False
        target=urljoin(base,str(value));parsed=urlsplit(target)
        return parsed.scheme.lower() in {'http','https'} and bool(parsed.hostname) and domain_group(target)!=page_domain
    def ratio(items,predicate):return sum(predicate(n) for n in items)/max(len(items),1)
    script_text=clean_text(' '.join(n['text'] for n in scripts)).lower()
    values={
      'html_element_count':len(nodes),'html_anchor_count':len(anchors),'html_resource_count':len(resources),
      'html_form_count':len(forms),'html_input_count':len(inputs),
      'html_password_input_count':sum(n['attrs'].get('type','').lower()=='password' for n in inputs),
      'html_external_anchor_ratio':ratio(anchors,lambda n:external(n['attrs'].get('href'))),
      'html_null_anchor_ratio':ratio(anchors,lambda n:null(n['attrs'].get('href'))),
      'html_external_resource_ratio':ratio(resources,lambda n:external(n['attrs'].get('src',n['attrs'].get('href')))),
      'html_external_form_ratio':ratio(forms,lambda n:external(n['attrs'].get('action'))),
      'html_null_form_ratio':ratio(forms,lambda n:null(n['attrs'].get('action'))),
      'html_iframe_count':sum(n['tag'] in {'iframe','frame'} for n in nodes),
      'html_script_count':len(scripts),'html_inline_script_ratio':ratio(scripts,lambda n:not n['attrs'].get('src')),
      'html_event_attribute_count':sum(sum(k.startswith('on') for k in n['attrs']) for n in nodes),
      'html_email_link_count':sum(n['attrs'].get('href','').lower().startswith('mailto:') for n in anchors),
      'html_meta_refresh_count':sum(n['tag']=='meta' and n['attrs'].get('http-equiv','').lower()=='refresh' for n in nodes),
      'html_base_count':sum(n['tag']=='base' for n in nodes),
      'html_empty_title':int(not title),'html_domain_in_title':int(page_domain.lower() in title.lower()),
      'html_title_length':len(title),'html_visible_text_length':len(visible_text),
      'html_hidden_element_ratio':ratio(nodes,lambda n:'hidden' in n['attrs'] or bool(re.search(r'display\s*:\s*none|visibility\s*:\s*hidden',n['attrs'].get('style',''),re.I))),
      'html_image_count':sum(n['tag']=='img' for n in nodes),
      'html_external_stylesheet_count':sum(n['tag']=='link' and 'stylesheet' in n['attrs'].get('rel','').lower() and external(n['attrs'].get('href')) for n in nodes),
      'html_script_location_count':script_text.count('location'),
      'html_script_window_open_count':script_text.count('window.open'),
      'html_obfuscated_script_count':sum(token in script_text for token in ['eval(','atob(','unescape(']),
    }
    # A source-independent semantic fingerprint for duplicate auditing. Browser
    # rendering and HTML-template similarity beyond exact normalization are not implied.
    signature={'nodes':[(n['tag'],sorted((k,clean_text(v)) for k,v in n['attrs'].items()),clean_text(n['text'])) for n in nodes],
               'visible_text':clean_text(visible_text)}
    digest=hashlib.sha256(json.dumps(signature,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    return values,digest

def extract_html_features(url,markup):return aggregate_page(url,*nodes_from_html(markup))
def extract_inert_dom_features(url,dom):return aggregate_page(url,*nodes_from_inert_dom(dom))
