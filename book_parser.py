from typing import List, Dict
from dataclasses import dataclass

import re

from chain import Chain, ChainLink, XmlSax, SaxItem  # , Printer
from state_machine import StateMachine, State, WrongSignalException
from models import CafedraArticle, ArticleEpiskopRow, ArticleNote
from lib.rus_eng_letters_confusion import EngInRusWordsTextPreprocessor


@dataclass
class Signal:
    name: str
    data: str
    line: str

    def serialize(self):
        return f"{self.name:15} {self.line or '##NONE##':5} " \
               f"{self.data if self.data else '##NONE##'}"

    @staticmethod
    def deserialize(s):
        name, line_num, data = s.split(maxsplit=2)
        data = data if data != '##NONE##' else None
        line_num = int(line_num) if line_num != '##NONE##' else None
        return Signal(name, data, line_num)


class SignalPrinter(ChainLink):
    def process(self, s: Signal):
        print(s.serialize())
        self.send(s)


class SignalSaver(ChainLink):
    def __init__(self, filename):
        self.f = open(filename, 'w', encoding='utf8')

    def process(self, s: Signal):
        self.f.write(s.serialize() + '\n')
        self.send(s)

    def finish(self):
        self.f.close()


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
    Reads book xml and generates signals as objects of type Signal
    with field 'name' with value from list:
    * header - заголовок статьи о кафедре
    * text - текст статьи о кафедре
    * episkop - строка таблицы епископов, содержит сведения об управлении
                кафедрой епископом в конкретный период
    * episkops_header - подзаголовок внутри таблицы епископов.
            Примеры: В Смоленске; Архиепископы и митрополиты Московские;
    * note_num - номер сноски при ссылке из текста
    * note_start - номер сноски в начале текста сноски
    * note - текст сноски

    * header_obn, text_obn, episkop_obn, note_obn - то же для раскольничьих
                                                    кафедр
    * text_? - текст статьи о кафедре (настоящей или раскольничьей -
                                       надо разбираться из контекста).

    * props - техническая информация о шрифтах и прочем,
              которую можно игнрорировать
    * skipped - куски текста, не отнесённые ни к одному из предыдущих типов
                (таких быть не должно)

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
        # print("SET", st)

    def pop_state(self):
        st = self._state_stack.pop()
        self.signal_type, self.cur_tag, self.tag_level = st
        # print("POP", st)

    def process(self, item: SaxItem):
        if item.event == 'end' and item.level == self.tag_level:
            self.pop_state()
        else:
            self._item_text_skipped = True
            getattr(self, 'tag_' + self.cur_tag)(item)
            if item.event == 'text' and self._item_text_skipped \
               and item.data.strip():
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
                    case 'ParagraphStyle/Таблица' | \
                         'ParagraphStyle/Таблица сжатая':
                        if item.data.get('Justification') == 'CenterAlign':
                            self.set_state('episkops_header', item)
                        else:
                            self.set_state('episkop', item)
                    case 'ParagraphStyle/Сноска с лин' | \
                         'ParagraphStyle/Сноска' | \
                         'ParagraphStyle/Footnote text':
                        self.set_state('note', item)

                    case 'ParagraphStyle/КАФЕДРА ОБН.':
                        self.set_state('header_obn', item)
                    case 'ParagraphStyle/ТЕКСТ ОБН.':
                        self.set_state('text_obn', item)
                    case 'ParagraphStyle/ТАБЛ ОБН' | \
                         'ParagraphStyle/Таблица обн сжатая':
                        self.set_state('episkop_obn', item)
                    case 'ParagraphStyle/СНОСКА с лин. ОБН' | \
                         'ParagraphStyle/сноска обн.':
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
    def __init__(self, fail_on_skipped=True):
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
                continue  # replace with nothing in Бобрикович-Копоть-\u2028\t\t\t\t\t\tАнехожский  # noqa: E501
            else:
                res.append(' ')  # replace with space
        else:
            res.append(s[i])
    return ''.join(res)


class TextCleaner(ChainLink):
    def __init__(self):
        self.fixer = EngInRusWordsTextPreprocessor().process

    def process(self, sig: Signal):
        if sig.data:
            if '\u2028' in sig.data:
                # print("!!!!!", sig)
                sig.data = replace_u2028(sig.data)

            # TODO Сейчас заменяются английские буквы только внутри
            # кириллических слов.
            # Если сделать replace_single=True, то будут заменяться на
            # русские и одиночные английские буквы.
            # Это ломает английские источники, римские X и проч,
            # но в некоторых случаях это надо сделать - встречается
            # предлог 'с' и инициалы, записанные английскими буквами.
            # Когда-нибудь надо запустить с True, сравнить articles.json
            # и при помощи signal patch вручную поправить нужные места.
            sig.data = self.fixer(sig.data, replace_single=False)

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
        cond1 = s.name.startswith(self.prefix1) \
                and self._prev and self._prev.name.startswith(self.prefix2)
        if self.prefix3:
            if cond1 and self._prev_prev \
               and self._prev_prev.name.startswith(self.prefix3):
                self.send(
                    Signal('tool', (self._prev_prev, self._prev, s), s.line)
                )
        elif cond1:
            self.send(Signal('tool', (self._prev, s), s.line))

        self._prev_prev = self._prev
        self._prev = s


class SignalPatcher(ChainLink):
    def __init__(self, patches: Dict[int, tuple]):
        """
        patches - dict with key = signal line field,
        value = tuple (signal data for check, new signal name)

        special keys:
        * SKIP! - delete this signal for data flow
        * BR! - insert Signal(name='br') before this signal
        * EDIT! - edit signal text. Signal data for check
                  should be 'check data===>full new data'
        """
        self.patches = patches

    def process(self, s: Signal):
        patch = self.patches.get(s.line)
        if patch:
            expected_data, new_signal_name = patch
            if new_signal_name == 'SKIP!':
                return
            elif new_signal_name == 'EDIT!':
                expected_data, new_signal_data = expected_data.split('===>')

            if not (s.data == expected_data
               or s.data.strip().startswith(expected_data.strip())):
                raise Exception("Signal and patch different: expected "
                                f"'{expected_data}' for signal {s}")

            if new_signal_name == 'BR!':
                # add BR before signal
                self.send(Signal('br', None, s.line))
            elif new_signal_name == 'EDIT!':
                s.data = new_signal_data
            else:
                s.name = new_signal_name

        self.send(s)


cafedra_signals_patch = open('signal_patch.txt', encoding='utf8').read()


def parse_text_patch(text_patch):
    res = {}
    for line in text_patch.split('\n'):
        l = line.strip()  # noqa: E741
        if not l or l.startswith('#'):
            continue

        s = Signal.deserialize(l)
        res[s.line] = (s.data, s.name)
        # new_type, line_num, expected_data = l.split(maxsplit=2)
        # res[int(line_num)] = (expected_data, new_type)

    return res


class CafedraArticleBuilder(ChainLink):
    # При составлении правил надо иметь ввиду, что пока мы находимся в рамках
    # одного состояния сигналы складируются в self.state_data с целью сбора
    # итогового текста при выходе из состояния.
    states = [
        State('expect_header', cycle=[], next_state=['header', 'header_obn']),

        State('header', cycle='header', next_state=[
            'text', ('br', 'expect_text')
        ]),
        State('expect_text', cycle='br', next_state='text'),
        State('text', cycle=['text', 'br', 'note_num'], next_state=[
            'episkop', 'episkops_header', 'header', 'header_obn', 'note_start'
        ]),
        State('episkop', cycle=['episkop', 'note_num'], next_state=[
            ('br', 'expect_ep_note_head'), 'note_start', 'header', 'header_obn'
        ]),
        State('expect_ep_note_head', cycle='br', next_state=[
            'episkop', 'episkops_header', 'note_start', 'header', 'header_obn'
        ]),

        State('episkops_header', cycle=['episkops_header', 'note_num'],
              next_state=['episkop', ('br', 'expect_episkop')]),
        State('expect_episkop', cycle='br', next_state='episkop'),

        State('note_start', cycle=[], next_state='note'),
        State('note', cycle=['note', 'br'],
              next_state=['note_start', 'header', 'header_obn']),

        # раскольничьи кафедры - в общем-то копия,
        # но для надёжности обрабатываем их отдельно
        State('header_obn', cycle=['header_obn'],
              next_state=['text_obn', ('br', 'expect_text_obn')]),
        State('expect_text_obn', cycle='br', next_state='text_obn'),
        State('text_obn', cycle=['text_obn', 'br', 'note_num'], next_state=[
            'episkop_obn', 'header', 'header_obn'
        ]),
        State('episkop_obn', cycle=['episkop_obn', 'note_num'], next_state=[
            ('br', 'expect_ep_obn_note_head'),
            ('note_start', 'note_start_obn'),
            'header', 'header_obn'
        ]),
        State('expect_ep_obn_note_head', cycle='br', next_state=[
            'episkop_obn', ('note_start', 'note_start_obn'),
            'header', 'header_obn'
        ]),
        State('note_start_obn', cycle=[],
              next_state=['note_obn', ('note', 'note_obn')]),
        State('note_obn', cycle=['note_obn', 'note', 'br'], next_state=  # noqa E251
              [('note_start', 'note_start_obn'), 'header', 'header_obn']),
    ]

    # Машина состояний требует наличия текста после заголовка,
    # но в редких случаях список епископов следует сразу после заголовка.
    no_text_cafedras = [
        'Викариатство Киевской епархии',
        'ВЛАДИВОСТОКСКАЯ, григ.',
        'МОСКОВСКИЙ И ВСЕЯ РОССИИ ПАТРИАРХАТ, обн.',
        'САРАТОВСКАЯ, григ.',
        'ХАРЬКОВСКАЯ, григ.',
        'ЯРОСЛАВСКАЯ, григ.'
    ]

    def __init__(self):
        self.machine = StateMachine(self.states, 'expect_header', self)
        self.state_data = []

        self.caf = None
        self._cur_note_number = None

    def add_state_data(self, data):
        self.state_data.append(data)

    def clear_state_data(self):
        self.state_data.clear()

    def get_state_line(self):
        assert len(self.state_data) > 0
        return self.state_data[0].line

    def send_cafedra_and_create_new(self):
        if self.caf:
            assert self.caf.header, 'Empty cafedra!!!'
            sig_name = 'cafedra'
            if self.caf.is_obn:
                sig_name += '_obn'
            if self.caf.is_link:
                sig_name += '_link'
            assert self._cur_note_number is None
            self.send(Signal(sig_name, self.caf, self.caf.start_line))

        self.caf = CafedraArticle()

    def process(self, s: Signal):
        if s.name not in ['props']:
            try:
                self.machine.signal(s.name, s)
            except WrongSignalException as ex:
                raise ValueError(f"{s.line}: Error in state machine "
                                 f"state={self.machine.state.name}, "
                                 f"signal '{s.name}' at line {s.line} "
                                 f"state_data={self.state_data}", ex)
            # except Exception as ex:     - this makes system exceptions unreadable  # noqa: E501
            #    raise Exception(f"{s.line}: {ex}")

    def on_enter_state(self, sig: str, signal: Signal, machine):
        self.clear_state_data()
        if sig != 'br':
            self.add_state_data(signal)

    def on_cycle_state(self, sig: str, signal: Signal, machine):
        self.add_state_data(signal)

    def on_exit_state(self, sig: str, signal: Signal, machine):
        pass
        # self.add_state_data(signal)

    def on_fail_state(self, sig: str, signal: Signal, machine):
        if self.caf.header in self.no_text_cafedras \
                and machine.state.name == 'expect_text' and sig == 'episkop':
            machine.set_state('text', run_callbacks=False)
            machine.signal(sig, signal)
            return True
        elif self.caf.header in self.no_text_cafedras \
                and machine.state.name == 'expect_text_obn' \
                and sig == 'episkop_obn':
            machine.set_state('text_obn', run_callbacks=False)
            machine.signal(sig, signal)
            return True

    def on_header_enter(self, sig: str, signal: Signal, machine):
        self.send_cafedra_and_create_new()
        self.caf.start_line = signal.line

    def on_header_obn_enter(self, sig: str, signal: Signal, machine):
        self.send_cafedra_and_create_new()
        self.caf.start_line = signal.line

    def on_header_exit(self, sig: str, signal: Signal, machine):
        return self._build_header(sig, machine, False)

    def on_header_obn_exit(self, sig: str, signal: Signal, machine):
        return self._build_header(sig, machine, True)

    def on_text_exit(self, sig: str, signal: Signal, machine):
        self._build_text()

    def on_text_obn_exit(self, sig: str, signal: Signal, machine):
        self._build_text()

    def on_episkop_exit(self, sig: str, signal: Signal, machine):
        self._build_episkop()

    def on_episkop_obn_exit(self, sig: str, signal: Signal, machine):
        self._build_episkop()

    def on_episkops_header_exit(self, sig: str, signal: Signal, machine):
        self._build_episkops_header()

    def on_note_start_exit(self, sig: str, signal: Signal, machine):
        self._build_note_start()

    def on_note_start_obn_exit(self, sig: str, signal: Signal, machine):
        self._build_note_start()

    def on_note_exit(self, sig: str, signal: Signal, machine):
        self._build_note()

    def on_note_obn_exit(self, sig: str, signal: Signal, machine):
        self._build_note()

    def finish(self):
        if self.machine.state.name not in ('note', 'note_obn'):
            raise Exception(f'Wrong finish state of state machine: '
                            f'{self.machine.state.name}')

        # save last article last note info
        self.machine.set_state('expect_header', run_callbacks=True)
        self.send_cafedra_and_create_new()

    @property
    def header(self):
        return self.caf.header

    obn_header_re = re.compile(r'.* ((\s(обн\.|григ\.|самозв\.|укр\.)) | \(ПАПЦ\))', re.X)  # noqa: E501
    link_re = re.compile(r'.*(\(|\s)см\.')

    def _build_header(self, sig: str, machine, is_obn):
        assert len(self.state_data) > 0
        self.caf.header = join_signals(self.state_data)
        self.caf.is_obn = is_obn

        is_obn_re = self.obn_header_re.match(self.header)

        if bool(is_obn) != bool(is_obn_re):
            raise Exception(f'Настоящая или раскольничья кафедра? '
                            f'{self.header} {self.state_data}\n'
                            f'{self.state_data[0].serialize()}')

        if sig == 'br' and self.link_re.match(self.header):
            self.caf.is_link = True
            self.clear_state_data()
            # manual set next state - wait new header
            machine.set_state('expect_header', run_callbacks=False)
            # and cancel go to state, defined by State.next_state
            return True
        else:
            # self.send(Signal(f'name{"_obn" if is_obn else ""}', self.header, self.get_state_line()))  # noqa: E501
            pass

    def _build_text(self):
        self.caf.text = join_signals_html(self.state_data)

    def _build_episkop(self):
        line = join_signals_html(self.state_data, strip=False)
        item = ArticleEpiskopRow(line)
        self.caf.episkops.append(item)

    def _build_episkops_header(self):
        header = join_signals_html(self.state_data)
        self.caf.episkops.append(header)

    def _build_note_start(self):
        assert self._cur_note_number is None
        self._cur_note_number = int(join_signals(self.state_data))

    def _build_note(self):
        assert self._cur_note_number is not None
        note = join_signals_html(self.state_data)
        assert len(note) > 0
        self.caf.notes.append(ArticleNote(self._cur_note_number, note))
        self._cur_note_number = None


def join_signals(signals: List[Signal]):
    r = []
    for s in signals:
        if s.name != 'br':
            r.append(s.data)
        else:
            r.append('\n')
    return ''.join(r).strip()


def join_signals_html(signals: List[Signal], strip=True):
    import html
    r = []
    for s in signals:
        if s.name == 'br':
            r.append('<br>\n')
        elif s.name == 'note_num':
            note_num = int(s.data)
            r.append(f'<span class="note" data-note="{note_num}">{note_num}</span>')  # noqa: E501
        else:
            r.append(html.escape(s.data))

    while r and r[-1] == '<br>\n':
        del r[-1]

    res = ''.join(r)
    if strip:
        res = res.strip()
    return res


class CafedraArticlesToJsonFile(ChainLink):
    def __init__(self, path):
        self.path = path
        self.out = open(path, 'w', encoding='utf8')
        self.out.write('[\n')
        self._first = True

    def process(self, s: Signal):
        import json
        if not isinstance(s.data, CafedraArticle):
            raise ValueError('Expected Signal with CafedraArticle object '
                             'in data field')

        json_data = json.dumps(s.data.to_dict(), ensure_ascii=False, indent=4)
        if not self._first:
            self.out.write(',\n')
        else:
            self._first = False
        self.out.write(json_data)

        self.send(Signal(s.name, f'{s.data.header} | {len(json_data)/1024: .1f} kb', s.line))  # noqa: E501

    def finish(self):
        self.out.write('\n]\n')
        size = self.out.tell() + 1
        self.out.close()
        self.send(Signal('json_file', self.path, None))
        self.send(Signal('json_file_size', size, None))


class CafedraArticlesFromJson(ChainLink):
    @staticmethod
    def load_parsed_book(json_file: str) -> List[CafedraArticle]:
        import json
        db = json.load(open(json_file))
        assert isinstance(db, list)

        for i in range(len(db)):
            db[i] = CafedraArticle.from_dict(db[i])

        return db

    def process(self, json_filename):
        signals = self.load_parsed_book(json_filename)

        for s in signals:
            s: CafedraArticle
            self.send(s)


if __name__ == '__main__':
    import sys
    chain = Chain(XmlSax()) \
        .add(CafedraSignaller()) \
        .add(SignalSaver('signals.txt')) \
        .add(SkippedTextCatcher()).add(TextCleaner()) \
        .add(SignalPatcher(parse_text_patch(cafedra_signals_patch)))
    if 'articles' in sys.argv:
        chain.add(CafedraArticleBuilder())\
             .add(CafedraArticlesToJsonFile('articles.json'))
    elif 'tool' in sys.argv:
        chain.add(SignalTool('header', 'br', 'header'))

    if not ('no' in sys.argv and 'print' in sys.argv and
       sys.argv.index('print') - sys.argv.index('no') == 1):
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

    # print(texter.get_text())
