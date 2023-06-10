from xml import sax
from typing import Union, List, Dict
from dataclasses import dataclass
import inspect

from chain import Chain, ChainLink, XmlSax, SaxItem, Printer

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

@dataclass
class Signal:
    name: str
    data: str
    line: str
    
                
class CafedraSignaller(ChainLink):
    def __init__(self):
        self.signal_type = None
        self.cur_tag = 'init'        
        self.tag_level = None
        self._state_stack = []

        self._item_text_skipped = None
       
    def set_state(self, signal_type, item: SaxItem):
        old = self.signal_type, self.cur_tag, self.tag_level
        self._state_stack.append(old)

        st = (signal_type, item.name, item.level)
        self.signal_type, self.cur_tag, self.tag_level = st
        #print("SET", st)

    def pop_state(self):
        st = self._state_stack.pop()
        self.signal_type, self.cur_tag, self.tag_level = st
        #print("POP", st)
        
    def process(self, item: SaxItem):
        if item.event == 'end' and item.level == self.tag_level:
            self.pop_state()
        else:
            self._item_text_skipped = True
            getattr(self, 'tag_' + self.cur_tag)(item)
            if item.event == 'text' and self._item_text_skipped and item.data.strip():
                self.send(Signal("skipped_text", item.data, item.line))
                

    def tag_init(self, item: SaxItem):
        if item.event == 'start' and item.name == 'ParagraphStyleRange':
            if item.data.get('AppliedParagraphStyle') == "ParagraphStyle/Кафедра":
                self.set_state('header', item)
            elif item.data.get('AppliedParagraphStyle') == 'ParagraphStyle/Текст':
                self.set_state('text', item)
    
    def tag_ParagraphStyleRange(self, item: SaxItem):
        if item.event == 'start' and item.name == 'CharacterStyleRange':
            if item.data.get('Position') == 'Superscript':
                self.set_state('note_num', item)
            else:
                self.set_state(self.signal_type, item)
        
    def tag_CharacterStyleRange(self, item: SaxItem):
        if item.event == 'start' and item.name == 'Content':
            self.set_state(self.signal_type, item)
        elif item.event == 'start' and item.name == 'Br':
            self.send(Signal('br', None, item.line))
    

    def tag_Content(self, item: SaxItem):                
        if item.event == 'text':
            self._item_text_skipped = False
            self.send(Signal(self.signal_type, item.data, item.line))
        

    def finish(self):
        ...
        

if __name__ == '__main__':
    import sys
    #texter = TextBuilder()
    #chain = Chain(XmlSax()).add(CafedraSignaller()).add(CafedraBuilder()).add(texter)
    
    #chain = Chain(XmlSax()).add(Printer())

    # chain = Chain(XmlSax()).add(CafedraCounter())

    chain = Chain(XmlSax()).add(CafedraSignaller()).add(Printer())

    filename = 'sample_cafedry.xml'
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    
    f = open(filename, encoding='utf8')
    chain.process(f)

    #print(texter.get_text())
    
