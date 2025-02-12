import sys
import os
import json
from pathlib import Path
import re
from dataclasses import dataclass

sys.path.append(os.getcwd())
from article_parser import divide_episkop_row
from parsers.fail import ParseFail

from edit import storage

from datetime import datetime

CSS_NOTE_ERROR = 'error-note'

ORIGINAL_DATA_FILE = 'data/edit-init/cafedra-edit.json'
EXPANDED_DATA_FILE = 'data/edit-init/cafedra-exp-abbrs-edit.json'

def main():
    if len(sys.argv) != 2:
        print("добавьте параметр json для преобразования json во входной html,\n" + \
              "либо db для построения БД на основе html")
        return 1
    if sys.argv[1] == 'json':
        print('\n\n============================')
        print('Конвертируем исходный текст книги (с сокращениями)\n')

        ok = process_json(ORIGINAL_DATA_FILE)
        if not ok: return 2

        print('\n\n============================')
        print("Конвертируем текст с раскрытыми сокращениями\n")
        ok = process_json(EXPANDED_DATA_FILE)
        if not ok: return 2
        
        print('\n\n============================')
        print("Проверяем согласованность двух упомянутых текстов...")
        from utils import check_cafedra_expand_abbrs as check_util
        ok = check_util.main(ORIGINAL_DATA_FILE, EXPANDED_DATA_FILE)
        if ok: print("OK")
        else:
            print("Fail")
            return 3

    elif sys.argv[1] == 'old-json':
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
        filename = EXPANDED_DATA_FILE
        print("Загружаем данные из файла", filename, "в БД", storage.DbName)

        with open(filename) as f:
            html = f.read().strip()

        articles = [x.strip() + '</article>' for x in html.split('</article>') if x.strip().startswith('<article')]

        check = html.count('<article class="cafedra_article')
        assert len(articles) == check, f"Должно быть {check} статей, а получилось {len(articles)}"

        print(f"Всего {check} статей")

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
            reg_data = {
                'who': 'admin',
                'when': datetime.fromisoformat('2024-06-01T09:00:00+00:00').timestamp(),
                'comment': 'автоматически раскрыты сокращения'
            }
            for art in articles:
                c = stor.cafedra.new()
                c.html = art
                stor.cafedra.upsert(c, reg_data=reg_data, fix_reg_data=False)


        print("Готово!")


def process_json(filename):
    print("Конвертируем файл", filename, "во входной html")

    if filename.endswith(".json"):
        filename, error = article_json_to_html_edit(filename)
        if error:
            print(f"""\nNB!!!\tПри конвертации данных есть ошибки!!!
            Результат конвертации лежит в {filename},
            а отчёт с удобным просмотром ошибок - {error}.
            Для поиска ошибок ищите html теги с class = {CSS_NOTE_ERROR}""")
            return False

        print(f"Успешно сконвертированный html в файле {filename}")
        return True
    else:
        raise ValueError("Expected json file")





def article_json_to_html_edit(filename):
    result_file = Path(filename).with_suffix(".html")
    errs = []
    with open(filename) as f, open(result_file, 'w', encoding="utf8") as t:
        data = json.load(f)
        assert isinstance(data, list)
        for d in data:
            r, err = convert_cafedra_json_to_html(d)
            t.write(r)
            if err:
                r, err = convert_cafedra_json_to_html(d, mode='error_report')

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



note_re = re.compile(r'<span\s+class="note"[^>]*? data-note="(?P<note_num_0>\d+)"[^>]*>\s*(?P<note_num>\d+)\s*</span>')

@dataclass
class Note:
    num: int
    text: str
    touched: bool = False

def convert_cafedra_json_to_html(caf: dict, mode="normal"):
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
                return f'''<details><summary><sup>[сноска]</sup></summary><div>{r.text}</div></details>'''
        else:
            has_err=True

            if mode=="error_report":
                return \
f'''<sup class="{CSS_NOTE_ERROR}" data-note-num="{m.group('note_num')}" title="сноска БЕЗ ТЕКСТА">
         <b>{m.group('note_num')}</b> - сноска БЕЗ ТЕКСТА ???
</sup>'''
            else:
                return f'''<sup class="{CSS_NOTE_ERROR}" style="color:red" title="сноска БЕЗ ТЕКСТА"><b>{m.group('note_num')}</b>???</sup>''' + \
                f'''<details><div>??? нет текста сноски ???</div></details>'''

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
    result = f'''
<article class="cafedra_article" data-start-line="{caf['start_line']}" data-is-link="{caf['is_link']}" data-is-obn="{caf['is_obn']}">
<div class="header">{header}</div>
<div class="text">
{text}
<br>
</div>
<table class="episkops">
{html_eps}
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

if __name__ == '__main__':
    main()
