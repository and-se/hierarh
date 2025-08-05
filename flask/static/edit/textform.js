'use strict';

function TextForm(root) {
    if (!root) throw new Error("Empty root");
    this.root = root;
    
    this.setMenu = function(m) {
        this.menu = m;        
    }
    
    this.editors = []
    this.addEditor = function(selector, editor) {
        let ed_root = this.root.querySelector(selector)
        if (!ed_root) throw new Error("Can't find elem", selector, "for editor", editor)
        
        editor.bind(this, ed_root);
        this.editors.push(editor)
    }
    
    this.pluginsMap = new Map()
    
    this.start = function() {
        root.classList.add('he-edit-form');
        this.menu.init()
        
        for (let ed of this.editors) {
            if (ed.init) {
                let slot = null
                if (this.menu) {
                    console.log('create MenuSlot for editor', ed.__proto__.constructor.name)
                    slot = this.menu.createSlot()                
                    slot.hide()                   
                } else slot = new MenuSlot(document.createElement('fake'))
                
                ed.menuSlot = slot
                //slot.targetEditor = ed                    
                
                ed.init(slot)                
                initEditorPlugins(this, ed)
            }
            else console.log("Not init() for", ed)
        }
        
        function initEditorPlugins(form, editor) {        
            for (let plug of editor.plugins || []) {                        
                if (form.pluginsMap.has(plug)) {
                    form.pluginsMap.get(plug).push(editor)
                    plug.registerEditor(editor)
                    continue
                } else {
                    form.pluginsMap.set(plug, [editor])
                    let slot = null
                    if (form.menu) {
                        slot = form.menu.createSlot()                
                        console.log('create MenuSlot for plugin', plug.__proto__.constructor.name)
                        slot.hide()                    
                    } else slot = new MenuSlot(document.createElement('fake'))
                    
                    plug.menuSlot = slot                    
                    plug.init(slot)
                    plug.registerEditor(editor)        
                }
            }
        }
        
        //console.log('FORM PLUGINS MAP', this.pluginsMap)
        
        // в зависимсоти от текущей позиции в документе
        // обновляем доступные в меню опции
        document.addEventListener("selectionchange", () => {        
            let r = getSelectionRange()
            if (!r) return
            
            let activePlugins = new Set()
            
            for (let ed of this.editors) {
                if (ed.root.contains(r.commonAncestorContainer)) {
                    //if (ed.isActive) continue
                    //ed.activate(r)                
                    ed.isActive = true
                    ed.menuSlot.show()                    
                    if (ed.plugins) {
                        ed.plugins.forEach(plug => activePlugins.add(plug))
                    }
                } else {
                    //ed.deactivate()
                    ed.isActive = false
                    ed.menuSlot.hide()
                }
                
                //console.log("find active", ed, ed.isActive)
            }
            
            for (let plug of this.pluginsMap.keys()) {
                if (activePlugins.has(plug)) {
                    plug.menuSlot.show()
                } else {
                    plug.menuSlot.hide()
                }
            }
        });
    }
}

function MenuPanel(containerElem) {
    if (!containerElem) throw new Error("Empty menu container elem");        
    
    let MENU_TEMPLATE = `
    <div class="he-menu">
        <button class="he-undo-button">отмена (Ctrl+Z)</button>
    </div>
    `;
    
    this.init = function() {
        let menu = createElementByHtml(MENU_TEMPLATE);
        menu.querySelector('.he-undo-button')
            .addEventListener('click', doUndo);  
        containerElem.appendChild(menu);
        this.root = menu
    }
    
    this.createSlot = function() {
        let elem = createElementByHtml('<span class="he-menu-slot"></span>')
        const undo = this.root.querySelector('.he-undo-button')        
        undo.before(elem)
        //this.root.prepend(elem)
        
        return new MenuSlot(elem)
    }
}

function MenuSlot(root) {
    this.root = root
    this.setHtmlElem = function(elem) { this.root.innerHtml = ''; this.root.append(elem) }
    this.isVisible = true
    
    this.hide = function() { 
        if (this.isVisible) {
            this.root.style.display = "none" 
            this.isVisible = false
        }
    }
    
    this.show = function(mode) {
        if (!this.isVisible) {
            this.root.style.display = (mode || "inline")
            this.isVisible = true
        }
    }
}

/* EDITORS */

//// base

let EDITOR_BASE = {
    bind(form, elem) {
        this.form = form        
        if (!elem) throw new Error("Empty root elem");
        this.root = elem
    },

    init(editor) {        
        // пройти по элементам, убрать contenteditable везде - расставим правильно далее
        processAllChildren(editor.root, (ch) => {
                if (ch.hasAttribute('contenteditable')) ch.removeAttribute('contenteditable');

        });
        
        // из буфера обмена разрешаем вставлять только текст, чтобы случайно
        // не вставились ссылки на внешние ресурсы и неправильные теги.
        // TODO разрешить вставлять теги details со сносками
        CONTENT_EDITABLE_TOOLS.insertOnlyTextFromClipboard(editor.root);
        
        // <br> между строками вместо тегов <div> для каждой строки
        CONTENT_EDITABLE_TOOLS.insertBrOnEnterInsteadOfDiv(editor.root);        
    },
    
    addPlugin(plugin) {
        if (!this.plugins) this.plugins = []
        this.plugins.push(plugin)
        
        return this    
    }
}

//// text editor
function TextEditor() {
    this.bind = EDITOR_BASE.bind;
    
    this.withPlugin = EDITOR_BASE.addPlugin
        
    this.init = function() {
        EDITOR_BASE.init(this)        
        this.root.setAttribute('contenteditable', 'true');        
    }
}

//// Таблица епископов или кафедр
function HierarhTableEditor(itemType /*кафедра или епископ*/) {
    if (itemType == 'епископ') {
        let TABLE_HEAD_TEMPLATE = `
        <thead class="he-table-head">
            <tr><th>начало</th><th>окончание</th><th>епископ</th></tr>
        </thead>
        `;
    } else if (itemType == 'кафедра') {
        TABLE_HEAD_TEMPLATE = `
        <thead class="he-table-head">
            <tr><th>кафедра</th><th>начало</th><th>окончание</th></tr>
        </thead>
        `;
    } else throw new Error("unexpected itemType", itemType)
    
    // обычная строка таблицы (от, до, кто).
    let TABLE_ROW_TEMPLATE = `
    <tr>
        <td></td>
        <td></td>
        <td></td>
    </tr>
    `;
    
    // строка-заголовок наподобие "Московский и всея Руси Патриархат"
    let TABLE_HEADER_ROW_TEMPLATE = `
        <tr class="header-row">
            <td colspan="3">Заголовок...</td>
        </tr>
    `;
    
    let TABLE_MENU_TEMPLATE = `
    <span class="he-table-menu">
        <button class="he-delete-row-button" title="удалить строку">X</button>
        <button class="he-up-row-button" title="переместить строку ввверх">^</button>
        <button class="he-down-row-button" title="переместить строку вниз">v</button>
        <button class="he-add-row-buton" title="добавить строку">+</button>
        <button class="he-add-header-button" title="добавить подзаголовок таблицы">+ заголовок</button>

        <span title="помещён в список управляющих кафедрой условно" class="he-table-menu-inaccurate">
            <input type="checkbox" id="he-inaccurate-row-checkbox" />
            <label for="he-inaccurate-row-checkbox">условно</label>
        </span>
    </span>
    `;
    
    let INACCURATE_ROW_CLASS = "inaccurate";
    
    this.bind = EDITOR_BASE.bind
        
    this.withPlugin = EDITOR_BASE.addPlugin 
       
    this.init = function(menuSlot) {
        EDITOR_BASE.init(this)
        
        if (this.root.tagName != 'TABLE') throw new Error('Expected <table> tag, got ' + this.root.tagName)
        let table = this.root
        table.setAttribute('contenteditable', 'true');
        
        // заголовок таблицы
        let th = table.querySelector('thead');
        if (!th) {
            console.log('Restore header in table', table);            
            th = createElementByHtml(TABLE_HEAD_TEMPLATE);
            table.insertBefore(th, table.firstElementChild);
        }
        
        th.setAttribute('contenteditable', false);
        th.classList.add('he-table-head');
        
        // ? prepareNotes(table);
        // TODO проверить, что у заголовков tr.header-row стоит colspan=3
        if (!table.querySelector('tbody')) {
            console.log('Add data row to empty table', table);

            let tb = document.createElement('tbody');
            tb.appendChild(createElementByHtml(TABLE_ROW_TEMPLATE));
            table.appendChild(tb);
        }
        
        
        let menu = createElementByHtml(TABLE_MENU_TEMPLATE)
        menu.querySelector(".he-delete-row-button").addEventListener('click', () => this.deleteCurRow())
        menu.querySelector(".he-up-row-button").addEventListener('click', () => this.upCurRow())
        menu.querySelector(".he-down-row-button").addEventListener('click', () => this.downCurRow())
        menu.querySelector(".he-add-row-buton").addEventListener('click', () => this.addAfterCurRow())
        menu.querySelector(".he-add-header-button").addEventListener('click', () => this.addAfterCurRow('header-row'))
        
        let inaccurateCheckBox = menu.querySelector(".he-table-menu-inaccurate input[type='checkbox']")
        inaccurateCheckBox.checked = false;
        inaccurateCheckBox.addEventListener('click', (ev) => {
            let r = this.toggleCurRowInaccurate()
            // Не разрешаем менять состояние чекбокса, если
            // он не связан со строкой
            if (!r) ev.preventDefault()
        })
        // Обновление чекбокса при выборе другой строки
        document.addEventListener("selectionchange", () => {
            let row = this.getCurrentRow()
            if (row) {
                inaccurateCheckBox.checked = row.classList.contains(INACCURATE_ROW_CLASS)
            } else {
                inaccurateCheckBox.checked = false
            }
        })
        
        menuSlot.setHtmlElem(menu)
    }    
    
    /* menu buttons */
    
    this.addAfterCurRow = function(rowClass) {
        let table = this.root        
        let curRow = this.getCurrentRow();
        let isHeader = (rowClass == 'header-row');

        let ntr;
        if (isHeader) {
            ntr = createElementByHtml(TABLE_HEADER_ROW_TEMPLATE);
        } else {
            ntr = createElementByHtml(TABLE_ROW_TEMPLATE);
        }

        if (curRow) {
            curRow.parentNode.insertBefore(ntr, curRow.nextElementSibling);
        } else if (!table.querySelector('tbody tr')) {
            console.log('Create row for empty table', table);
            table.querySelector('tbody').appendChild(ntr);
        } else {
            return
        }

        // Ставим курсор внутрь новосозданного элемента
        if (isHeader) {
            document.getSelection().selectAllChildren(ntr.querySelector('td'));
        }
        else {
            document.getSelection().collapse(ntr.querySelector('td'), 0);
        }
    }
    
    this.deleteCurRow = function() {
        let curRow = this.getCurrentRow();

        if (curRow) {
            let otherRow = curRow.previousElementSibling;
            if (!otherRow) {
                otherRow = curRow.nextElementSibling;
            }

            // удаляем так, чтобы можно было откатить
            deleteWithUndo(curRow);
            //let table = curRow.closest('table');
            //curRow.remove();
            
            // Если строчек не осталось, добавляем пустую
            if (this.root.querySelector('tbody tr') == null) this.addAfterCurRow();
            // иначе оставляем в оставшейся строке только курсор (снимаем выделение всей строки)
            else if (otherRow) {                
                document.getSelection().collapse(otherRow.querySelector('td'), 0);
            }
        }
    }
    
    this.upCurRow = function() {
        let curRow = this.getCurrentRow();
        if (curRow) {
            const prev = curRow.previousElementSibling;
            if (prev) {
                prev.before(curRow);
            }
        }
    }
    
    this.downCurRow = function() {
        let curRow = this.getCurrentRow()
        if (curRow) {
            const nxt = curRow.nextElementSibling;
            if (nxt) {
                nxt.after(curRow);
            }
        }
    }
    
    this.toggleCurRowInaccurate = function() {
        let curRow = this.getCurrentRow();
        if (curRow) {
            if (curRow.classList.contains('header-row')) {
                console.log("Can't set header-row inaccurate");
                return false;
            }
            curRow.classList.toggle(INACCURATE_ROW_CLASS);

            return true;
        } else {
            console.log('No row to set inaccurate!');
            return false;
        }
    }
    
    /* UTILS */
    
    this.getCurrentRow = function() {
        let r = getSelectionRange();
        if(!r) return null;

        let p = r.startContainer;
        if (!this.root.contains(p)) {
            // выделение не относится к текущей таблице
            // console.log("Selection", p, "not in table", this.root)
            return null;
        }
        
        while(p) {
            // в заголовке таблицы не работаем!
            if (p.tagName == 'TH') return null;

            if (p.tagName == 'TR') {
                return p;
            }

            p = p.parentNode;
        }

        return null;
    }
    
    return this
}



function NotePlugin() {
    let NOTE_MENU_TEMPLATE = `
    <button class="he-add-note-button" title="добавить сноску">сноска</button>
    `
    
    let DELETE_BTN_TEMPLATE = `<button class="he-delete-button he-tmp">удалить</button>`;
    
    let NOTE_HEADER_TEMPLATE = `<sup>[сноска]</sup>`
    
    let NOTE_TEMPLATE = `
    <span class="fnote" contenteditable="false">
    ${NOTE_HEADER_TEMPLATE}<span contenteditable="true"></span></span>`;
    
    this.init = function(menuSlot) {
        let menu = createElementByHtml(NOTE_MENU_TEMPLATE)
        //console.log('note init menu', menu)
        menu.addEventListener('click', () => this.addNote())        
        menuSlot.setHtmlElem(menu)
    }
    
    this.registerEditor = function(editor) {
        // TODO обработать имеющиеся в editor.root сноски span.fnote:
        // - восстановить <sup>[сноска]</sup> если нет
        // - убрать .open или оставить, но тогда ещё добавить кнопку удаления
        
        
        // чиним редактирование если сноска находится в конце текста,
        // а курсор стоит на её нередактируемой части.
        // в этом случае мышкой курсор в конец текста уже не ставится
        // (клавиатурой можно)
        editor.root.addEventListener("beforeinput", (ev) => {            
            let r = getSelectionRange()
            // если при попытке ввода курсор стоит на 
            // нередактируемой части сноски,
            // то переставляем его после сноски
            if (r && !canUserEditRange(r)) {
                let elem = r.endContainer
                if (elem.nodeType == Node.TEXT_NODE) {
                    elem = elem.parentNode
                }
        
                let fnote = elem.closest('span.fnote')
                if (fnote) {
                    setCursorAfter(fnote)
                }
            }
        });
    }
    
    this.addNote = function() {        
        let sl = window.getSelection();
        if (!sl.rangeCount) return;

        let r = sl.getRangeAt(0);
        r.collapse();
        
        // TODO По-хорошему надо спросить у editor, можно ли это
        // место редактировать. Но как найти нужного editor?
        // - в общем случае их может быть несколько вложенных...
        if (!canUserEditRange(r)) {
            console.log("Can't add note to not-editable area", r);
            return;
        }

        let n = createElementByHtml(NOTE_TEMPLATE);
        openNote(n)     
        
        n.removeClickController = new AbortController();
        
        // открытие/закрытие сноски кликом по заголовку
        n.querySelector('sup').addEventListener('click', () => {            
            if (n.classList.contains('open')) {
                closeNote(n)
            } else {
                openNote(n)
            }
        }, {signal: n.removeClickController.signal})
        

        r.insertNode(n);
        //addEofIfRequired();

        // выделяем текст сноски - там Placeholder "текст сноски..."
        sl.empty();
        sl.selectAllChildren(n.querySelector("span[contenteditable='true']"));
    }
    
    function openNote(n) {
        let btn = n.querySelector('sup > .he-delete-button')
        if (!btn) {
            btn = createElementByHtml(DELETE_BTN_TEMPLATE)
            btn.addEventListener('click', (ev) => {
                // удаляем обработчик раскрытия/закрытия сноски. Если он сработает после удаления,
                // будет ошибка.
                n.removeClickController.abort()              
                deleteWithUndo(ev.target.closest('span.fnote'))                
            })
            
            n.querySelector('sup').append(btn)            
        }
        
        n.classList.add('open')
    }
    
    function closeNote(n) {        
        let btn = n.querySelector('sup > .he-delete-button')
        if (btn) {
            btn.remove()
        }
        n.classList.remove('open')
        
        setCursorAfter(n)        
    }
    
    function canUserEditRange(r) {
        let tag = r.startContainer;        
        if (tag.nodeType == Node.TEXT_NODE) {
            tag = tag.parentElement;
        }

        while (tag) {
            if(tag.getAttribute('contenteditable') == "false") {
                return false;
            } else if (tag.getAttribute('contenteditable') == "true") {
                return true;
            }

            tag = tag.parentElement;
        }

        return false;
    }
}


/*************** CONTENTEDITABLE TOOLS *****************/

let CONTENT_EDITABLE_TOOLS = {
    // из буфера обмена разрешаем вставлять только текст
    insertOnlyTextFromClipboard(root) {
        root.addEventListener("paste", (ev) => {    
            ev.preventDefault();

            let paste = (event.clipboardData || window.clipboardData).getData("text");

            const selection = window.getSelection();
            if (!selection.rangeCount) return;
            selection.deleteFromDocument();
            selection.getRangeAt(0).insertNode(document.createTextNode(paste));
            selection.collapseToEnd();
        });
    },

    // <br> между строками вместо тегов <div> для каждой строки
    insertBrOnEnterInsteadOfDiv(root) {
        root.addEventListener("keydown", (ev) => {
            ev = ev || window.event;
            var keyCode = ev.charCode || ev.keyCode;
            if (keyCode == 13) {
                document.execCommand('insertHTML', false, '<br/>');
                //document.execCommand('insertLineBreak');
                ev.preventDefault();
                
                // В конце текста <br> по нажатию Enter добавляется, 
                // но курсор остаётся в предыдущей строке.
                // А в Chrome вообще на конце текста Enter не работает.
                let r = getSelectionRange();                
                //console.log("Enter with selection", r)
                // Отлавливаем ситуацию нажатия Enter в конце текста
                if (r.collapsed && r.startContainer.nodeType == Node.TEXT_NODE && r.startOffset != 0) {
                    console.log("Enter on end of", root)
                    // Chrome надо два <br> вставить - один пропадёт при вводе
                    if (window.chrome) {
                        document.execCommand('insertHTML', false, '<br/><br/>');
                    } else {
                        document.execCommand('insertHTML', false, '<br/>');
                    }
                }
                
                // TODO В Chrome при нажатии Enter в конце строки внутри текста новая строка не добавляется.
                // вместо этого курсор переносится на следующую строку и этого даже не видно пока не начнёшь набирать.                
            }
        });
    }
};

/*************** UTILS *****************/

function processAllChildren(elem, f) {
    let chh = []
    for (let ch of elem.children) {
        chh.push(ch);
    }

    for (let ch of chh) {
        let skipChildren = f(ch);
        if (!skipChildren)
            processAllChildren(ch, f);
    }
}


function createElementByHtml(html) {
    let t = document.createElement('template');
    t.innerHTML = html;
    return t.content.firstElementChild;
}


function getSelectionRange() {
    const sl = window.getSelection();
    if (!sl.rangeCount) return null;
    return sl.getRangeAt(0);
}

function setCursorAfter(elem) {        
    let r = new Range()
    console.log("set cursor after", elem)
    r.setStartAfter(elem)
            
    let sl = window.getSelection()
    sl.empty()
    sl.addRange(r)
}

function doUndo() {
    document.execCommand('undo', false, null);
}

function deleteWithUndo(tag) {
    // выделяем тег
    let r = new Range();
    r.selectNode(tag);
    document.getSelection().removeAllRanges();
    document.getSelection().addRange(r);

    // просим браузер нажать клавишу delete
    // благодаря этому будет работать отмена execCommand('undo')
    document.execCommand('delete', false, null);
}


