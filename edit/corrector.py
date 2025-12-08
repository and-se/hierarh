import os
import sys

sys.path.append(os.getcwd())


from lxml import html

import re
import logging
logging.basicConfig()

from edit.storage import HierarhEditStorage, TextCafedra, TextEpiskop

from parsers.fail import ParseFail

def create_tasks_for_coll(db: HierarhEditStorage, coll_name: str, doc_processor, task_type: str, remove_old_tasks: bool):
    """
    Перебирает документы коллекции coll_name и добавляет задачи

    Функция doc_processor(doc, task, db) получает 
    документ коллекции, пустую задачу и соединение с БД.
    Должна добавить в задачу проблемы при помощи Task.add_problem, 
    а также задать заголовок задачи Task.title

    Есть проблемы в задачу не добавлены, то задача для документа не создаётся.
    """

    coll = db.get_coll(coll_name)
    
    if remove_old_tasks:
        # db.task.reset() - recreates table
        db.task.remove_by_type(task_type)
    
    for cnt, doc in enumerate(coll.iterate()):
        if cnt and cnt % 100 == 0:
            logging.warning("Processed %s items", cnt)   
        task = db.task.get(coll_name=db.episkop.name, doc_key=doc.key, doc_reg_data_when=doc.reg_data['when'])
        task.type_ = task_type        
        task.changed = False  # сброс флага изменённости задачи

        # внешняя обработка документа вызывающим
        doc_processor(doc, task, db)

        if task.changed:
            task.save('admin')

def check_episkop_to_cafedra_links(remove_old_tasks=False):
    """Проверка ссылок на кафедры из статей о епископах"""
    Cafedra_name_map = {
        'ВСЕРОССИЙСКАЯ': 
            'ВСЕРОССИЙСКАЯ Митрополия Киевская и всея Руссии («Митрополия России»), Митрополия Московская и всея Руссии',
        'ВЛАДИМИРСКАЯ': 'ВЛАДИМИРСКАЯ (Суздальско-Владимирская)',
        'МОСКОВСКАЯ, обновленческая': 'МОСКОВСКАЯ I, обновленческая',
        'ЗВЕНИГОРОДСКАЯ' : 'ЗВЕНИГОРОДСКАЯ (Московская)',
        'ЗВЕНИГОРОДСКАЯ, обновленческая' : 'ЗВЕНИГОРОДСКАЯ (Московская), обновленческая',
    }

    def episkop_proccessor(ep, task, db):
        task.title = ep.header() + " - непонятные ссылки на кафедры"        
        ep = EpiskopView(ep)

        for i, caf in enumerate(ep.cafedras):
            if caf.link:
                linked = db.cafedra.get(caf.link)
                if not linked:
                    task.add_problem(i, caf, 'сломанная ссылка - нет такой кафедры', caf.link)
                else:
                    linked = CafedraView(linked)
                    if not linked.has_name(caf.name):
                        task.add_problem(i, caf, 'Проставлена сылка на кафедру', linked.name, 'Это верно?')
            else:
                #if caf in db.cafedra.ignored_names:                
                    # не нужно проставлять ссылки на ?, NN
                    #continue
                
                search_name = caf.name
                if caf.name in Cafedra_name_map:
                    search_name = Cafedra_name_map[caf.name]

                found_cafs = db.cafedra.find_by_name(search_name)
                if len(found_cafs) == 1:
                    ... # проставить ссылку на кафедру
                elif not len(found_cafs):
                    task.add_problem(i, caf, "кафедра не найдена")
                else: # many cafedra
                    task.add_problem(i, caf, "какая именно кафедра?", found_cafs)
    
    db = HierarhEditStorage()
    create_tasks_for_coll(db, 'episkop', episkop_proccessor, "episkop->cafedra", remove_old_tasks)
        
def check_cafedra_to_episkop_links(remove_old_tasks):
    """Проверка ссылок на епископов в статьях кафедр"""
    def cafedra_processor(caf, task, db):
        task.title = caf.header() + " - непонятные ссылки на епископов"        
        caf: CafedraView = CafedraView(caf)

        for i, ep in enumerate(caf.episkops):
            if ep.link:
                linked = db.episkop.get(ep.link)
                if not linked:
                    task.add_problem(i, ep, 'сломанная ссылка - нет такого епископа', ep.link)
                else:
                    raise NotImplementedError
                    #linked = EpiskopView(linked)
                    #if not linked.has_name(ep.name):
                    #    task.add_problem(i, ep, 'Проставлена ссылка на епископа', linked.name, 'Это верно?')
            else:
                if ep.header == 'NN':
                    # не нужно проставлять ссылки на ?, NN
                    continue

                parsed_ep = ep.parsed
                if isinstance(parsed_ep, ParseFail):
                    task.add_problem(i, ep, 'Ошибка разбора', parsed_ep)
                    continue
                
                found_ep = db.episkop_index.find_episkops(parsed_ep.name, parsed_ep.surname)
                #found_ep = db.episkop.find_by_name(ep.header)

                if len(found_ep) == 1:
                    ... # проставить ссылку на епископа
                elif not len(found_ep):
                    task.add_problem(i, ep, "епископ не найден")
                else: # many cafedra
                    task.add_problem(i, ep, "какой именно епископ?", [f"{x.header} (#{x.id})" for x in found_ep])
    
    create_tasks_for_coll(HierarhEditStorage(), 'cafedra', cafedra_processor, "episkop->cafedra", remove_old_tasks)


class EpiskopView:
    """
    Структурированное представление html данных епископа
    """
    def __init__(self, data: TextEpiskop):
        self._text = data
        self._tree = html.fragment_fromstring(data.html)    
    
    @property
    def cafedras(self) -> list['CafedraRowView']:
        # отбираем строки таблицы епископов, которые не являются заголовками
        rows = self._tree.xpath("""//table[contains(@class, 'cafedras')]/tbody/tr[not(contains(@class, 'header-row'))]""")
        return [CafedraRowView(r) for r in rows]


from edit.init_db_creator import CAFEDRA_MAP_FILE
import json


class CafedraRowView:    
    """
    Структурированное представление строки таблицы кафедр в html епископа
    """
    def __init__(self, tr: html.HtmlElement):
        self.d = tr
        self.caf = tr[0]
        assert self.caf.tag == 'td'

        self._name = None
 
    @property
    def name(self):
        if not self._name:
            self._name = self.get_cafedra_name_in_episkop(self.caf.text_content())
        return self._name
    
    @property
    def link(self):
        return None  # TODO now no links

    @property
    def dating(self):
        return self.d[1].text_content().strip()
    
    def __repr__(self):
        return f"CafedraRow({self.name} {self.dating})"
    
    def __str__(self):
        return f"{self.name} ({self.dating})"
    
    with open(CAFEDRA_MAP_FILE, encoding='utf8') as f:
        Cafedra_name_map = json.load(f)

    @classmethod
    def get_cafedra_name_in_episkop(cls, caf_td: str):
        caf_td = caf_td.replace('?', '')        
        caf_td = re.sub(r'^\s*\(?\s*в\s*/\s*у\s*\)?\s*', '', caf_td)            
        caf_td = caf_td.replace('()', '')
        caf_td = re.sub(r',\s*((паки)|(в \d-й раз))\s*$', '', caf_td)
        caf_td = caf_td.strip()

        res = cls.Cafedra_name_map.get(caf_td)
        if not res:
            caf_td = re.sub(r',\s*обн\.?\s*$', ', обновленческая', caf_td)
            caf_td = re.sub(r',\s*григ\.?\s*$', ', григорианская', caf_td)
            caf_td = re.sub(r',\s*\(ПАПЦ\)\.?\s*$', ', (Польская автокефальная православная церковь)', caf_td)
            res = caf_td

        return res


class CafedraView:
    """
    Структурированное представление html данных кафедры
    """
    def __init__(self, data: TextCafedra):
        self._text = data
        self._tree = html.fragment_fromstring(data.html)

    def has_name(self, name: str):
        return name.lower().strip() == self._text.header()
        # TODO other names...

    @property
    def episkops(self) -> list['EpiskopRowView']:
        # отбираем строки таблицы епископов, которые не являются заголовками
        rows = self._tree.xpath("""//table[contains(@class, 'episkops')]/tbody/tr[not(contains(@class, 'header-row'))]""")
        return [EpiskopRowView(r) for r in rows]
    

class EpiskopRowView:
    """
    Структурированное представление строки таблицы епископов в html кафедры
    """
    def __init__(self, tr: html.HtmlElement):
        self.d = tr
        self.ep = tr[-1]
        assert self.ep.tag == 'td'

        self._header = None
        self._parsed = None
 
    @property
    def header(self):
        if not self._header:
            # берем только текстовые узлы, все теги игнорируем
            # todo игнорировать только span fnote
            text = ''.join(self.ep.xpath('text()'))
            #from parsers.episkop import parse_episkop_name_in_cafedra
            self._header = text
        return self._header
    
    @property
    def parsed(self):
        if not self._parsed:
            from parsers.episkop import parse_episkop_name_in_cafedra
            self._parsed = parse_episkop_name_in_cafedra(self.header)
        return self._parsed

    @property
    def begin_dating(self):
        return self.d[0].text_content().strip()

    @property
    def end_dating(self):
        return self.d[1].text_content().strip()
    
    
    @property
    def link(self):
        return None  # TODO now no links
    
    def __repr__(self):
        return f"EpiskopRow({self.begin_dating} - {self.end_dating} {self.header})"
    
    def __str__(self):
        return f"{self.header} ({self.begin_dating} - {self.end_dating})"


    
if __name__ == '__main__':
    # check_episkop_to_cafedra_links(remove_old_tasks=True)


    #st = HierarhEditStorage()
    #st.episkop_index.rebuild()
    check_cafedra_to_episkop_links(True)