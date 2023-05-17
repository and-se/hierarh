from xml import sax
from typing import Union, List, Dict
from dataclasses import dataclass
import inspect

class Chain:
    def __init__(self, first: 'ChainLink'):
        self.links = [first]

    def add(self, chain_link: 'ChainLink'):
        if inspect.isclass(chain_link):            
            raise ValueError('May be you forgot emtpy brackets () after class name')
            
        self.links[-1].set_next(chain_link)
        self.links.append(chain_link)
        return self

    def process(self, data):
        first = self.links[0]
        first.process(data)

        for l in self.links:
            l.finish()
        

class ChainLink:
    """
    process data item from previous chain link
    """
    def process(self, data) -> None:
        raise NotImplementedError()

    """
    do work on finish chain processing
    """
    def finish(self) -> None: pass

    def set_next(self, link: 'ChainLink'):
        self.next_ = link

    def get_next(self) -> 'ChainLink':
        r = getattr(self, 'next_')
        if not r:
            raise Exception('no next chain link')
        return r

    def send(self, data):
        self.get_next().process(data)

@dataclass
class SaxItem:
    event: str  # start, text, end
    name: str
    data: Union[dict, str]  # dict for start dat attrs, str for text
    level: int
    

class XmlSax(ChainLink, sax.ContentHandler):
    def __init__(self, ignore_whitespace_text = True):
        self.no_white_text = ignore_whitespace_text
        
    def process(self, xml):
        if isinstance(xml, str):
            sax.parseString(xml, self)
        else:
            sax.parse(xml, self)

    def startDocument(self):
        self.level = 0

    def startElement(self, name, attrs):
        self.send(SaxItem('start', name, dict(attrs.copy()), self.level))
        self.level += 1

    def characters(self, text):
        if self.no_white_text==False or text.strip() != '':
            self.send(SaxItem('text', None, text, self.level))

    def endElement(self, name):
        self.level -= 1
        self.send(SaxItem('end', name, None, self.level))
        

class CafedraCounter(ChainLink):
    def __init__(self):
        self.counts = {}
    
    def process(self, item: SaxItem):
        if item.event == 'start' \
           and item.name == 'ParagraphStyleRange' \
           and 'кафедра' in (k:=item.data.get('AppliedParagraphStyle').lower()):
                if k not in self.counts:
                    self.counts[k] = 1
                else:
                    self.counts[k] += 1

    def finish(self):
        print(self.counts)
                
            
        
class Printer(ChainLink):
    def process(self, data):
        print(data)
    

if __name__ == '__main__':
    import sys
    #texter = TextBuilder()
    #chain = Chain(XmlSax()).add(CafedraSignaller()).add(CafedraBuilder()).add(texter)
    
    #chain = Chain(XmlSax()).add(Printer())

    chain = Chain(XmlSax()).add(CafedraCounter())

    filename = 'sample_cafedry.xml'
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    
    f = open(filename, encoding='utf8')
    chain.process(f)

    #print(texter.get_text())
    
