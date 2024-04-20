import json

MAX_TEXT_LENGTH = 6300  # Это примерно полторы страницы текста

input_file_path = '../input/articles.json'
output_file_path = '../input/articles_large.json'

try:
    with open(input_file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

    group_of_large_elements = []

    for index, item in enumerate(data):
        item_text = json.dumps(item, ensure_ascii=False)
        item_length = len(item_text)

        if item_length > MAX_TEXT_LENGTH:
            group_of_large_elements.append(item)

except FileNotFoundError:
    print("Файл не найден.")
except json.JSONDecodeError:
    print("Ошибка в формате JSON.")

with open(output_file_path, 'w', encoding='utf-8') as file:
    json.dump(group_of_large_elements, file, ensure_ascii=False, indent=4)

