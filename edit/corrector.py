import os
import sys

if __name__ == '__main__':
    sys.path.append(os.getcwd())

from edit.text_view import CafedraView, EpiskopView


import logging
logging.basicConfig()

from edit.storage import HierarhEditStorage

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

    def episkop_proccessor(ep, task, db: HierarhEditStorage):
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
    def cafedra_processor(caf, task, db: HierarhEditStorage):
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
                if ep.episkop == 'NN':
                    # не нужно проставлять ссылки на ?, NN
                    continue

                parsed_ep = ep.parsed_episkop
                if isinstance(parsed_ep, ParseFail):
                    task.add_problem(i, ep, 'Ошибка разбора', parsed_ep)
                    continue
                
                found_ep = db.episkop_index.find_by_fields(parsed_ep.name, parsed_ep.surname, 
                                                           begin_year=ep.begin_year, end_year=ep.end_year)
                #found_ep = db.episkop.find_by_name(ep.header)

                if len(found_ep) == 1:
                    ... # проставить ссылку на епископа
                elif not len(found_ep):
                    task.add_problem(i, ep, "епископ не найден")
                else: # many cafedra
                    task.add_problem(i, ep, "какой именно епископ?", [f"{x.header} (#{x.id})" for x in found_ep])
    
    create_tasks_for_coll(HierarhEditStorage(), 'cafedra', cafedra_processor, "episkop->cafedra", remove_old_tasks)




    
if __name__ == '__main__':
    # check_episkop_to_cafedra_links(remove_old_tasks=True)


    '''print("Rebuild episkop index")
    st = HierarhEditStorage()
    st.episkop_index.rebuild()'''
    check_cafedra_to_episkop_links(True)