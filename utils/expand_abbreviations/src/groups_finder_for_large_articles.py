import json

MAX_TEXT_LENGTH = 6000  # Это примерно полторы страницы текста


def show_article_statistics(input_file_path, index_groups):
    with open(input_file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
        for i in index_groups:
            item_text = [data[j]['header'] for j in i]
            print(f'len={sum([len(json.dumps(data[j]["text"], ensure_ascii=False)) for j in i])}, {item_text}, idxs={i}')


def group_json_elements(input_file_path):
    try:
        with open(input_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        groups = []
        group_of_large_elements = []
        current_group = []
        current_length = 0

        for index, item in enumerate(data):
            item_text = json.dumps(item['text'], ensure_ascii=False)
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
show_article_statistics(input_file_path, index_groups)

print(index_groups_of_large_articles)
print(len(index_groups_of_large_articles))
show_article_statistics(input_file_path, index_groups_of_large_articles)
