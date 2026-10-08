"""Convert authored LaTeX into editable Word math using MathML and Microsoft's XSLT."""
from pathlib import Path
import hashlib,json,sys
from lxml import etree as E

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,'/tmp/finalproject-latex-authoring')
from latex2mathml.converter import convert

EQUATIONS={
 '3-1':r'p(y=1\,\vert\,\mathbf{x})=\frac{1}{1+\exp[-(\mathbf{w}^{\mathsf{T}}\mathbf{x}+b)]}',
 '3-2':r'\widehat{p}_{\mathrm{RF}}(y=1\,\vert\,\mathbf{x})=\frac{1}{B}\sum_{b=1}^{B}\widehat{p}_{b}(y=1\,\vert\,\mathbf{x})',
 '3-3':r'P=\frac{TP}{TP+FP},\quad R=\frac{TP}{TP+FN},\quad F_1=\frac{2PR}{P+R},\quad\mathrm{FPR}=\frac{FP}{FP+TN}',
 '3-4':r'\mathrm{AP}=\sum_{k=1}^{K}(R_k-R_{k-1})P_k',
 '3-5':r'f(\mathbf{x})=\phi_0+\sum_{j=1}^{M}\phi_j(\mathbf{x})',
 '3-6':r'\phi_j=\sum_{S\subseteq F\setminus\{j\}}\frac{|S|!(M-|S|-1)!}{M!}\left[v(S\cup\{j\})-v(S)\right]',
 '3-7':r'e_i=\mathbb{1}\!\left[\widehat{y}_i\ne y_i\right],\qquad a_i=b(i)+d',
 '3-8':r'\left|\widehat{\mu}_{W_0}-\widehat{\mu}_{W_1}\right|>\epsilon_t',
}
out=ROOT/'thesis/equations';out.mkdir(exist_ok=True)
transform_path=Path('/Applications/Microsoft Word.app/Contents/Resources/mathml2omml.xsl')
transform=E.XSLT(E.parse(str(transform_path)))
records=[]
for number,latex in EQUATIONS.items():
    (out/f'eq_{number}.tex').write_text(latex+'\n')
    mathml=convert(latex,display='block')
    (out/f'eq_{number}.mathml').write_text(mathml)
    tree=E.fromstring(mathml.encode());mml={'x':'http://www.w3.org/1998/Math/MathML'}
    # latex2mathml leaves the MathML mover accent implicit; Office's XSLT
    # requires it explicitly to produce an accent rather than an upper limit.
    for mover in tree.xpath('.//x:mover',namespaces=mml):
        if len(mover)==2 and ''.join(mover[1].itertext())=='^':mover.set('accent','true')
    result=transform(tree)
    ns={'m':'http://schemas.openxmlformats.org/officeDocument/2006/math'};mn='{'+ns['m']+'}'
    # Office may encode an infix operator as a delimiter separator. LibreOffice
    # drops custom separators such as != on render. Materialise the same operator
    # between arguments, preserving the fenced expression's mathematical meaning.
    for delim in result.xpath('//m:d',namespaces=ns):
        elements=delim.findall(mn+'e');separator=delim.find(mn+'dPr/'+mn+'sepChr')
        if len(elements)>1 and separator is not None:
            token=separator.get(mn+'val','|');first=elements[0]
            for other in elements[1:]:
                run=E.SubElement(first,mn+'r');E.SubElement(run,mn+'t').text=token
                for child in list(other):first.append(child)
                delim.remove(other)
            separator.set(mn+'val','|')
    xml=E.tostring(result,xml_declaration=True,encoding='UTF-8',pretty_print=True)
    (out/f'eq_{number}.omml').write_bytes(xml)
    records.append({'number':number,'latex':latex,'source_sha256':hashlib.sha256(latex.encode()).hexdigest(),'omml_sha256':hashlib.sha256(xml).hexdigest()})
(out/'manifest.json').write_text(json.dumps({'conversion':'latex2mathml 3.81.1; explicit hat-accent MathML; Microsoft Word mathml2omml.xsl; equivalent explicit infix separators for rendering portability','xslt_sha256':hashlib.sha256(transform_path.read_bytes()).hexdigest(),'equations':records},indent=2))
print('Converted',len(records),'LaTeX equations to editable OMML')
