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
def merge_arrays(file1, file2, file3):
    array1 = load_json(file1)
    array2 = load_json(file2)
    array3 = load_json(file3)
    print(len(array1), len(array2), len(array3))
    merged_array = []

    # Добавляем элементы из первого массива, если они не во втором
    i = 0
    j = 0
    k = 0
    while i < len(array1):
        if array1[i]["start_line"] == array2[j]["start_line"]:
            merged_array.append(array2[j])
            i = i + 1
            j = j + 1
        elif array1[i]["start_line"] == array3[k]["start_line"]:
            merged_array.append(array3[k])
            i = i + 1
            k = k + 1
        else:
            print('merge exception', i, j, k)
    print(len(merged_array))
    return merged_array


# Пути к файлам
file1_path = '../production/articles.json'
file2_path = '../production/articles+.json'
file3_path = '../production/articles_large+.json'
result_path = '../production/articles+prod.json'

# Объединение массивов и сохранение результата
merged_array = merge_arrays(file1_path, file2_path, file3_path)
save_json(merged_array, result_path)

print(f"Результат был успешно сохранен в файл: {result_path}")
