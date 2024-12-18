'use strict';


/*** public ***/

function makeCafedraEditForm(root) {
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

    let text = root.querySelector('.text');
    if (!text) throw new Error('Text not found');

    text.setAttribute('contenteditable', 'true');
    prepareNotes(text);

    let table = root.querySelector('table.episkops');
    if (!table) throw new Error('Episkops table not found');

    table.setAttribute('contenteditable', 'true');

    // заголовок таблицы
    let th = table.querySelector('thead');
    if (!th) {
        th = createElementByHtml(TABLE_HEAD_TEMPLATE);
        table.insertBefore(th, table.firstElementChild);
        console.log('Restore header in table', table);
    }
    th.setAttribute('contenteditable', false);
    th.classList.add('he-table-head');

    prepareNotes(table);

    // скрытие/показ кнопок, специфичных для таблицы
    root.addEventListener('click', updateMenu);

    // из буфера обмена разрешаем вставлять только текст, чтобы случайно
    // не вставились ссылки на внешние ресурсы и неправильные теги.
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
}

function makeEditMenu(root) {
    root.appendChild(createElementByHtml(MENU_TEMPLATE));
}

/*** html templates ***/

let DELETE_BTN_TEMPLATE = `<button class="he-delete-button" onclick="deleteNote(this)">удалить</button>`;

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
        <button onclick="addNote()">сноска</button>

        <span class="he-table-menu" style="display:none">
            <button onclick="deleteRow()">X</button>
            <button onclick="upRow()">^</button>
            <button onclick="downRow()">v</button>
            <button onclick="addRow()">+</button>
            <button onclick="addRow('header-row')">+ заголовок</button>
        </span>

        <button onclick="doUndo()" class="he-cancel-button">отмена (Ctrl+Z)</button>

    </div>
`;

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
    let n = createElementByHtml(NOTE_TEMPLATE);

    r.insertNode(n);
    r.collapse();
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

function addRow(rowClass) {
    let ntr;
    if (rowClass == 'header-row') {
        ntr = createElementByHtml(TABLE_HEADER_ROW_TEMPLATE);
    } else {
        ntr = createElementByHtml(TABLE_ROW_TEMPLATE);
    }

    let curRow = getCurrentTableRow();
    if (curRow) {
        curRow.parentNode.insertBefore(ntr, curRow.nextElementSibling);
    } else document.querySelector('.he-edit-form table').appendChild(ntr);
}


function deleteRow() {
    let curRow = getCurrentTableRow();
    if (curRow) {
        let table = curRow.closest('table');

        //curRow.remove();
        deleteWithUndo(curRow);

        if (table.querySelector('tbody tr') == null) addRow();
    }
}


function upRow() {
    let cur_row = getCurrentTableRow();
    if (cur_row) {
        const prev = getPrevTableRow(cur_row);
        if (prev) {
            prev.before(cur_row);
        }
    }
}

function downRow() {
    let cur_row = getCurrentTableRow();
    if (cur_row) {
        const nxt = getNextTableRow(cur_row);
        if (nxt) {
            nxt.after(cur_row);
        }
    }
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

/*** other internals***/

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
    for (let ch of elem.children) {
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

    while(p) {
        //console.log('wh', p);
        if (p.nodeType ==  Node.ELEMENT_NODE) {
            if (p.classList.contains('text')) {
                mext.style.display="none";
                return;
            } else if (p.tagName == 'TD') {
                mext.style.display="inline";
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

