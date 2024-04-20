def load_abbreviations(filename):
    abbreviations = {}
    with open(filename, 'r', encoding='utf-8') as file:
        for line in file:
            parts = line.strip().split(' – ')
            if len(parts) == 2:
                abbreviations[parts[0]] = parts[1]
    # print(abbreviations)
    return abbreviations

def find_abbreviations_in_text(text, abbreviations):
    words = text.split()
    found_abbreviations = {}
    for word in words:
        if word in abbreviations:
            found_abbreviations[word] = abbreviations[word]
    return found_abbreviations

# Загрузка словаря сокращений
abbreviations = load_abbreviations('../abbreviations.txt')

# Чтение текста для проверки
with open('../output/episkops3.json', 'r', encoding='utf-8') as file:
    text = file.read()

# Поиск сокращений в тексте
found_abbreviations = find_abbreviations_in_text(text, abbreviations)

# Вывод результатов
for abbreviation, full_form in found_abbreviations.items():
    print(f'{abbreviation} – {full_form}')
