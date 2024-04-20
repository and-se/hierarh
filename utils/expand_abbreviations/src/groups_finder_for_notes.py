import json
import itertools

MAX_TEXT_LENGTH = 5500  # Это примерно полторы страницы текста

def group_json_elements(input_file_path):
    try:
        with open(input_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        groups = []
        group_of_large_elements = []
        current_group = []
        current_length = 0

        note_data = list(itertools.chain.from_iterable(
                [data[i]['notes'] for i in range(len(data))]))

        with open('../output/notes.json', 'w', encoding='utf-8') as file:
            json.dump(note_data, file, ensure_ascii=False, indent=4)

        for index, item in enumerate(note_data):
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


input_file_path = '../input/articles_large.json'

index_groups, index_groups_of_large_articles = group_json_elements(input_file_path)

print(index_groups)
print(len(index_groups))

print(index_groups_of_large_articles)
print(len(index_groups_of_large_articles))
