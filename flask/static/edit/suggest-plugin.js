'use strict';

/**
 * Задаваемая пользователем логика работы подсказки
 */
function CafedraSuggestController() {
    /**
     * На основе анализа выделенной части текста возвращает запрос для getMatches
     * @param {Range} range - редактируемый фрагмент текста
     */
    this.getMatchQuery = (range) => {
        let cell = getEditedCell(range);

        if (cell) {
            let tr = cell.closest('tr');
            // подсказывать нужно только первую колонку - где названия кафедр
            if (tr.firstElementChild != cell) return;
        }
        
        let txt = cell?.innerText || '';
        const onlyCapitalWords = /[А-ЯЁA-Z][А-ЯЁA-Zа-яёa-z]+/g;
        // Возвращаем слова с большой буквы через пробел
        return (txt.match(onlyCapitalWords) || []).join(' ')
    }

    /**
     * список подсказок в виде массива строк либо объектов (можно Promise)
     * Для объектов обязательно свойство value - это будет текст подсказки.
     * @param {*} query запрос (см. getMatchQuery)
     */
    this.suggestFunc = async (query) => {
        /*return [
            {key: 1, value: 'Иван Иванович'},
            {key: 2, value: 'Петр Петрович'},
            {key: 3, value: 'Семён Семёнович'}
        ]*/

        if (!query.trim()) {
            return []
        }

        return await fetch("/edit/suggest/cafedra?" + new URLSearchParams({ query: query }),
            { /*signal: cancel,*/ credentials: 'include' })                
            .then(resp => resp.json())
    }

    /**
     * Проверяет, что полученный из suggestFunc объект obj является текущей выбранной подсказкой
     * @param {*} obj - подсказка
     * @param {*} range - текущий редактирумый фрагмент текста
     * @returns 
     */
    this.isCurrentSelected = (obj, range) => {
        let cell = getEditedCell(range)

        if (cell && obj.key && cell.dataset.ref == "cafedra/" + obj.key) {
            return true;
        }
    }


    /**
     * Вставлят подсказку в текст
     * @param {*} suggestItem - выбранная подсказка (объект или строка)
     * @param {*} range - редактируемая часть текста
     */
    this.insertSuggestion = (suggestItem, range) => {
        console.debug('insert', suggestItem, range);

        if (!suggestItem.key || !suggestItem.value) {
            throw new Error(`Bad suggest (no key/value) ${JSON.stringify(suggestItem)}`)
        }

        let sel = document.getSelection();
        /*if (!sel.containsNode(range.startContainer, true)) {
            console.error("Неожиданное выделение ", sel, "при вставке подсказки в", range)
            return;
        }*/

        let cell = getEditedCell(range);
        

        cell.dataset.ref="cafedra/" + suggestItem.key;

        
        /* После добавления и удаления строки может быть несколько подряд идущих textNode
           Посему слово может быть разорвано между несколькими textNode.
           Чтобы с этим не возиться, лучше воспользоваться встроенными в браузер средствами
           модификации выделения.
        */
        // ставим курсор в начало слова
        // (если уже был в начале слова - будет баг что заменят предыдущее)
        sel.modify("move", "left", "word")
        // идём вправо на одно слово и всё выделяем
        sel.modify("extend", "right", "word")
        
        let word = sel.getRangeAt(0);
        if (word) {
            word.deleteContents()
            word.insertNode(document.createTextNode(suggestItem.value))
            sel.collapseToEnd();
        }
    }

    /**
     * Возвращает текущую редактируемую ячейку таблицы
     * @param {Range} range 
     * @returns {Element}
     */
    function getEditedCell(range) {
        let el = range.startContainer;
        if (el.nodeType == Node.TEXT_NODE) el = el.parentElement;
        return el.closest('td')
    }
}


/**
 * Плагин для вывода подсказки при вводе текста.
 * @param {SuggestController} suggestController - ползовательская логика подсказки
 */
function SuggestPlugin(suggestController){
    if (!suggestController) {
        throw new Error(`Expected suggest controller`)
    }
    for (const item of ['getMatchQuery', 'suggestFunc', 'insertSuggestion']) {
        if (!suggestController[item]) {
            throw new Error(`Bad controller: not function ${item}`)
        }
    }

    this.controller = suggestController;

    const PREFIX = "__suggest_plugin_";

    const STYLE = `
    .${PREFIX}suggest {
        position: absolute;

        background: white;
        border: 1px solid #ddd;        
        border-radius: 4px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        
        line-height: 1.5;

        max-width: 300px;
        max-height: 200px;
        overflow-y: scroll;
        
        z-index: 1000;
        user-select: none;

        .item {
            cursor: pointer;            
            padding: 0 5px;
            border-radius: 4px;
            transition: background-color 0.2s;
        }

        .item:hover, .suggestion-active {
            background-color: #579bdf;
            color: white;
        }

        .current {
            border: 2px solid #cf002dff;
            border-radius: 5px;
        }
    }
    `

    this.init = (menuSlot) => {
        if (!document.querySelector("head style[data-plugin='SuggestPlugin']")) {
            let hstyle = document.createElement('style')
            hstyle.dataset.plugin = "SuggestPlugin";
            hstyle.textContent = STYLE;
            document.head.appendChild(hstyle);
        }

        this.suggestBox = LIB.createElementByHtml(`
            <div class="${PREFIX}suggest" style="display: none"></div>`);

        this.suggestBox.addEventListener('click', (ev) => {
            let item = ev.target.closest('.item');
            if (item) {
                insertSuggestion(item)
            }
        })

        this.activeSuggestionIndex = null;
        
        document.body.appendChild(this.suggestBox);
    }
    
    this.registerEditor = (editor) => {
        editor.root.addEventListener('keydown', handleInput); // Ввод, а также управление с клавиатуры
        editor.root.addEventListener('mouseup', handleInput); // При клике мышью
        editor.root.addEventListener('touchend', handleInput);
        //editor.root.addEventListener('focus', handleInput); // Подсказка не в том месте при клике мышкой!
        
        if (!this.editors) {
            this.editors = [];
        }
        this.editors.push(editor);
    }

    const suggestionEventDebounced = LIB.debounce((e) => suggestionEvent(e), 500); // задержка 300 мс перед обработкой

    function handleInput(e) {
        if (handleSuggestionKeyboard(e) == 'stop') {
            return;
        }

        suggestionEventDebounced(e);
    }

    // Основной обработчик событий
    const suggestionEvent = async (e) => {
        const query = this.controller.getMatchQuery(document.getSelection().getRangeAt(0));
        if (query) {
            console.debug("get matches for query", query)
            const matches = await this.controller.suggestFunc(query)
            showSuggestions(matches);
        } else {
            hideSuggestions();
        }
    }

    // Обработчик клавиатурных событий
    const handleSuggestionKeyboard = (e) => {
        if (this.suggestBox.style.display === 'none') return;
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                if (this.activeSuggestionIndex == null) this.activeSuggestionIndex = -1;
                this.activeSuggestionIndex = (this.activeSuggestionIndex + 1) %
                    this.suggestBox.children.length;
                highlightActiveSuggestion();
                break;
            case 'ArrowUp':
                e.preventDefault();
                this.activeSuggestionIndex = (this.activeSuggestionIndex - 1 +
                    this.suggestBox.children.length) % this.suggestBox.children.length;
                highlightActiveSuggestion();
                break;

            case 'Enter': /* вставка подсказки*/
                if (this.activeSuggestionIndex == null) return;
                
                e.preventDefault();
                
                // Удаляем br, вставленный CONTENT_EDITABLE_TOOLS.insertBrOnEnterInsteadOfDiv
                CONTENT_EDITABLE_TOOLS.removePreviousBrIfExists();

                if (this.activeSuggestionIndex >= 0) {
                    const selectedSuggest = this.suggestBox.children[this.activeSuggestionIndex];
                    if (selectedSuggest) {
                        insertSuggestion(selectedSuggest);
                    }
                }
                break;

            case 'Escape':
                e.preventDefault();
                hideSuggestions()
                break;

            default:
                return 'not keyboard'
                ;
        }
        return 'stop';
    }

    // Функция показа подсказки
    const showSuggestions = (matches) => {
        /*if (!matches || matches.length === 0) {
            hideSuggestions();
            return;
        }*/

        this.activeSuggestionIndex = null;

        const tags = matches.map((obj, i) => {
            let d = document.createElement('div')
            d.classList.add('item')
            d.dataset.index = i;
            d.innerText = obj.value;
            d[PREFIX+'suggest_obj'] = obj

            if (this.controller.isCurrentSelected(obj, document.getSelection().getRangeAt(0))) {
                d.classList.add('current');
            }
            
            return d;
        })

        this.suggestBox.innerHTML = "";
        this.suggestBox.append(...tags);

        let [cursorX, cursorY] = getUnderCursorPosition();

        if (cursorX == 0) {
            //debugger;
            console.warn("TODO bug: not correct cursor position - don't show suggestions")
            return;
        }

        // Позиционируем подсказку рядом с курсором
        this.suggestBox.style.left = `${cursorX + 5}px`;
        this.suggestBox.style.top = `${cursorY + 1}px`;
        this.suggestBox.style.display = 'block';
    }

    const insertSuggestion = (itemElem)  => {
        this.controller.insertSuggestion(itemElem[PREFIX + 'suggest_obj'], document.getSelection().getRangeAt(0));
        hideSuggestions();
    }

    const highlightActiveSuggestion = () => {
        const items = this.suggestBox.querySelectorAll('.item');

        items.forEach((item, index) => {
            if (index === this.activeSuggestionIndex) {
                item.classList.add('suggestion-active');
                item.scrollIntoView({container:'nearest', block: 'center', behavior: 'smooth'})
            } else {
                item.classList.remove('suggestion-active');
            }
        });
    }

    const hideSuggestions = () => {
        this.suggestBox.style.display= 'none';
        this.activeSuggestionIndex = null;
    }


    function getUnderCursorPosition() {
        const selection = window.getSelection();
        if (!selection.rangeCount) return;

        const range = selection.getRangeAt(0);
        const rect = range.getBoundingClientRect();

        return [rect.right + window.pageXOffset, rect.bottom + window.pageYOffset]
    }

}

