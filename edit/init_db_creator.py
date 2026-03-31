import sys
import os
import json
from pathlib import Path
import re
from dataclasses import dataclass

sys.path.append(os.getcwd())
from article_parser import divide_episkop_row
from parsers.fail import ParseFail
from utils import check_cafedra_expand_abbrs as cafedra_check_util

from edit import storage

from datetime import datetime

from typing import List

CSS_NOTE_ERROR = 'error-note'

ORIGINAL_CAFEDRA_JSON = 'data/edit-init/cafedra-edit.json'
EXPANDED_CAFEDRA_JSON = 'data/edit-init/cafedra-exp-abbrs-edit.json'

EPISKOP_JSON = 'data/edit-init/episkop-edit.json'

CAFEDRA_MAP_FILE = 'data/edit-init/map-origin-expanded-cafedra.json'

def main():
    if len(sys.argv) != 2:
        print("добавьте параметр json для преобразования json во входные html,\n" + \
              "либо db для построения БД на основе html")
        return 1
    if sys.argv[1] == 'json':
        er = make_cafedra_html()
        if er: return er
        
        er = make_episkop_html()
        if er: return er

    elif sys.argv[1] == 'old-json':
        # сборка json из оригинального текста книги
        from chain import Chain, ChainLink
        from article_parser import CafedraArticleParser, WholeRussiaCafedraFixer,\
                                   CafedraJsonPatcher, UnparsedCafedraEpiskopLogger
        from book_parser import CafedraArticlesFromJson, CafedraArticlesToJsonFile

        target_path = 'data/edit-init/cafedra_old.json'
        target_json = CafedraArticlesToJsonFile(target_path)

        patch_file = 'data/patch/cafedra-episkop-patch-old.txt'

        ch = Chain(CafedraArticlesFromJson()) \
            .add(CafedraJsonPatcher(patch_file)) \
            .add(target_json)

        source_file = 'data/cafedra_articles.json'
        print(f"Patch {source_file} and save to to {target_path}")
        ch.process(source_file)

    elif sys.argv[1] == 'db':
        load_result_html_into_db()
    
    else:
        print('Непонятно. Для получения справки запустите без параметров')
        return 1


def load_result_html_into_db():    
    file1 = Path(ORIGINAL_CAFEDRA_JSON).with_suffix('.html')
    file2 = Path(EXPANDED_CAFEDRA_JSON).with_suffix('.html')
    print("Загружаем кафедры из файлов", file1, "и", file2, "в БД", storage.DbName)
    
    articles1: List[storage.TextCafedra] = load_cafedra_html(file1)
    articles2: List[storage.TextCafedra] = load_cafedra_html(file2)
    assert len(articles1) == len(articles2), "Разное количество статей"
    
    with open(CAFEDRA_MAP_FILE, encoding='utf8') as f:
        header_map = json.load(f)        
    
    file_ep = Path(EPISKOP_JSON).with_suffix('.html')
    print(f"Загружаем епископов из файла {file_ep}")
    
    articles_ep: List[storage.TextEpiskop] = load_episkop_html(file_ep)

    print("Создаём БД", storage.DbName)
    if os.path.exists(storage.DbName):
        ans = input("БД уже существует. Удалить? ")
        if ans.lower().strip() in ['1', 'true', 'yes', 'да']:
            os.remove(storage.DbName)
            print("Create new edit db")
            storage.init_edit_db()
        else:
            print("Тогда ничего не делаем")
            return 4        

    stor = storage.HierarhEditStorage()
    with stor.atomic():
        reg_data_orig = {
            'who': 'admin',
            'when': datetime.fromisoformat('2019-03-03T12:00:00+00:00').timestamp(),
            'comment': 'текст книги'
        }
        
        reg_data_exp = {
            'who': 'admin',
            'when': datetime.fromisoformat('2024-06-01T09:00:00+00:00').timestamp(),
            'comment': 'автоматически раскрыты сокращения'
        }
        
        print(f"Загружаем кафедры - {len(articles1)} статей")
        for i, art in enumerate(articles1):                
            art = stor.cafedra.upsert(art, reg_data=reg_data_orig, fix_reg_data=False)
            
            assert header_map[art.header()] == articles2[i].header()
            
            art.html = articles2[i].html
            art = stor.cafedra.upsert(art, reg_data=reg_data_exp, fix_reg_data=False)
            
        print(f"Загружаем епископов - {len(articles_ep)} статей")
        for i, art in enumerate(articles_ep):
            art = stor.episkop.upsert(art, reg_data = reg_data_orig, fix_reg_data=False)
        

    print("Готово!")

def make_cafedra_html():
    print('\n\n============================')
    print('Конвертируем исходный текст книги (с сокращениями)\n')

    html_o = process_cafedra_json(ORIGINAL_CAFEDRA_JSON)
    if not html_o: return 2

    print('\n\n============================')
    print("Конвертируем текст с раскрытыми сокращениями\n")
    html_e = process_cafedra_json(EXPANDED_CAFEDRA_JSON)
    if not html_e: return 2
    
    print('\n\n============================')
    print("Проверяем согласованность двух упомянутых текстов...")
    
    ok = cafedra_check_util.main(ORIGINAL_CAFEDRA_JSON, EXPANDED_CAFEDRA_JSON)
    if ok: print("OK")
    else:
        print("Fail")
        return 3
    
    print('\n\n============================')
    print("Соотносим заголовки в двух текстах")
    caf_origin: List[storage.TextCafedra] = load_cafedra_html(html_o)
    caf_expand: List[storage.TextCafedra] = load_cafedra_html(html_e)
    
    map_data = {}
    assert len(caf_origin) == len(caf_expand), "Разное количество статей"
    for (co, ce) in zip(caf_origin, caf_expand):
        head1, head2 = co.header(), ce.header()
        ok = True
        if not cafedra_check_util.header_like(head1, head2):
            print(f'Разные кафедры? {head1}  <-> {head2}')
            ok = False
        else:
            map_data[head1] = head2
        if not ok:
            return 4
            
    with open(CAFEDRA_MAP_FILE, 'w', encoding="utf8") as f:
        json.dump(map_data, f, ensure_ascii=False, indent=2)
    print("Соотнесение заголовков в файле", CAFEDRA_MAP_FILE)
    

def process_cafedra_json(filename):
    print("Конвертируем файл", filename, "во входной html")

    if filename.endswith(".json"):
        filename, error = cafedra_json_to_html_edit(filename)
        if error:
            print(f"""\nNB!!!\tПри конвертации данных есть ошибки!!!
            Результат конвертации лежит в {filename},
            а отчёт с удобным просмотром ошибок - {error}.
            Для поиска ошибок ищите html теги с class = {CSS_NOTE_ERROR}""")
            return False

        print(f"Успешно сконвертированный html в файле {filename}")
        return filename
    else:
        raise ValueError("Expected json file")


def cafedra_json_to_html_edit(filename):
    result_file = Path(filename).with_suffix(".html")
    errs = []
    with open(filename) as f, open(result_file, 'w', encoding="utf8") as t:
        data = json.load(f)
        assert isinstance(data, list)
        for d in data:
            r, err = convert_cafedra_to_html(d)
            t.write(r)
            if err:
                r, err = convert_cafedra_to_html(d, mode='error_report')

                errs.append(r)


    error_file = Path(filename).with_suffix(".errors.html")
    error_file.unlink(missing_ok=True)
    if errs:
        with open(error_file, 'w', encoding="utf8") as f:
            f.write(f'''<!DOCTYPE html>
            <body>
            <style>
            .{CSS_NOTE_ERROR} {{
                color:red;
                background-color: yellow;
            }}

            body {{
                max-width: 800px;
                margin: auto;
            }}

            .header {{
                font-size: x-large;
                font-weight: bold;
            }}

            table {{
                border-collapse: collapse;
            }}
            td {{
                height: 40px; /* it is min height */
                border: 1px solid #DDDDDD;
                padding: 5px;
            }}
            </style>

            <h1>Статьи с ошибками</h1>
            <div>
            Всего статей с ошибками: {len(errs)}<br/>
            Жёлтым выделены ошибки в сносках и прочем.
            </div>
            <hr/>
            ''')
            for er in errs:
                f.write(er)
            f.write("</body>")
    else:
        error_file = None

    return result_file, error_file


_note_base_re = r'(?P<note_full><span\s+class="note"[^>]*? data-note="(?P<note_num_0>\d+)"[^>]*>\s*(?P<note_num>\d+)\s*</span>)'
_space_re = r'(\s|\\t)*'
note_re = re.compile(_note_base_re)
inaccurate_tail_note_re = re.compile(rf'^{_space_re}(?P<brackets>\(.*\)){_space_re}{_note_base_re}{_space_re}$')

@dataclass
class Note:
    num: int
    text: str
    touched: bool = False

def convert_cafedra_to_html(caf: dict, mode="normal"):
    has_err = False
    notes = [Note(int(x['num']), x['text']) for x in caf['notes']]

    def find_note(num):
        num = int(num)
        for x in notes:
            if x.num == num:
                return x

    def note_convert(m):
        nonlocal has_err
        r = find_note(m.group('note_num'))
        if r:
            # если сноска уже была упомянута - то на неё ссылаются из текста два раза - это тоже плохо
            if r.touched:
                has_err=True
                if mode == "error_report":                    
                    return \
f'''<sup class="{CSS_NOTE_ERROR}" data-note-num="{m.group('note_num')}" title="повторное обращение к сноске">
         {m.group('note_num')} – повторное обращение к сноске
</sup>'''
                
            r.touched=True

            if m.group('note_num_0') != m.group('note_num'):
                has_err=True
                if mode == "error_report":                    
                    return \
f'''<sup class="{CSS_NOTE_ERROR}" data-note-num="{m.group('note_num')}" title="сноска БЕЗ ТЕКСТА">
         разные номера в json: data-note={m.group('note_num_0')}   номер_сноски={m.group('note_num')}
</sup>'''

            if mode=="error_report":
                return f'''<sup data-note-num="{m.group('note_num')}">{m.group('note_num')}</sup>'''
            else:
                return f'''<span class="fnote"><sup>[сноска]</sup><span>{r.text}</span></span>'''
        else:
            has_err=True

            if mode=="error_report":
                return \
f'''<sup class="{CSS_NOTE_ERROR}" data-note-num="{m.group('note_num')}" title="сноска БЕЗ ТЕКСТА">
         <b>{m.group('note_num')}</b> - сноска БЕЗ ТЕКСТА ???
</sup>'''
            else:
                return f'''<sup class="{CSS_NOTE_ERROR}" style="color:red" title="сноска БЕЗ ТЕКСТА"><b>{m.group('note_num')}</b>???</sup>''' + \
                f'''<span class="fnote"><sup>[сноска]</sup><span>??? нет текста сноски ???</span></span>'''

    def convert_notes(txt):
        if not txt: return ''
        return note_re.sub(note_convert, txt)

    header = convert_notes(caf['header'])
    text = convert_notes(caf.get('text') or '')

    html_eps = []
    for i, ep in enumerate((caf['episkops'] or []), 1):
        if isinstance(ep, str):
            ep = convert_notes(ep)
            html_eps.append(f'''<tr class="header-row"><td colspan="3">{ep}</td></tr>''')
        else:
            assert isinstance(ep, dict) and len(ep) == 1
            ep = ep['text']
            if isinstance(ep, list):
                assert len(ep) == 3 and all(map(lambda x: isinstance(x, str) or x is None, ep)), \
                       "Поле text должно содержать либо строку, либо массив 3-х строк"
                start, end, who = ep
                if start and end and start.strip().startswith('(') and who.strip().endswith(')'):
                    inexact = True
                    start = start.strip()[1:]
                    who = who.strip()[:-1]
                else:
                    inexact = False
            else:                
                # Сноска после неточной строки в скобках:
                # \t\t(06.1943\t–\t09.1943\t–\tПавел Мелетьев)<span class=\"note\" data-note=\"8\">8</span>
                tail_note_after_inaccurate = None
                sm = inaccurate_tail_note_re.match(ep)
                if sm:
                    ep = sm.group('brackets')
                    tail_note_after_inaccurate = sm.group('note_full')

                r = divide_episkop_row(ep)
                if isinstance(r, ParseFail):
                    raise Exception(f'''
В статье {caf['header']} не удалось разбить строку епископа №{i}
{ep}
на колонки ОТ ДО и КТО.

Во входном json файле сделайте разбивку под длинным тирэ вручную:
полю 'text' вместо строки сопоставьте массив из трёх строк.
Если исходная строка взята в скобки, например "text": "(90 – 120 – Кто-то)", то сделайте так:
"text": ["(90", "120", "Кто-то)"]  ''')
                start, end, who, inexact = r

                if tail_note_after_inaccurate:
                    assert inexact, 'Ошибка логики - раз сработала inaccurate_tail_note_re, то строка должна быть в скобках!'
                    who += tail_note_after_inaccurate

            start, end, who = map(convert_notes, (start, end, who))

            if inexact:
                startTr = '<tr class="inaccurate">'
            else:
                startTr = '<tr>'

            html_eps.append(
            f'  {startTr}<td>{start}</td><td>{end}</td><td>{who}</td></tr>')
    html_eps = '\n'.join(html_eps)

    bad_notes_info = build_bad_notes(mode, notes)
    if bad_notes_info:
        has_err = True

    #NB! html-escaping уже сделан во входном json
    b = lambda v: "true" if v else "false"
    result = f'''
<article class="cafedra_article" data-start-line="{caf['start_line']}" data-is-link="{b(caf['is_link'])}" data-is-obn="{b(caf['is_obn'])}">
<div class="header">{header}</div>
<div class="text">
{text}
<br>
</div>
<table class="episkops">
<thead>
<tr><th>начало</th><th>окончание</th><th>епископ</th></tr>
</thead>
<tbody>
{html_eps}
</tbody>
</table>
{bad_notes_info}
</article>
'''

    return result, has_err


def build_bad_notes(mode, notes):
    unused_notes = '\n'.join([f'''<li class="{CSS_NOTE_ERROR}" style="color:red">{x.num}. {x.text}</li>''' for x in notes if not x.touched])

    if mode == "error_report":
        def gen_attrs(expected_num, note):
            if note.touched:
                if (expected_num != note.num):
                    return f'class="{CSS_NOTE_ERROR}" title="нумерация не по порядку"'
                return ''
            else:
                return f'class="{CSS_NOTE_ERROR}" title="не упомянута в тексте"'

        notes_info = '\n'.join([f'''<li {gen_attrs(i, x)}>{x.num}. {x.text}</li>''' for i, x in enumerate(notes, 1)])
        caption = "Выделены сноски, не упомянутые в статье либо со сбитой нумерацией"
        action = ''
    else:
        notes_info = unused_notes
        caption = "Неиспользуемые сноски:"
        action = '''<button onclick="this.closest('.notes-info').remove()">удалить это сообщение</button>'''
    if notes_info:
        return f'''
        <div class="notes-info">
        <em>{caption}</em>
        {action}
        <ul>
        {notes_info}
        </ul>
        </div>'''
    return ''


def make_episkop_html():
    print('\n\n============================')
    print('Конвертируем данные о епископах\n')
    
    filename = EPISKOP_JSON    
    print("Конвертируем файл", filename, "во входной html")

    with open(filename, encoding="utf8") as f:
        json_e = json.load(f)
    
    result_file = Path(filename).with_suffix(".html")
    
    assert isinstance(json_e, list), 'Ожидается список епископов'
    
    with result_file.open('w', encoding='utf8') as out:
        for ep in json_e:
            try:
                ep_html = convert_episkop_to_html(ep)
            except Exception as e:
                print("Ошибка с епископом")
                print(ep)
                raise
            else:    
                out.write(ep_html)
    
    print(f"Успешно сконвертированный html в файле {result_file}")


def convert_episkop_to_html(ep: dict):
    b = lambda v: "true" if v else "false"
    
    name = ep['name'].strip()
    # имя есть и туда не попало что-то не то
    assert name and re.match('.*[а-яА-ЯN]', name)
    
    cafs = ep['appointments']
    
    is_link = ' см.'   in name or '(см.' in name
    
    assert (not is_link and len(cafs) > 0) or (is_link and len(cafs) == 0), name
    
    if is_link:
            return f'''
<article class="episkop_article" data-is-obn="{b(ep['isRenovator'])}" data-is-dubious="false" data-is-link="true">
<div class="header">{name}</div>
<div class="text"><br></div>
</article>
'''
    
    # Статья о епископе в скобках - условные (легендарные) личности
    legendary = False
    tail = cafs[-1]['dates'].strip()
    skip = ['(Св. ?) Ефрем I', '(Св.?) Иоанн III', '(Св.?) Прохор']
    if name.startswith('(') and name not in skip:
        if not tail.endswith(')'):
            raise Exception('Статья о епископе в скобках или нет?')
        legendary = True
        # убираем скобки
        name = name[1:]
        cafs[-1]['dates'] = tail[:-1]  

    html_cafs = []
    for caf in ep['appointments']:
        cafedra = caf['department']
        assert cafedra
        dating:str = caf['dates']
        
        inaccurate = False

        '''
        Св. Петр Волынянин
        ВСЕРОССИЙСКАЯ 1308–21.12.1326
        (ВО ВЛАДИМИРЕ 1308(1309)–1321
        В МОСКВЕ 1321–21.12.1326)
        '''
        if cafedra == '(ВО ВЛАДИМИРЕ':
            cafedra, inaccurate = 'ВО ВЛАДИМИРЕ', True
        elif cafedra == 'В МОСКВЕ' and dating == '1321–21.12.1326)':
            cafedra, inaccurate = 'В МОСКВЕ', True
            dating = dating[:-1]
        elif cafedra.startswith('('):
            if dating.endswith(')') and dating.count('(') + 1 == dating.count(')'):
                cafedra = cafedra[1:].strip()
                dating = dating[:-1].strip()
                inaccurate = True
            elif cafedra.startswith('(в/у'):
                pass
            else:
                raise Exception('Bad inaccurate brackets: ' + str(caf))

        start, end, _ = divide_dating_start_end(dating)
        if inaccurate:
            html_cafs.append(f'''<tr class="inaccurate"><td>{cafedra}</td><td>{start}</td><td>{end}</td></tr>''')
        else:
            html_cafs.append(f'''<tr><td>{cafedra}</td><td>{start}</td><td>{end}</td></tr>''')
    
    html_cafs = '\n'.join(html_cafs)
    
    return f'''
<article class="episkop_article" data-is-obn="{b(ep['isRenovator'])}" data-is-dubious="{b(legendary)}" data-is-link="false">
<div class="header">{name}</div>
<div class="text">
<br>
</div>
<table class="cafedras">
<thead>
<tr><th>кафедра</th><th>начало</th><th>окончание</th></tr>
</thead>
<tbody>
{html_cafs}
</tbody>
</table>
</article>
'''

manual_dating_divide = {
    '–(1441 – 1442)' : (None, '(1441–1442)'),
    'XIII в.': ('XIII в.', None),
    '–(1569 – 1596)': (None, '(1569–1596)'),
    '–(в 1630–1640-е годы)': ('(в 1630–1640-е годы)', None),    
    'XVI в.' : ('XVI в.', None),
    '16(29)02.1924–1928–1929 (?)': ('16(29)02.1924', '1928–1929 (?)'),
    '–(1447–1451)': (None, '(1447–1451)'),
    '(1533–1534)–05.08.1535': ('(1533–1534)', '05.08.1535'),
    'XII в.' : ('XII в.', None),
    '(XII–XIII в.)–' : ('(XII–XIII в.)', None),
    '–(1345– 1347)' : (None, '(1345– 1347)'),
    'XI в.' : ('XI в.', None),
    '–24.04.1339 (1327–1331)' : (None, '24.04.1339 (1327–1331)'),
    '26.04.1135–(1147–1167)' : ('26.04.1135', '(1147–1167)'),
    '–(1929–1930)' : (None, '(1929–1930)'),
    '01(14)02.1928–04.1928 – 04.1929' : ('01(14)02.1928', '04.1928 – 04.1929'),
    'XIII–XIV вв.–' : ('XIII–XIV вв.', None),
    '–08.06.1023(1010 – 1014)' : (None, '08.06.1023(1010 – 1014)'),
    
    
    
}

def divide_dating_start_end(dating):
    def r(f, t, i):
        return (f or '', t or '', i)
        
    if not dating:
        return r(None, None, False)
        
    if re.match(r'^\s*\([^)]+\)\s*$', dating):
        return r(dating, None, True)
    
    d = manual_dating_divide.get(dating) or dating.split('–')    
    #assert len(d) == 2, dating
    if not len(d) == 2:        
        print(f"!!!!!!!!!!! Fail parse date | {dating} |")
        
    return r(d[0], d[1] if len(d)>1 else None, False)


def load_cafedra_html(filename):
    return load_html_result_file(storage.TextCafedra, 'cafedra_article', filename)
    
def load_episkop_html(filename):
    return load_html_result_file(storage.TextEpiskop, 'episkop_article', filename)
    
def load_html_result_file(text_model_class, css_class, filename):
    #from bs4 import BeautifulSoup --- too slow!
    #res = []
    with open(filename, encoding="utf8") as f:        
    #    for ar in BeautifulSoup(f, 'html.parser', from_encoding="utf8").find_all('article'):
    #        tc = storage.TextCafedra.from_html(None, str(ar))
    #        res.append(tc)
        html = f.read().strip()

    articles = [x.strip() + '</article>' for x in html.split('</article>') if x.strip().startswith('<article')]

    check = html.count(f'<article class="{css_class}')
    assert len(articles) == check, f"Должно быть {check} статей, а получилось {len(articles)}"

    res = [text_model_class.from_html(None, x) for x in articles]
    return res


if __name__ == '__main__':
    main()
