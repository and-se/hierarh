import json

MAX_TEXT_LENGTH = 6300  # Это примерно полторы страницы текста

def group_json_elements_by_size(input_file_path):
    """
    Группирует элементы JSON-массива так, чтобы общая длина текста в каждой группе не превышала MAX_TEXT_LENGTH.
    Возвращает список групп, где каждая группа содержит индексы элементов.

    :param input_file_path: Путь к файлу с JSON-массивом.
    :return: Список групп индексов.
    """
    try:
        with open(input_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)

        groups = []
        group_of_large_elements = []
        current_group = []
        current_length = 0

        for index, item in enumerate(data):
            item_text = json.dumps(item, ensure_ascii=False)
            item_length = len(item_text)

            if item_length > MAX_TEXT_LENGTH:
                # Если элемент слишком большой, обрабатываем его отдельно
                group_of_large_elements.append([index])
            elif current_length + item_length > MAX_TEXT_LENGTH:
                # Начинаем новую группу
                groups.append(current_group)
                current_group = [index]
                current_length = item_length
            else:
                # Добавляем индекс элемента в текущую группу
                current_group.append(index)
                current_length += item_length

        # Не забываем добавить последнюю группу, если она не пуста
        if current_group:
            groups.append(current_group)

        return groups, group_of_large_elements
    except FileNotFoundError:
        return "Файл не найден.", ""
    except json.JSONDecodeError:
        return "Ошибка в формате JSON.", ""

input_file_path = '../input/articles.json'

index_groups, index_groups_of_large = group_json_elements_by_size(input_file_path)
print(index_groups)
print(index_groups_of_large)
print(len(index_groups))
print(len(index_groups_of_large))

with open(input_file_path, 'r', encoding='utf-8') as file:
    data = json.load(file)

for i in index_groups_of_large:
    item_text = data[i[0]]['header']
    print(f'{item_text}, len={len(json.dumps(data[i[0]], ensure_ascii=False))}, idx={i[0]}')