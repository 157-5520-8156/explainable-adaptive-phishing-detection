"""Read the creator's DOM pickle as inert data; never call pickle.load or globals."""
import pickletools
from dataclasses import dataclass

@dataclass
class DomRecord:
    kind: str
    state: object = None

ALLOWED_GLOBALS={'htmldom.htmldom HtmlDom','htmldom.htmldom HtmlDomNode'}

def parse_dom_pickle(data,max_operations=12000000):
    stack=[];memo={};mark=object()
    def marked():
        i=len(stack)-1
        while i>=0 and stack[i] is not mark:i-=1
        if i<0:raise ValueError('Missing pickle mark')
        values=stack[i+1:];del stack[i:];return values
    for count,(op,arg,_) in enumerate(pickletools.genops(data)):
        if count>=max_operations:raise ValueError('DOM data operation limit exceeded')
        name=op.name
        if name in {'PROTO','FRAME'}:continue
        if name=='STOP':
            if len(stack)!=1:raise ValueError('Unexpected final data stack')
            return stack[0]
        if name=='MARK':stack.append(mark)
        elif name in {'BINUNICODE','SHORT_BINUNICODE','BINUNICODE8','UNICODE','BINSTRING','SHORT_BINSTRING','BINBYTES','SHORT_BINBYTES','BINBYTES8','BININT','BININT1','BININT2','INT','LONG','LONG1','LONG4','BINFLOAT','FLOAT'}:stack.append(arg)
        elif name=='NONE':stack.append(None)
        elif name=='NEWTRUE':stack.append(True)
        elif name=='NEWFALSE':stack.append(False)
        elif name=='EMPTY_DICT':stack.append({})
        elif name=='EMPTY_LIST':stack.append([])
        elif name=='EMPTY_TUPLE':stack.append(())
        elif name in {'BINPUT','LONG_BINPUT','PUT'}:memo[int(arg)]=stack[-1]
        elif name=='MEMOIZE':memo[len(memo)]=stack[-1]
        elif name in {'BINGET','LONG_BINGET','GET'}:stack.append(memo[int(arg)])
        elif name=='GLOBAL':
            if arg not in ALLOWED_GLOBALS:raise ValueError('Unapproved global in DOM data: '+arg)
            stack.append(('INERT_CLASS',arg))
        elif name=='NEWOBJ':
            args=stack.pop();kind=stack.pop()
            if not isinstance(kind,tuple) or kind[0]!='INERT_CLASS' or args!=():raise ValueError('Unsupported inert object arguments')
            stack.append(DomRecord(kind[1]))
        elif name=='BUILD':
            state=stack.pop()
            if not isinstance(stack[-1],DomRecord) or not isinstance(state,dict):raise ValueError('Unsupported DOM state')
            stack[-1].state=state
        elif name=='TUPLE':stack.append(tuple(marked()))
        elif name in {'TUPLE1','TUPLE2','TUPLE3'}:
            n=int(name[-1]);values=tuple(stack[-n:]);del stack[-n:];stack.append(values)
        elif name=='LIST':stack.append(marked())
        elif name=='DICT':
            values=marked();stack.append(dict(zip(values[::2],values[1::2])))
        elif name=='APPEND':
            value=stack.pop();stack[-1].append(value)
        elif name=='APPENDS':
            values=marked();stack[-1].extend(values)
        elif name=='SETITEM':
            value=stack.pop();key=stack.pop();stack[-1][key]=value
        elif name=='SETITEMS':
            values=marked()
            if len(values)%2:raise ValueError('Odd dictionary state')
            stack[-1].update(zip(values[::2],values[1::2]))
        else:raise ValueError('Unsupported executable or data opcode: '+name)
    raise ValueError('DOM pickle lacks STOP')
