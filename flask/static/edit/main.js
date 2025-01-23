'use strict';


/*** public ***/

function makeCafedraEditForm(root) {
    let result = {};
    result.root = root;

    if (!root) throw new Error('empty root!');
    // пройти по элементам, убрать contenteditable везде - расставим правильно далее
    processAllChildren(root, (ch) => {
            if (ch.hasAttribute('contenteditable')) ch.removeAttribute('contenteditable');

    });

    root.classList.add('he-edit-form');

    let header = root.firstElementChild;
    if (!header.classList.contains('header')) {
        throw new Error('Header not found.');
    }
    header.setAttribute('contenteditable', 'true');
    result.header = header;

    let text = root.querySelector('.text');
    if (!text) throw new Error('Text not found');
    result.text = text;

    text.setAttribute('contenteditable', 'true');
    prepareNotes(text);

    let table = root.querySelector('table.episkops');
    if (!table) throw new Error('Episkops table not found');
    result.table = table;

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
    prepareNotes(table);
    // TODO проверить, что у заголовков tr.header-row стоит colspan=3
    if (!table.querySelector('tbody')) {
        console.log('Add data row to empty table', table);

        let tb = document.createElement('tbody');
        tb.appendChild(createElementByHtml(TABLE_ROW_TEMPLATE));
        table.appendChild(tb);
    }

    // скрытие/показ кнопок, специфичных для таблицы
    root.addEventListener('click', updateMenu);
    // TODO при работе только с клавиатуры (без мыши) меню не обновляется

    // Редактирование общих свойств формы - пока это признак обновленческой
    let props = root.querySelector('.he-props');
    if (!props) props = createElementByHtml(PROPS_EDIT_TEMPLATE);
    let obncb = props.querySelector("#he-obn-checkbox");
    obncb.checked = root.dataset.isObn === 'true';
    obncb.hfroot = root;
    root.insertBefore(props, text);

    // из буфера обмена разрешаем вставлять только текст, чтобы случайно
    // не вставились ссылки на внешние ресурсы и неправильные теги.
    // TODO разрешить вставлять теги details со сносками
    root.addEventListener("paste", (ev) => {
        ev.preventDefault();

        let paste = (event.clipboardData || window.clipboardData).getData("text");

        const selection = window.getSelection();
        if (!selection.rangeCount) return;
        selection.deleteFromDocument();
        selection.getRangeAt(0).insertNode(document.createTextNode(paste));
        selection.collapseToEnd();

    });

    root.addEventListener("beforeinput", (ev) => {
        //console.log(ev);
        // ev.target берёт только таблицу целиком, а нам нужен сам редактируемый элемент
        // - ищем его на основе анализа выделения
        addEofIfRequired();
    });

    root.addEventListener("input", (ev) => {
        // Следим, чтобы сноски были после текста, а не с новой строки
        // contenteditable при нажатии Enter иногда раскладывает сноски по отдельным строкам
        // так, что это нельзя отредактировать.
        repairDetails(root);
    });

    // <br> между строками вместо тегов <div> для каждой строки
    root.addEventListener("keydown", (ev) => {
        ev = ev || window.event;
        var keyCode = ev.charCode || ev.keyCode;
        if (keyCode == 13) {
            document.execCommand('insertHTML', false, '<br/>');
            //document.execCommand('insertLineBreak');
            ev.preventDefault();
        }
    });

    result.makeMenu = makeEditMenu;
    result.getData = getSaveData;

    return result;
}
/*** form private ***/
function makeEditMenu(menuRoot) {
    let menu = createElementByHtml(MENU_TEMPLATE);
    for(let btn of menu.querySelectorAll('.he-table-menu button')) {
        btn.table = this.table;
    }

    menuRoot.appendChild(menu);
}

function getSaveData() {
    let data = this.root.cloneNode(true);
    data.classList.remove('he-edit-form');

    processAllChildren(data, (ch) => {
            if (ch.hasAttribute('contenteditable')) ch.removeAttribute('contenteditable');
            // todo удалять ли атрибут "open" у тегов details или пусть запоминается, что сноски открыты?
            if (ch.classList.contains('he-tmp')) {
                //console.log('remove', ch);
                ch.remove();
                return true;
            }
            let toDel = [];
            for (let cl of ch.classList) {
                if (cl.startsWith('he-')) {
                    toDel.push(cl);
                }
            }

            for(let cl of toDel) {
                ch.classList.remove(cl);
            }
            if(ch.classList.length == 0) ch.removeAttribute('class');
    });

    return data.outerHTML;
}
/*** html templates ***/

let PROPS_EDIT_TEMPLATE = `
    <div class="he-props he-tmp">
        <input type="checkbox" id="he-obn-checkbox" onclick="this.hfroot.dataset.isObn = this.checked"/>
        <label for="he-obn-checkbox">обновленческая</label>
    </div>
`;

let DELETE_BTN_TEMPLATE = `<button class="he-delete-button he-tmp" onclick="deleteNote(this)">удалить</button>`;

let NOTE_HEADER_TEMPLATE = `
    <summary>
        <sup>[сноска]</sup>
        ${DELETE_BTN_TEMPLATE}
    </summary>`;

let NOTE_TEMPLATE = `
    <details contenteditable="false">
        ${NOTE_HEADER_TEMPLATE}
        <div contenteditable="true">текст сноски...</div>
    </details>
`;

let MENU_TEMPLATE = `
    <div class="he-menu">
        <button class="he-add-note-button" onclick="addNote()" title="добавить сноску">сноска</button>

        <span class="he-table-menu" style="display:none">
            <button class="he-delete-row-button" onclick="deleteRow(this.table)" title="удалить строку">X</button>
            <button class="he-up-row-button" onclick="upRow(this.table)" title="переместить строку ввверх">^</button>
            <button class="he-down-row-button" onclick="downRow(this.table)" title="переместить строку вниз">v</button>
            <button class="he-add-row-buton" onclick="addRow(this.table)" title="добавить строку">+</button>
            <button class="he-add-header-button" onclick="addRow(this.table, 'header-row')" title="добавить подзаголовок таблицы">+ заголовок</button>

            <span title="помещён в список управляющих кафедрой условно" class="he-table-menu-inaccurate">
                <input type="checkbox" id="he-inaccurate-row-checkbox"
                       onclick="return setRowInaccurate(this.closest('.he-table-menu').table, this.checked)"/>
                <label for="he-inaccurate-row-checkbox">условно</label>
            </span>
        </span>

        <button onclick="doUndo()" class="he-undo-button">отмена (Ctrl+Z)</button>

    </div>
`;

let INACCURATE_ROW_CLASS = "inaccurate";

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

/*** buttons ***/

function addNote() {
    let sl = window.getSelection();
    if (!sl.rangeCount) return;

    let r = sl.getRangeAt(0);
    r.collapse();

    if (!canUserEditRange(r)) {
        console.log("Can't add note to not-editable area", r);
        return;
    }

    let n = createElementByHtml(NOTE_TEMPLATE);

    r.insertNode(n);
    addEofIfRequired();

    // открываем сноску на редактирование
    n.setAttribute('open', '');
    // выделяем текст сноски - там Placeholder "текст сноски"
    sl.empty();
    sl.selectAllChildren(n.querySelector('div'));

}

function doUndo() {
    document.execCommand('undo', false, null);
}

function deleteNote(node) {
    //node.closest('details').remove(); // так не работает undo

    deleteWithUndo(node.closest('details'));

}

function addRow(table, rowClass) {
    let curRow = getCurrentTableRow();
    let isHeader = (rowClass == 'header-row');

    let ntr;
    if (isHeader) {
        ntr = createElementByHtml(TABLE_HEADER_ROW_TEMPLATE);
    } else {
        ntr = createElementByHtml(TABLE_ROW_TEMPLATE);
    }

    if (curRow) {
        if(!table.contains(curRow)) return; // выбранная строка не относится к текущей таблице!
        curRow.parentNode.insertBefore(ntr, curRow.nextElementSibling);
    } else {
        console.log('Create row for empty table', table);
        table.querySelector('tbody').appendChild(ntr);
    }

    // Ставим курсор внутрь новосозданного элемента
    if (isHeader) {
        document.getSelection().selectAllChildren(ntr.querySelector('td'));
    }
    else {
        document.getSelection().collapse(ntr.querySelector('td'), 0);
    }
}


function deleteRow(table) {
    let curRow = getCurrentTableRow();

    if (curRow) {
        if(!table.contains(curRow)) return;

        let otherRow = getNextTableRow(curRow);
        if (!otherRow) {
            otherRow = getPrevTableRow(curRow);
        }

        //let table = curRow.closest('table');
        //curRow.remove();
        deleteWithUndo(curRow);

        if (table.querySelector('tbody tr') == null) addRow(table);
        else if (otherRow) {
            document.getSelection().collapse(otherRow.querySelector('td'), 0);
        }
    }
}


function upRow(table) {
    let curRow = getCurrentTableRow();
    if (curRow) {
        const prev = getPrevTableRow(curRow);
        if (prev) {
            prev.before(curRow);
        }
    }
}

function downRow(table) {
    let curRow = getCurrentTableRow();
    if (curRow) {
        const nxt = getNextTableRow(curRow);
        if (nxt) {
            nxt.after(curRow);
        }
    }
}

function setRowInaccurate(table, value) {
    let curRow = getCurrentTableRow();
    if (curRow) {
        if (curRow.classList.contains('header-row')) {
            console.log("Can't set header-row inaccurate");
            return false;
        }
        if (value) {
            curRow.classList.add(INACCURATE_ROW_CLASS);
        } else {
            curRow.classList.remove(INACCURATE_ROW_CLASS);
        }

        return true;
    } else {
        console.log('No row to set inaccurate!');
        return false;
    }
}


/*** selection and navigation***/

function getSelectionRange() {
    const sl = window.getSelection();
    if (!sl.rangeCount) return null;
    return sl.getRangeAt(0);
}


function getCurrentTableRow() {
    let r = getSelectionRange();
    if(!r) return null;

    let p = r.startContainer;
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


function getPrevTableRow(curRow) {
    let prev = curRow.previousElementSibling;
    /*while(prev) {
        if (prev.classList.contains("epcaf")) {
            return prev;
        }

        prev = prev.previousElementSibling;
    }*/
    return prev;
}

function getNextTableRow(curRow) {
    let nxt = curRow.nextElementSibling;
    /*while(nxt) {
        if (nxt.classList.contains("epcaf")) {
            return nxt;
        }

        nxt = nxt.nextElementSibling;
    }*/
    return nxt;
}

/*** other internals***/
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

function prepareNotes(tag) {
    // Отключаем редактирование у пояснений (details), но оставляем для текста пояснения
    for (let dt of tag.querySelectorAll('details')) {
        dt.setAttribute('contenteditable', 'false');

        // Загловок сноски [сноска]
        let summ = dt.querySelector('summary');
        if (!summ) {
            console.log('repair summary for', dt);
            summ = createElementByHtml(NOTE_HEADER_TEMPLATE);
            dt.insertBefore(summ, dt.firstElementChild);
        }

        // Заголовок сноски - верхний индекс
        let delbtn = summ.querySelector('button.he-delete-button');
        if (!summ.firstElementChild || summ.firstElementChild.tagName != 'SUP') {
            console.log('add summary->sup for', dt);
            let sup = document.createElement('sup');
            for(let el of summ.childNodes) {
                if (el != delbtn) sup.appendChild(el);
            }

            summ.appendChild(sup);
        }

        // кнопка удаления сноски
        if (!delbtn) {
            delbtn = createElementByHtml(DELETE_BTN_TEMPLATE);
            summ.appendChild(delbtn);
        }

        // Всё остальное - текст сноски
        if (dt.childElementCount < 2) {
            console.log('add empty note content for', dt);
            let nn = document.createElement('div');
            nn.innerHTML = '...';
            dt.appendChild(nn);
        }
        for (let el of dt.children) {
            if (el != summ) el.setAttribute('contenteditable', 'true');
        }

        /*let quote = dt.querySelector('div.note-content');

        if (!quote) {
            console.log('add div.note-content for', dt);
            quote = document.createElement('div');
            quote.classList.add('note-content');
            dt.appendChild(quote);
        }
        quote.setAttribute('contenteditable', 'true');*/
    }
}

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

function addEofIfRequired() {
    let target = getSelectionRange();
    if (!target) return;

    target = target.startContainer;
    if (target.nodeType == Node.TEXT_NODE) target = target.parentNode;
    //console.log(target);

    let last = target.lastChild;
    if (!last) return;
    if (last.nodeName == 'DETAILS' || (last.nodeType == Node.TEXT_NODE && last.nodeValue == "")) {
        // добавляем пустую строку, чтобы можно было редактировать и ставить курсор после сноски.
        let eof = createElementByHtml(`<span><br></span>`);

        target.appendChild(eof);

        //console.log('add eof to', target);
    }
}

function repairDetails(root) {
    processAllChildren(root, tag => {
        if (tag.tagName == 'DETAILS') {
            let pr = tag.previousSibling;
            if (pr && pr.nodeType == Node.ELEMENT_NODE && pr.tagName == 'BR') {
                console.log('remove', pr, 'before', tag);
                // сноска не может быть с новой строки - она всегда после текста
                pr.remove();
            }

            pr = tag.previousSibling;
            if (!pr || (pr.nodeType == Node.TEXT_NODE && pr.textContent.trim()=='')) {
                console.log('add ... before', tag);
                tag.before("...");
            }
        }
    });
}

function createElementByHtml(html) {
    let t = document.createElement('template');
    t.innerHTML = html;
    return t.content.firstElementChild;
}

function updateMenu() {
    let r = getSelectionRange();
    if (!r) return;
    let p = r.startContainer;
    const mext = document.querySelector('.he-table-menu');
    let cb = document.getElementById('he-inaccurate-row-checkbox')

    while(p) {
        //console.log('wh', p);
        if (p.nodeType ==  Node.ELEMENT_NODE) {
            if (p.classList.contains('text')) {
                mext.style.display="none";
                return;
            } else if (p.tagName == 'TD') {
                mext.style.display="inline";

                cb.checked = p.closest('tr').classList.contains(INACCURATE_ROW_CLASS);
                return;
            }
        }

        p = p.parentNode;
    }
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

