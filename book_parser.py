from xml import sax
from typing import Union, List, Dict
from dataclasses import dataclass
import inspect
import re

from chain import Chain, ChainLink, XmlSax, SaxItem, Printer

@dataclass
class Signal:
    name: str
    data: str
    line: str


class SignalPrinter(ChainLink):
    def process(self, s: Signal):
        print(f"{s.name:15} {s.line:5} {s.data}")
        self.send(s)


class SignalCounter(ChainLink):
    def __init__(self):
        self.counts = {}

    def process(self, s: Signal):
        if s.name not in self.counts:
            self.counts[s.name] = 1
        else:
            self.counts[s.name] += 1
        self.send(s)

    def finish(self):
        print(self.counts)


class CafedraSignaller(ChainLink):
    """
    Reads book xml and generates signals as objects of type Signal with filed 'name':
    * header - заголовок статьи о кафедре
    * text - текст статьи о кафедре
    * episkop - строка таблицы епископов, содержит сведения об управлении кафедрой епископом в конкретный период
    * episkops-header - подзаголовок внутри таблицы епископов. Примеры: В Смоленске; Архиепископы и митрополиты Московские;    
    * note_num - номер сноски при ссылке из текста
    * note_start - номер сноски в начале текста сноски
    * note - текст сноски

    * header_obn, text_obn, episkop_obn, note_obn - то же для раскольничьих кафедр
    * text_? - текст статьи о кафедре (настоящей или раскольничьей - надо разбираться из контекста).

    * props - техническая информация о шрифтах и прочем, которую можно игнрорировать
    * skipped - куски текста, не отнесённые ни к одному из предыдущих типов (таких быть не должно)
    
    """
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


class SkippedTextCatcher(ChainLink):
    def __init__(self, fail_on_skipped = True):
        self.fail_on_skipped = fail_on_skipped

    def process(self, s: Signal):
        if s.name == 'skipped':
            if self.fail_on_skipped:
                raise ValueError('Skipped text detected: ' + str(s))
            else:
                print('!!!! SKIPPED', s)
        self.send(s)


def replace_u2028(s):
    """
    replaces \\u2028 (UNICODE LINE SEPARATOR) with space or nothing.
    \\u2028 not recognized by text editors and browser as \n
    """
    res = []
    for i in range(len(s)):
        if s[i] == '\u2028':
            if i-1 > 0 and s[i-1] == '-':
                continue  # replace with nothing in Бобрикович-Копоть-\u2028\t\t\t\t\t\tАнехожский
            else:
                res.append(' ')  # replace with space
        else:
            res.append(s[i])
    return ''.join(res)


class TextCleaner(ChainLink):
    def process(self, sig: Signal):
        if sig.data and '\u2028' in sig.data:
            # print("!!!!!", sig)
            sig.data = replace_u2028(sig.data)

        self.send(sig)


class CafedraNameBuilder(ChainLink):
    def __init__(self):
        self._cur_name = None
        self._start_signal = None

    def process(self, s: Signal):
        is_header = s.name.startswith('header')
                
        if self.has_name() and is_header:
            self.append_name(s)            
        elif self.has_name() and not is_header:
            self.send_name()
        elif not self.has_name() and is_header:
            self.start_name(s)
            
    def finish(self):
        if self._cur_name:
            self.send_name()

    def has_name(self):
        return bool(self._cur_name)

    def start_name(self, s: Signal):
        self._cur_name = s.data
        self._start_signal = s

    def append_name(self, s: Signal):
        assert s.name == self._start_signal.name
        self._cur_name += s.data

    def send_name(self):
        if self._start_signal.name == 'header':
            sname = 'name'
        elif self._start_signal.name == 'header_obn':
            sname = 'name_obn'
        else:
            raise ValueError('expected header or header_obn signal')
        
        is_link = '(см.' in self._cur_name
        if is_link:
            sname += '_link'
        
        self.send(Signal(sname, self._cur_name, self._start_signal.line))
        self._cur_name = None
        self._start_signal = None



if __name__ == '__main__':
    import sys
    #texter = TextBuilder()
    #chain = Chain(XmlSax()).add(CafedraSignaller()).add(CafedraBuilder()).add(texter)
    
    chain = Chain(XmlSax()).add(CafedraSignaller())\
                .add(SkippedTextCatcher()).add(TextCleaner())
    
    chain.add(CafedraNameBuilder())

    chain.add(SignalPrinter())
    chain.add(SignalCounter())
    
    filename = 'sample_cafedry.xml'
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    
    f = open(filename, encoding='utf8')
    chain.process(f)

    #print(texter.get_text())
    
