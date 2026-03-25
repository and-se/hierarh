'use strict';


class BaseSuggestController {
    /**
     * На основе анализа выделенной части текста возвращает запрос для {@link suggestFunc}
     * @param {Range} range - редактируемый фрагмент текста     * 
     * @returns Запрос для {@link suggestFunc} или ничего, 
     * если в данном контексте (range) подсказку показывать не надо
     */
    getMatchQuery(range) {
        throw new TypeError('Метод надо реализовать в подклассе')
    }

    /**
     * список подсказок в виде массива строк либо объектов (можно Promise)
     * Для объектов обязательно свойство value - это будет текст подсказки.
     * @param {*} query запрос (см. {@link getMatchQuery})
     */
    suggestFunc(query) {
        throw new TypeError('Метод надо реализовать в подклассе')
    }

    /**
     * Вставлят подсказку в текст
     * @param {*} suggestItem - выбранная подсказка (объект или строка)
     * @param {*} range - редактируемая часть текста
     */
    applySuggestion(suggestItem, range) {
        throw new TypeError('Метод надо реализовать в подклассе')
    }

    /**
     * Возвращает данные ранее применённой для этого места текста подсказки.
     * Например, если при выборе подсказки проставляется ссылка, надо вернуть сведения о ссылке
     * @param {Range} range 
     * @returns объект с полями key и value
     */
    getAppliedSuggestion(range) {}

    /**
     * Удаляет связь текста с ранее применённой подсказкой.
     * Например, если выбор подсказки проставляет ссылку куда-либо - этот метод ссылку удаляет.
     * @param {Range} range 
     */
    clearAppliedSuggestion(range) {}

    /**
     * Ссылка на дополнительную информацию для подсказки
     * @param {*} suggestItem - подсказка, для которой ищется доп. информация
     * @returns гиперссылка на доп. информацию
     */
    getAdditionalInfoLink(suggestItem) {}
}

/**
 * Логика работы подсказки для выбора кафедры
 */
class CafedraSuggestController extends BaseSuggestController {
    _suggestFetcher = new LIB.SingleFetchManager("suggest");
    _headFetcher = new LIB.SingleFetchManager("head")

    getMatchQuery(range) {
        let el = range.startContainer;
        if (el.nodeType == Node.TEXT_NODE) el = el.parentElement;
        if (el.closest('.fnote')) return; // внутри сноски подсказку не показываем
        
        let cell = this.getEditedCell(range);
        if (cell) {
            let tr = cell.closest('tr');
            // подсказывать нужно только первую колонку - где названия кафедр
            if (tr.firstElementChild != cell) return;
        }
        
        let txt = cell?.innerText || '';

        // если только одно слово, то по нему и ищем
        if (!txt.trim().includes(' ')) return txt;

        // Ищем только по словам с большой буквы
        const onlyCapitalWords = /[А-ЯЁA-Z][А-ЯЁA-Zа-яёa-z]+/g;
        // выпишем такие слова через пробел
        return (txt.match(onlyCapitalWords) || []).join(' ')
    }

    async suggestFunc(query) {
        if (!query.trim()) {
            return []
        }

        return await this._suggestFetcher.fetch("/edit/suggest/cafedra?" + new URLSearchParams({ query: query }),
            { credentials: 'include' })                
            .then(resp => resp.json())
    }

    applySuggestion(suggestItem, range) {
        console.debug('insert', suggestItem, range);

        if (!suggestItem.key || !suggestItem.value) {
            throw new Error(`Bad suggest (no key/value) ${JSON.stringify(suggestItem)}`)
        }
        
        let cell = this.getEditedCell(range);
        cell.dataset.ref="cafedra#" + suggestItem.key;
        cell.__tmpRefName = suggestItem.value;
        
        let sel = SuggestHelpers.selectCurrentWordInCell(cell)        
        if (sel) {
            let word = sel.getRangeAt(0);        
            word.deleteContents()
            word.insertNode(document.createTextNode(suggestItem.value))
            // fixme no undo...
            // not work... document.execCommand('insertText', suggestItem.value);
            sel.collapseToEnd();
        }        
    }

    async getAppliedSuggestion(range) {
        const cell = this.getEditedCell(range);

        if (cell && cell.dataset.ref) {
            const key = cell.dataset.ref.split('#')[1]

            if (!key) return;

            if (!cell.__tmpRefName) {
                cell.__tmpRefName = await this._headFetcher.fetch("/edit/cafedra/" + key + '/json',
                                    { credentials: 'include' })                
                .then(resp => resp.json())
                .then(d => {                    
                    if (d.success) {
                        return d.data.header
                    } else {
                        throw new Error(json.message)
                    }
                })
            }
            
            return {key: key, value: cell.__tmpRefName}
        }
    }

    clearAppliedSuggestion(range) {
        const cell = this.getEditedCell(range);

        if (cell && cell.dataset.ref) {
            delete cell.dataset.ref;
        }
    }
    
    getAdditionalInfoLink(suggestItem) {
        if (suggestItem.key) {
            return "/edit/cafedra/" + suggestItem.key
        }        
    }

    /**
     * Возвращает текущую редактируемую ячейку таблицы
     * @param {Range} range 
     * @returns {Element}
     */
    getEditedCell(range) {
        let el = range.startContainer;
        if (el.nodeType == Node.TEXT_NODE) el = el.parentElement;
        return el.closest('td')
    }

}

class SuggestHelpers {
     static selectCurrentWordInCell(cell) {
        /* После добавления и удаления строки может быть несколько подряд идущих textNode
           Посему слово может быть разорвано между несколькими textNode.
           Чтобы с этим не возиться, лучше воспользоваться встроенными в браузер средствами
           модификации выделения.

           Но надо не выйти за границы тега при перемещении курсора!
        */

        let sel = document.getSelection();

        // выделение должно быть курсором и содержать интересующую ячейку
        if (!sel.rangeCount || !sel.isCollapsed) return null;
        if (!sel.containsNode(cell, true)) return null;

        // пустая ячейка слов не содержит - оставляем пустое выделение
        if (!cell.innerText.trim()) return sel;

        if (this.isCursorAtStartOfElem(cell)) {
            // если мы в начале текста - двигаемся вправо, чтбобы не выйти за границы ячейки
            sel.modify("move", "right", "word")
            sel.modify("extend", "left", "word");
        } else {
            // иначе ставим курсор в начало слова
            // (если уже был в начале слова - будет баг что заменят предыдущее)
            sel.modify("move", "left", "word")
            // идём вправо на одно слово и всё выделяем
            sel.modify("extend", "right", "word")
        }
        
        return sel;
    }

    static isCursorAtStartOfElem(elem) {
        const selection = document.getSelection();
        if (selection.rangeCount === 0) return false;

        const range = selection.getRangeAt(0);
        const preSelectionRange = range.cloneRange();
        preSelectionRange.selectNodeContents(elem);
        preSelectionRange.setEnd(range.startContainer, range.startOffset);

        return preSelectionRange.toString().length === 0;
    }
}

/**
 * Плагин для вывода подсказки при вводе текста.
 * @param {BaseSuggestController} suggestController - ползовательская логика подсказки
 */
function SuggestPlugin(suggestController){
    if (! (suggestController instanceof BaseSuggestController &&
           Object.getPrototypeOf(suggestController) != BaseSuggestController.prototype)
     ) {
        throw new Error(`Expected suggest controller as subclass of BaseSuggestController`)
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

            .add-info {
                visibility: hidden;
                padding-left: 15px;
            }

        }

        .item:hover, .suggestion-active {
            background-color: #579bdf;
            color: white;

            .add-info {
                visibility: visible;
            }
        }

        .current {
            border: 2px solid #cf002dff;
            border-radius: 5px;

            a {
                text-decoration: none;
            }
        }


        .right-btn {
            float:right;
            cursor:pointer
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

        this.suggestRoot = LIB.createElementByHtml(`
            <div class="${PREFIX}suggest" style="display: none">
                <div class="header"></div>
                <div class="items"></div>
            </div>
        `)

        this.suggestHeader = this.suggestRoot.querySelector('.header');
        this.suggestList = this.suggestRoot.querySelector('.items');

        /*this.suggestBox = LIB.createElementByHtml(`
            <div class="${PREFIX}suggest" style="display: none"></div>`);
        */

        this.suggestRoot.addEventListener('click', (ev) => {
            if (ev.target.closest('.add-info')) return;

            let item = ev.target.closest('.item');
            if (item) {
                insertSuggestion(item)
            }
        })

        this.activeSuggestionIndex = null;
        
        document.body.appendChild(this.suggestRoot);

        document.addEventListener('click', e => {
            for(let ed of this.editors) {
                if (ed.root.contains(e.target)) return;
            }

            console.debug('hide suggestion on click out')
            hideSuggestions();
        })
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
            try {
                const matches = await this.controller.suggestFunc(query)
                showSuggestions(matches);
            } catch (err) {
                console.debug("Fail get suggestions", err);
            }
        } else {
            // подсказка в данном контексте не нужна
            hideSuggestions();
        }
    }

    // Обработчик клавиатурных событий
    const handleSuggestionKeyboard = (e) => {
        if (this.suggestRoot.style.display === 'none') return;
        switch (e.code) {
            case 'ArrowDown':
                if (this.suggestList.childElementCount==0) return;
                e.preventDefault();
                if (this.activeSuggestionIndex == null) this.activeSuggestionIndex = -1;
                this.activeSuggestionIndex = (this.activeSuggestionIndex + 1) %
                    this.suggestList.children.length;
                highlightActiveSuggestion();
                break;
            case 'ArrowUp':
                if (this.suggestList.childElementCount==0) return;
                e.preventDefault();
                this.activeSuggestionIndex = (this.activeSuggestionIndex - 1 +
                    this.suggestList.children.length) % this.suggestList.children.length;
                highlightActiveSuggestion();
                break;

            case 'Enter': /* вставка подсказки*/
                if (this.activeSuggestionIndex == null) return;
                
                e.preventDefault();
                
                // Удаляем br, вставленный CONTENT_EDITABLE_TOOLS.insertBrOnEnterInsteadOfDiv
                CONTENT_EDITABLE_TOOLS.removePreviousBrIfExists();

                if (this.activeSuggestionIndex >= 0) {
                    const selectedSuggest = this.suggestList.children[this.activeSuggestionIndex];
                    if (selectedSuggest) {
                        insertSuggestion(selectedSuggest);
                    }
                }
                break;

            case 'Escape':
                e.preventDefault();
                hideSuggestions()
                break;
            
            case 'Delete':
                if (e.altKey) {
                    e.preventDefault();
                    this.controller.clearAppliedSuggestion(document.getSelection().getRangeAt(0));
                }
                break;
            
            case 'KeyL':
                if (e.altKey) {
                    e.preventDefault();

                    if (this.activeSuggestionIndex == null) {
                        this.suggestHeader.querySelector('.current a')?.click();
                    } else {
                        this.suggestList.children[this.activeSuggestionIndex]?.querySelector('a.add-info')?.click();
                    }
                }
                break;
                
            default:
                return 'not keyboard';
        }
        return 'stop';
    }

    // Функция показа подсказки
    const showSuggestions = async (matches) => {
        this.activeSuggestionIndex = null;

        const tags = matches.map((obj, i) => {
            let d = document.createElement('div')
            d.classList.add('item')
            d.dataset.index = i;
            d.innerText = obj.value;
            d[PREFIX+'suggest_obj'] = obj

            let href = this.controller.getAdditionalInfoLink(obj)
            if (href) {
                let a = LIB.createElementByHtml(`
                    <a class="add-info" target="_blank" title="подробнее Alt+L">ℹ️</a>
                    `)
                a.setAttribute('href', href)
                d.append(a)
            }
            
            return d;
        })

        this.suggestList.innerHTML = "";
        this.suggestList.append(...tags);

        this.suggestHeader.innerHTML = '';
        const headObj = await this.controller.getAppliedSuggestion(document.getSelection().getRangeAt(0));
        if(headObj) {
            let d = LIB.createElementByHtml(`
            <div class='current'>
                🔗 <a class="txt" target="_blank" title="текущая связь"></a>
                <span class="del right-btn" title="удалить связь Alt+Del">❌</span>
            </div>`)
            let atxt = d.querySelector('.txt');
            atxt.innerText = headObj.value;
            atxt.setAttribute('href', this.controller.getAdditionalInfoLink(headObj) || '');

            d.querySelector('.del').addEventListener('click', ev => {
                ev.preventDefault();
                this.controller.clearAppliedSuggestion(document.getSelection().getRangeAt(0));
                this.suggestHeader.innerHTML = '';
            })
            this.suggestHeader.append(d)
        }

        let [cursorX, cursorY] = getUnderCursorPosition();

        if (cursorX == 0) {
            //debugger;
            console.warn("TODO bug: not correct cursor position - don't show suggestions")
            return;
        }

        // Позиционируем подсказку рядом с курсором
        this.suggestRoot.style.left = `${cursorX + 5}px`;
        this.suggestRoot.style.top = `${cursorY + 1}px`;
        this.suggestRoot.style.display = 'block';
    }

    const insertSuggestion = (itemElem)  => {
        this.controller.applySuggestion(itemElem[PREFIX + 'suggest_obj'], document.getSelection().getRangeAt(0));
        hideSuggestions();
    }

    const highlightActiveSuggestion = () => {
        const items = this.suggestList.querySelectorAll('.item');

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
        this.suggestRoot.style.display= 'none';
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

