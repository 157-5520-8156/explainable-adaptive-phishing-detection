"""Hand-worked HTML fixtures verify shared passive feature meanings, not performance."""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))

class PassiveHtmlTest(unittest.TestCase):
    def test_link_and_form_ratios_use_domains_and_skip_null_targets(self):
        from passive_html import extract_html_features
        html='<html><head><title>Example</title></head><body><a href="/a">A</a><a href="https://other.test/">B</a><a href="#">C</a><form action="https://other.test/go"><input type="password"></form></body></html>'
        values,digest=extract_html_features('https://example.test/',html)
        self.assertEqual(values['html_anchor_count'],3)
        self.assertEqual(values['html_external_anchor_ratio'],1/3)
        self.assertEqual(values['html_null_anchor_ratio'],1/3)
        self.assertEqual(values['html_external_form_ratio'],1)
        self.assertEqual(values['html_password_input_count'],1)
        self.assertEqual(len(digest),64)

    def test_html_and_inert_dom_adapters_share_feature_meanings(self):
        from passive_html import extract_html_features,extract_inert_dom_features
        from safe_dom_pickle import DomRecord
        nodes=[]
        for pos,(tag,kind,text) in enumerate([('html',1,''),('head',1,''),('title',1,''),('text',3,'Example'),('body',1,''),('a',1,''),('text',3,'Hello')],1):
            nodes.append(DomRecord('htmldom.htmldom HtmlDomNode',{'nodeName':tag,'nodeType':kind,'text':text,'pos':pos,'attributes':{},'children':[],'ancestorList':[]}))
        root,head,title,titletext,body,anchor,anchortext=nodes
        root.state['children']=[head,body];head.state['children']=[title];title.state['children']=[titletext];body.state['children']=[anchor];anchor.state['children']=[anchortext]
        anchor.state['attributes']={'href':'/a'};titletext.state['ancestorList']=[root,head,title];anchortext.state['ancestorList']=[root,body,anchor]
        dom=DomRecord('htmldom.htmldom HtmlDom',{'domNodesList':nodes})
        literal='<html><head><title>Example</title></head><body><a href="/a">Hello</a></body></html>'
        self.assertEqual(extract_html_features('https://example.test/',literal),extract_inert_dom_features('https://example.test/',dom))
