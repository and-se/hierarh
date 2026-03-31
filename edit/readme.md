# Построение БД редактирования

1. Положить в `data/edit-init` файлы `cafedra-edit.json`, `cafedra-exp-abbrs-edit.json`, `map-origin-expanded-cafedra.json` и `episkop-edit.json`.
1. Преобразовать json в html командой `python edit/init_db_creator.py json`
1. Если ошибок нет - загрузить html в БД командой `python edit/init_db_creator.py db`

# Расстановка ссылок на епископов и кафедры

Предварительно построить индекс епископов командой `python edit/corrector.py index`

Обработаем статьи кафедр - расставим ссылки на епископов, а для спорных случаев сгенерируем задачи для ручной обработки. Выполнить команду `python corrector.py cafedra`. В конце работы скрипта надо согласиться на внесение изменений в БД.

Такожде и для статей епископов расставим ссылки на кафедры - команда `python edit/corrector.py episkop`
