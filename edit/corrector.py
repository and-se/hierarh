from collections import defaultdict

from pathlib import Path
from pprint import pprint
import sys
import logging
from typing import Any, DefaultDict

if __name__ == '__main__':
    # ищем модули начиная с корня проекта (папка hierarh)
    sys.path.append(str(Path(__file__).parent.parent.absolute()))


from edit.text_view import TEXT_VIEW_LOG_NAME, CafedraView, EpiskopView
from edit.storage import HierarhEditStorage
from parsers.fail import ParseFail


def main():
    # В корневой лог прилетают все сообщения из дочерних (т.е. вообще всех) логов, 
    # которые в своём логе (куда их отправили) прошли по logLevel.
    # У новых логов logLevel=UNSET, т.е. смотри родителя.
    # В крайнем случае цепочка докатится до корневого, у него по умолчанию WARNING
    # Но вот если у нашего лога явно выставлен logLevel ниже,
    # то всё подошедшее прилетит в корневой лог
    rt = logging.getLogger()
    fmt = logging.Formatter(logging.BASIC_FORMAT)
    
    # файловый обработчик все прилетевшие в него сообщения пишет в файл
    log_file = logging.FileHandler('corrector.log', 'w')
    log_file.setFormatter(fmt)
    rt.addHandler(log_file)

    # А обработчик консоли берёт только WARNING и выше
    # logLevel обработчика не связан с logLevel самого лога.
    strm = logging.StreamHandler()
    strm.setFormatter(fmt)
    strm.setLevel(logging.WARNING)
    rt.addHandler(strm)

    rt.warning("Ошибки в данных логируются в 'data-errors.log'")
    data_errors = logging.getLogger(TEXT_VIEW_LOG_NAME)
    data_errors.propagate = False
    data_errors.setLevel(logging.DEBUG)
    data_errors.addHandler(logging.FileHandler('data-errors.log', 'w'))

    if len(sys.argv) != 2:
        print(f"""usage: {sys.argv[0]}  CMD
              index - rebuild episkop index
              cafedra - process cafedra articles
              """)
        return
    cmd = sys.argv[1]

    # плохая идея, т.к. добавляет в корневой лог вывод на экран вообще всего
    # прилетевшего из дочерних (если вдруг в дочернем logLevel=DEBUG, это посыпется на экран)
    #logging.basicConfig()
    
    # check_episkop_to_cafedra_links(remove_old_tasks=True)
       
    if cmd == 'index':
        rt.setLevel(logging.INFO)
        strm.setLevel(logging.INFO)
        print("Rebuild episkop index")
        st = HierarhEditStorage()
        st.episkop_index.rebuild()
        return

    if cmd != 'cafedra':
        print("Bad cmd")
        return
    
    DEBUG_TASKS = True
    if DEBUG_TASKS:
        from task import TASK_LOG_NAME
        tlog = logging.getLogger(TASK_LOG_NAME)
        # В корневой лог прилетят все сообщения из tlog, даже DEBUG.
        # Но мы правильно настроили обработчики выше
        tlog.setLevel(logging.DEBUG)            
        tlog.warning("DEBUG_TASKS=TRUE!!!! ЗАДАЧИ ЛОГИРУЮТСЯ в файл tasks.txt!")
        
    totals = check_cafedra_to_episkop_links(True)
    pprint(totals)


def create_tasks_for_coll(db: HierarhEditStorage, coll_name: str, doc_processor, task_type: str, remove_old_tasks: bool):
    """
    Перебирает документы коллекции coll_name и добавляет задачи

    Функция doc_processor(doc, task, db) получает 
    документ коллекции, пустую задачу, соединение с БД и словарь stats для итоговой статистики
    (в stats автоматически добавляются неизвестные ключи со значением 0).
    Должна добавить в задачу проблемы при помощи Task.add_problem, 
    а также задать заголовок задачи Task.title

    Есть проблемы в задачу не добавлены, то задача для документа не создаётся.
    """

    coll = db.get_coll(coll_name)
    stats = defaultdict(int)
    
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
        doc_processor(doc, task, db, stats)

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

    def episkop_proccessor(ep, task, db: HierarhEditStorage, stats):
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
    return create_tasks_for_coll(db, 'episkop', episkop_proccessor, "episkop->cafedra", remove_old_tasks)


"""Проверка ссылок на епископов в статьях кафедр"""
def cafedra_processor(caf, task, db: HierarhEditStorage, stats: defaultdict):
    task.title = caf.header() + " - непонятные ссылки на епископов"        
    caf: CafedraView = CafedraView(caf)

    for i, ep in enumerate(caf.episkops):
        stats['всего строк о епископах']+=1
        if ep.link:
            linked = db.episkop.get(ep.link)
            stats['плохая ссылка']+=1
            if not linked:
                task.add_problem(i, ep, 'сломанная ссылка - нет такого епископа', ep.link)
            else:
                raise NotImplementedError
                #linked = EpiskopView(linked)
                #if not linked.has_name(ep.name):
                #    task.add_problem(i, ep, 'Проставлена ссылка на епископа', linked.name, 'Это верно?')
        else:
            if ep.episkop == 'NN':
                # не нужно проставлять ссылки на ?, NN
                continue

            parsed_ep = ep.parsed_episkop
            if isinstance(parsed_ep, ParseFail):                    
                stats['ошибка разбора']+=1
                task.add_problem(i, ep, 'Ошибка разбора', parsed_ep)
                continue

                '''
                found_ep = db.episkop.find_by_name(ep.episkop)
                if not found_ep:
                    stats['ошибка разбора']+=1
                    continue
                '''
            else:
                min_year, max_year = ep.get_min_max_year()
                found_ep = db.episkop_index.find_by_fields(parsed_ep.name, parsed_ep.surname, 
                                                        begin_year=min_year, end_year=max_year,
                                                        cafedra=caf.header)                    
                if not found_ep and (min_year or max_year):
                    found_ep = db.episkop_index.find_by_fields(parsed_ep.name, parsed_ep.surname)
                                                        
            #found_ep = db.episkop.find_by_name(ep.header)

            if len(found_ep) == 1:
                ... # проставить ссылку на епископа
            elif not len(found_ep):
                stats['епископ не найден']+=1
                task.add_problem(i, ep, "епископ не найден")
            else: # many cafedra
                stats['какой именно епископ?']+=1
                task.add_problem(i, ep, "какой именно епископ?", [f"{x.header} (#{x.doc_key})" for x in found_ep])


def check_cafedra_to_episkop_links(remove_old_tasks):    
    return create_tasks_for_coll(HierarhEditStorage(), 'cafedra', cafedra_processor, 
                                 "episkop->cafedra", remove_old_tasks)



if __name__ == '__main__':
    main()
    