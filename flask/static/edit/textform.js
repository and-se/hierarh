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
    
    this.start = function() {
        root.classList.add('he-edit-form');
        this.menu.init()
        for (let ed of this.editors) {
            if (ed.init) {
                let slot = null
                if (this.menu)
                    slot = this.menu.createSlot()
                
                ed.menuSlot = slot
                slot.targetEditor = ed
                
                slot.hide()
                ed.init(slot)
            }
            else console.log("Not init() for", ed)
        }
    }
    
    document.addEventListener("selectionchange", () => {        
        let r = getSelectionRange()
        if (!r) return        
        for (let ed of this.editors) {
            if (ed.root.contains(r.commonAncestorContainer)) {
                if (ed.isActive) continue
                //ed.activate(r)
                // todo update menu
                ed.isActive = true
                ed.menuSlot.show()
            } else {
                //ed.deactivate()
                ed.isActive = false
                ed.menuSlot.hide()
            }
            
            //console.log("find active", ed, ed.isActive)
        }
    });
    
    
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
        this.root.prepend(elem)
        
        return new MenuSlot(elem)
    }
}

function MenuSlot(root) {
    this.root = root
    this.setHtmlElem = function(elem) { this.root.innerHtml = ''; this.root.append(elem) }
    this.hide = function() { this.root.style.display = "none" }
    this.show = function(mode) { this.root.style.display = (mode || "inline") }
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
    }
}

//// text editor
function TextEditor(options = {}) {
    this.bind = EDITOR_BASE.bind;
    
    /*this.activate = function(selectionRange) {        
    }
    
    this.deactivate = function() = {}*/
    
    this.init = function() {
        EDITOR_BASE.init(this)        
        this.root.setAttribute('contenteditable', 'true');        
    }
    
    
    this.withPlugin = function(plugin) {
        //todo
        return this
    }
}


function HierarhTableEditor() {
    this.bind = EDITOR_BASE.bind
    
    let TABLE_HEAD_TEMPLATE = `
    <thead class="he-table-head">
        <tr><th>начало</th><th>окончание</th><th>епископ</th></tr>
    </thead>
    `;
    
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
    
    this.withPlugin = function(plugin) {
        //todo
        return this
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
            // выделение не относится к текущей таблице!
            console.log("Selection", p, "not in table" ,this.root)
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
    // ? prepareNotes(text);
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
                // TODO В конце текста <br> добавляется, но курсор перед ним - надо переставить его принудительно.
                // Пока приходится два раза нажимать Enter
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

