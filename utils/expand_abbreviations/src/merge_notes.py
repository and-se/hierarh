import json


# Загрузка данных из файлов
def load_json(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        return json.load(file)


# Сохранение результата в файл
def save_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


# Объединение двух массивов
def merge_arrays(file1, file2):
    array1 = load_json(file1)
    array2 = load_json(file2)
    print(len(array1), len(array2))
    merged_array = []

    # Добавляем элементы из первого массива, если они не во втором
    i = 0
    while i < len(array1):
        array1[i]["notes"] = array2[i]
        merged_array.append(array1[i])
        i += 1

    return merged_array


# Пути к файлам
file1_path = '../output/articles_to_process_part2.json'
file2_path = '../output/notes+split.json'
result_path = '../output/articles_to_process_merged.json'

# Объединение массивов и сохранение результата
merged_array = merge_arrays(file1_path, file2_path)
save_json(merged_array, result_path)

print(f"Результат был успешно сохранен в файл: {result_path}")
