import json


def find_largest_object_from_file(file_path):
    try:
        # Открытие и чтение данных из файла
        with open(file_path, 'r', encoding='utf-8') as file:
            json_array = json.load(file)

        max_length = 0
        largest_object = None
        print('json_array_len =', len(json_array))
        print(json_array[1])

        # Проходим по каждому объекту в массиве
        for obj in json_array:
            length = 0

            # Считаем количество символов во всех строковых полях объекта
            for key, value in obj.items():
                if isinstance(value, str):
                    length += len(value)
                elif isinstance(value, list):
                    # Считаем символы в элементах списка, если они строковые
                    for item in value:
                        if isinstance(item, dict):
                            for k, v in item.items():
                                if isinstance(v, str):
                                    length += len(v)

            # Обновляем объект с максимальной длиной
            if length > max_length:
                max_length = length
                largest_object = obj

        return json.dumps(largest_object, ensure_ascii=False, indent=4)

    except FileNotFoundError:
        return "Файл не найден."
    except json.JSONDecodeError:
        return "Ошибка в формате JSON."


file_path = '../input/articles.json'
# print(find_largest_object_from_file(file_path))


def expand_abbreviation(input_text):
    return input_text


def process_json_array(input_file_path, output_file_path, range=range(0, 1)):
    try:
        # Шаг 1: Чтение данных из исходного файла
        with open(input_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)

        # Шаг 2: Выбор элементов в заданном диапазоне
        selected_elements = data

        # Шаг 3: Сохранение в новый массив
        new_data = expand_abbreviation(selected_elements)

        # Шаг 4: Запись в другой файл
        with open(output_file_path, 'w', encoding='utf-8') as file:
            json.dump(new_data, file, ensure_ascii=False, indent=4)

        print("Результат выполнения находится в файле", output_file_path)

        return "Обработка и сохранение данных выполнены успешно."

    except FileNotFoundError:
        return "Файл не найден."
    except json.JSONDecodeError:
        return "Ошибка в формате JSON."
    except Exception as e:
        return f"Произошла ошибка: {e}"



# Пример использования
input_file_path = '../output/articles_to_process.json'
output_file_path = '../output/articles_after_process.json'

print(process_json_array(input_file_path, output_file_path, range=range(1, 4)))
