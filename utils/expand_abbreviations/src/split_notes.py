import json

# Загрузка данных из файла
def load_json_data(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        return json.load(file)

# Сохранение результатов в файл
def save_to_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

def split_into_blocks(data):
    blocks = []
    current_block = [data[0]]

    for i in range(1, len(data)):
        # Проверка разницы между последовательными номерами
        if data[i]['num'] - data[i-1]['num'] < 0:
            blocks.append(current_block)
            current_block = [data[i]]
        else:
            current_block.append(data[i])
    blocks.append(current_block)  # Добавляем последний блок

    return blocks

# Пример использования
filename = '../output/notes+.json'  # Замените на имя вашего файла
data = load_json_data(filename)
blocks = split_into_blocks(data)

# Для вывода или сохранения результатов
for block in blocks:
    print(json.dumps(block, indent=4, ensure_ascii=False))
save_to_json(blocks, '../output/notes+split.json')
