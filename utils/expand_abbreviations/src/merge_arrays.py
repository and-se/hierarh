import json

def load_json(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        return json.load(file)

def save_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def merge_objects(obj1, obj2):
    # Объединение двух объектов с одинаковым 'header'
    for key in obj2:
        if key not in obj1 or not obj1[key]:
            obj1[key] = obj2[key]
    return obj1

def merge_arrays(arr1, arr2):
    merged_array = []
    for obj1 in arr1:
        for obj2 in arr2:
            if obj1['start_line'] == obj2['start_line']:
                merged_array.append(merge_objects(obj1.copy(), obj2))
                break
    return merged_array

# Предполагается, что файлы находятся в той же директории, что и скрипт
file1_path = '../output/articles_large+.json' # Замените на путь к вашему файлу
file2_path = '../input/articles_large_episkops.json' # Замените на путь к вашему файлу
result_path = '../output/merged_result.json' # Путь для сохранения результата

array1 = load_json(file1_path)
array2 = load_json(file2_path)

merged_array = merge_arrays(array1, array2)
save_json(merged_array, result_path)

print(f"Результат был успешно сохранен в файл: {result_path}")
