from xml import sax
from typing import Union, List, Dict
from dataclasses import dataclass
import inspect


"""
Chain of data processing steps
"""
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
        


"""
Data processing step for Chain.
"""
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
        r = getattr(self, 'next_', None)
        # if not r:
        #    raise Exception('no next chain link')
        return r

    """
    sends data to next chain link
    """
    def send(self, data):        
        n = self.get_next()
        if n:
            n.process(data)

@dataclass
class SaxItem:
    event: str  # start, text, end
    name: str  # tag ...
    data: Union[dict, str]  # dict for start event attrs, str for text event
    level: int  # tag level (0 = root)
    line: int  # input data line number, which produced this SaxItem
    

"""
Chain link to process XML as SAX events
"""
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

    def setDocumentLocator(self, locator):
        self._loc = locator

    def line(self):
        return self._loc.getLineNumber()

    def startElement(self, name, attrs):
        self.send(
            SaxItem('start', name, dict(attrs.copy()), self.level, self.line())
        )
        self.level += 1

    def characters(self, text):
        if self.no_white_text==False or text.strip() != '':
            self.send(SaxItem('text', None, text, self.level, self.line()))

    def endElement(self, name):
        self.level -= 1
        self.send(SaxItem('end', name, None, self.level, self.line()))
        

"""
Debug chain step for printing all data
"""
class Printer(ChainLink):
    def process(self, data):
        print(data)
    

if __name__ == '__main__':
    chain = Chain(XmlSax()).add(Printer())

    xml = """
    <root attr="it is test">
      <!-- comment ignored -->
      <item>test of Chain XmlSax</item>
    </root>
    """   
    
    chain.process(xml)
