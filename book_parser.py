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


class SignalPrinter(ChainLink):
    def process(self, s: Signal):
        print(f"{s.name:15} {s.line:5} {s.data}")
                
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
                self.send(Signal("skipped", item.data, item.line))
                

    def tag_init(self, item: SaxItem):
        if item.event == 'start':
            if item.name == 'ParagraphStyleRange':
                match item.data.get('AppliedParagraphStyle'): 
                    case 'ParagraphStyle/Кафедра':
                        self.set_state('header', item)
                    case 'ParagraphStyle/Текст' | 'ParagraphStyle/Текст1':
                        self.set_state('text', item)
                    case 'ParagraphStyle/Таблица Заголовок':
                        self.set_state('episkops-header', item)
                    case 'ParagraphStyle/Таблица' | 'ParagraphStyle/Таблица сжатая':
                        self.set_state('episkop', item)
                    case 'ParagraphStyle/Сноска с лин' | 'ParagraphStyle/Сноска' | 'ParagraphStyle/Footnote text':
                        self.set_state('note', item)

                    case 'ParagraphStyle/КАФЕДРА ОБН.':
                        self.set_state('header_obn', item)                
                    case 'ParagraphStyle/ТЕКСТ ОБН.':
                        self.set_state('text_obn', item)
                    case 'ParagraphStyle/ТАБЛ ОБН' | 'ParagraphStyle/Таблица обн сжатая':
                        self.set_state('episkop_obn', item)
                    case 'ParagraphStyle/СНОСКА с лин. ОБН' | 'ParagraphStyle/сноска обн.':
                        self.set_state('note_obn', item)

                    case 'ParagraphStyle/Normal':
                        self.set_state('text_?', item)
            elif item.name == 'Properties':
                self.set_state('props', item)
        
    
    def tag_ParagraphStyleRange(self, item: SaxItem):        
        if item.event == 'start':
            if item.name == 'CharacterStyleRange':
                if item.data.get('Position') == 'Superscript':
                    st = 'note_num'
                    if self.signal_type in ('note', 'note_obn'):
                        st = 'note_start'                
                    self.set_state(st, item)
                else:
                    self.set_state(self.signal_type, item)        
            elif item.name == 'Properties':        
                self.set_state('props', item)

    def tag_CharacterStyleRange(self, item: SaxItem):        
        if item.event == 'start':            
            if item.name == 'Content':
                self.set_state(self.signal_type, item)
            elif item.name == 'Br':
                self.send(Signal('br', None, item.line))
            elif item.name == 'Properties':
                self.set_state('props', item)

    def tag_Content(self, item: SaxItem):                
        if item.event == 'text':
            self._item_text_skipped = False
            self.send(Signal(self.signal_type, item.data, item.line))
        
    def tag_Properties(self, item: SaxItem):            
        if item.event == 'text':
            self._item_text_skipped = False
            self.send(Signal(self.signal_type, item.data, item.line))
    
    def finish(self):
        pass


if __name__ == '__main__':
    import sys
    #texter = TextBuilder()
    #chain = Chain(XmlSax()).add(CafedraSignaller()).add(CafedraBuilder()).add(texter)
    
    # chain = Chain(XmlSax()).add(CafedraCounter())

    chain = Chain(XmlSax()).add(CafedraSignaller()).add(SignalPrinter())

    filename = 'sample_cafedry.xml'
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    
    f = open(filename, encoding='utf8')
    chain.process(f)

    #print(texter.get_text())
    
