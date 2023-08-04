from xml import sax
from typing import Union, List, Dict
from dataclasses import dataclass
import inspect
import re

from chain import Chain, ChainLink, XmlSax, SaxItem, Printer
from state_machine import StateMachine, State, WrongSignalException

@dataclass
class Signal:
    name: str
    data: str
    line: str

    def serialize(self):
        return f"{self.name:15} {self.line:5} {self.data if self.data else '##NONE##'}"

    @staticmethod
    def deserialize(s):
        name, line_num, data = s.split(maxsplit=2)
        data = data if data != '##NONE##' else None             
        return Signal(name, data, int(line_num))


class SignalPrinter(ChainLink):
    def process(self, s: Signal):
        print(s.serialize())
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
    * episkops_header - подзаголовок внутри таблицы епископов. Примеры: В Смоленске; Архиепископы и митрополиты Московские;    
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
                        self.set_state('episkops_header', item)
                    case 'ParagraphStyle/Таблица' | 'ParagraphStyle/Таблица сжатая':
                        if item.data.get('Justification') == 'CenterAlign':
                            self.set_state('episkops_header', item)
                        else:
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


class SignalTool(ChainLink):
    def __init__(self, cur_name, prev_name=None, prev_prev_name=None):
        prev_name = prev_name if prev_name else cur_name        
        self.prefix1 = cur_name
        self.prefix2 = prev_name
        self.prefix3 = prev_prev_name
        self._prev = None
        self._prev_prev = None
        
    def process(self, s: Signal):
        cond1 = s.name.startswith(self.prefix1) and self._prev and self._prev.name.startswith(self.prefix2)        
        if self.prefix3:
            if cond1 and self._prev_prev and self._prev_prev.name.startswith(self.prefix3):
                self.send(Signal('tool', (self._prev_prev, self._prev, s), s.line))
        elif cond1:
            self.send(Signal('tool', (self._prev, s), s.line))
            
        self._prev_prev = self._prev
        self._prev = s


class SignalNamePatcher(ChainLink):
    def __init__(self, patches: Dict[int, tuple]):
        """
        patches - dict with key = signal line field,
        value = tuple (signal data for check, new signal name)
        """
        self.patches = patches
        
    def process(self, s: Signal):
        patch = self.patches.get(s.line)
        if patch:
            expected_data, new_signal_name = patch
            if new_signal_name == 'SKIP!':
                return
            if not (s.data == expected_data or s.data.strip().startswith(expected_data.strip())):
                raise Exception(f"Signal and patch different: expected '{expected_data}' for signal {s}")
            s.name = new_signal_name
        
        self.send(s)

cafedra_signals_patch = open('signal_patch.txt', encoding='utf8').read()

def parse_text_patch(text_patch):
    res = {}
    for l in text_patch.split('\n'):
        l = l.strip()
        if not l or l.startswith('#'):
            continue

        s = Signal.deserialize(l)
        res[s.line] = (s.data, s.name)
        #new_type, line_num, expected_data = l.split(maxsplit=2)
        #res[int(line_num)] = (expected_data, new_type)

    return res


        
@dataclass
class CafedraArticle:
    header: str
    text: str
    episkops: List[str]

class CafedraArticleBuilder(ChainLink):
    # При составлении правил надо иметь ввиду, что пока мы находимся в рамках одного состояния
    # сигналы складируются в self.state_data с целью сбора итогового текста при выходе из состояния.
    states = [
        State('expect_header', cycle=[], next_state=['header', 'header_obn']),
        
        State('header', cycle='header', next_state = ['text', ('br', 'text')]),        
        State('text', cycle=['text', 'br', 'note_num'], next_state=['episkop', 'episkops_header', 'header', 'header_obn', 'note_start']),
        State('episkop', cycle=['episkop', 'note_num'], next_state=[
            ('br', 'expect_ep_note_head'), 'note_start', 'header', 'header_obn'
        ]),
        State('expect_ep_note_head', cycle='br', next_state=['episkop', 'episkops_header', 'note_start', 'header', 'header_obn']),
        
        State('episkops_header', cycle=['episkops_header', 'note_num'], next_state=['episkop', ('br', 'expect_episkop')]),
        State('expect_episkop', cycle='br', next_state='episkop'),

        State('note_start', cycle = [], next_state='note'),
        State('note', cycle=['note', 'br'], next_state=['note_start', 'header', 'header_obn']),

        # раскольничьи кафедры - в общем-то копия, но для надёжности обрабатываем их отдельно
        State('header_obn', cycle=['header_obn'], next_state = ['text_obn', ('br', 'text_obn')]),        
        State('text_obn', cycle=['text_obn', 'br', 'note_num'], next_state=['episkop_obn', 'header', 'header_obn']),
        State('episkop_obn', cycle=['episkop_obn', 'note_num'], next_state=[
            ('br', 'expect_ep_obn_note_head'), ('note_start', 'note_start_obn'), 'header', 'header_obn'
        ]),
        State('expect_ep_obn_note_head', cycle='br', next_state=['episkop_obn', ('note_start', 'note_start_obn'), 'header', 'header_obn']),
        State('note_start_obn', cycle=[], next_state=['note_obn', ('note', 'note_obn')]),
        State('note_obn', cycle=['note_obn', 'note', 'br'], next_state=[('note_start', 'note_start_obn'), 'header', 'header_obn']),
    ]

    def __init__(self):
        self.machine = StateMachine(self.states, 'expect_header', self)
        self.state_data = []

        self.header = None
        self._was_link = None
        
    def add_state_data(self, data):
        self.state_data.append(data)

    def clear_state_data(self):
        self.state_data.clear()

    def get_state_line(self):
        assert len(self.state_data) > 0
        return self.state_data[0].line
        
    def process(self, s: Signal):
        if s.name not in ['props']:
            try:         
                self.machine.signal(s.name, s)
            except WrongSignalException as ex:
                raise ValueError(f"Error in state machine state={self.machine.state.name}, signal '{s.name}' at line {s.line} state_data={self.state_data}", ex)

    def on_enter_state(self, sig: str, signal: Signal, machine):
        self.clear_state_data()
        if sig != 'br':
            self.add_state_data(signal)

    def on_cycle_state(self, sig: str, signal: Signal, machine):
        self.add_state_data(signal)

    def on_exit_state(self, sig: str, signal: Signal, machine):        
        self.add_state_data(signal)

    obn_header_re = re.compile(r'.* ((\s(обн\.|григ\.|самозв\.|укр\.)) | \(ПАПЦ\))', re.X)
    link_re = re.compile(r'.*(\(|\s)см\.')
    
    def _common_on_header_exit(self, sig, signal: Signal, machine, is_obn):
        pref = '_obn' if is_obn else ''
        
        assert len(self.state_data) > 0
        self.header = join_signals(self.state_data).strip()

        is_obn_re = self.obn_header_re.match(self.header)

        if bool(is_obn) != bool(is_obn_re):
            raise Exception(f'Настоящая или раскольничья кафедра? {self.header} {self.state_data}\n{self.state_data[0].serialize()}')
        
        if sig=='br' and self.link_re.match(self.header):
            self.send(Signal(f'name{pref}_link', self.header, self.get_state_line()))
            self.clear_state_data()
            # manual set next state - wait new header
            machine.set_state('expect_header', run_callbacks=False)
            # and cancel go to state, defined by State.next_state            
            return True
        else:                
            self.send(Signal(f'name{pref}', self.header, self.get_state_line()))
        
    
    def on_header_exit(self, sig: str, signal: Signal, machine):
        return self._common_on_header_exit(sig, signal, machine, False)
        
    def on_header_obn_exit(self, sig: str, signal: Signal, machine):
        return self._common_on_header_exit(sig, signal, machine, True)

        
def join_signals(signals: List[Signal]):
    r = []
    for s in signals:
        if s.name != 'br':
            r.append(s.data)
        else:
            r.append('\n')
    return ''.join(r)
    
    
    
    def finish(self):
        if self.machine.state.name not in ('expect_note_start_or_header', 'expect_note_start_obn_or_header'):
            raise Exception('Wrong finish state of state machine: {self.machine.state.name}')


if __name__ == '__main__':
    import sys
    #texter = TextBuilder()
    #chain = Chain(XmlSax()).add(CafedraSignaller()).add(CafedraBuilder()).add(texter)
    
    chain = Chain(XmlSax()).add(CafedraSignaller())\
                .add(SkippedTextCatcher()).add(TextCleaner())\
                .add(SignalNamePatcher(parse_text_patch(cafedra_signals_patch)))

    if 'names' in sys.argv:    
        chain.add(CafedraNameBuilder())
    elif 'articles' in sys.argv:
        chain.add(CafedraArticleBuilder())
    elif 'tool' in sys.argv:
        chain.add(SignalTool('header', 'br', 'header'))

    if not('no' in sys.argv and 'print' in sys.argv and sys.argv.index('print') - sys.argv.index('no') == 1):
        chain.add(SignalPrinter())

    if 'count' in sys.argv:
        chain.add(SignalCounter())
    
    filename = 'sample_cafedry.xml'
    if len(sys.argv) > 1 and sys.argv[1].endswith('.xml'):
        filename = sys.argv[1]

    with open(filename, encoding='utf8') as f:
        try:
            chain.process(f)
        except ValueError as ex:
            print(ex)
        

    #print(texter.get_text())
    
