'use strict'

/*
Тег input-select - input с подсказкой. Текст доступен в свойстве .value
В атрибут suggest нужно написать имя JS-функции, формирующей список подсказок.

suggest-функция принимает на вход ввод пользователя и 
возвращает список подсказок в виде массива строк либо объектов (можно Promise)

Для объектов обязательно свойство value - это будет текст подсказки,
а остальные поля будут записаны как data-атрибуты тега input-select после выбора подсказки.

При выборе подсказки генерируется событие suggestSelected, в detail которого 
кладётся dataset для быстрого доступа к data-атрибутам input-select

Если пользователь изменил текст вручную, 
генерируется событие suggestOutdated, а data-атрибуты input-select очищаются
*/
document.addEventListener('DOMContentLoaded', function() {
    let TheNbsp = "\u00A0"; // &nbsp; - пробел, но другой (неразрывный)

    document.querySelectorAll('input-select').forEach(el => {
        let suggestFunc = window[el.getAttribute('suggest')]
        if (typeof suggestFunc !== 'function') {
            console.error(el, 'suggest attribute must contain js-function name')
            return
        }

        let placeholder = el.innerText.trim()
        let sid = makeUniqueId("suggest")
        el.innerHTML = `
            <input placeholder="${sf(placeholder)}" list="${sid}" style="width:inherit; padding:inherit;">
            <datalist id="${sid}">
            </datalist>
        `
        // Пробрасываем свойство value из input в родительский input-select
        Object.defineProperty(el, 'value', {
            get() {
                return this.querySelector('input').value
            },
            set(value) {
                this.querySelector('input').value = value
            }
        })

        el.focus = () => {
            el.querySelector('input').focus()
        }

        let dl = document.getElementById(sid)
        el._input_select_allow_suggest_outdated=true
        
        let curTimer, oldRequestStopper
        function doSuggestOnEvent(ev) {
            // Механизм подсказки запускается с задержкой - отменяем предыдущую попытку
            clearTimeout(curTimer)

            // Просим предыдущую пользовательскую функцию-подсказку прерваться
            if (oldRequestStopper) oldRequestStopper.abort()
            oldRequestStopper = new AbortController()
                  
            let suggestNum = countAtEnd(ev.target.value, TheNbsp)
            clearDataSet(el) // очищаем старые data-атрибуты - текст же изменился
            // Правка вызвана выбором элемента в подсказках - копируем data-атрибуты
            if (suggestNum > 0)
            {
                let sugg = dl.children[suggestNum-1]
                Object.assign(el.dataset, sugg.dataset)                
                ev.target.value = ev.target.value.trim() // очищаем технические nbsp;
                console.info(el, 'selected suggest', suggestNum-1, sugg)
                el.dispatchEvent(new CustomEvent("suggestSelected", {
                    bubbles: true,
                    detail: el.dataset
                }))

                el._input_select_allow_suggest_outdated=true

                // подсказывать не надо - мы только что выбрали подсказку
                return
            }
            
            if (el._input_select_allow_suggest_outdated) {
                el.dispatchEvent(new CustomEvent('suggestOutdated', {bubbles:true}))
                // событие не будет генерироваться до следущей выбранной подсказки
                el._input_select_allow_suggest_outdated = false
            }
            
            // В противном случае запускаем механизм подсказки с задержкой
            let suggestDelayMs = 100
            curTimer = setTimeout(() => {
                Promise.try(suggestFunc, ev.target.value, oldRequestStopper.signal).then(variants => {
                    if (!variants || !variants[Symbol.iterator] === 'function') {                            
                        console.error(el, "Suggest func must return iterable, but got", variants)
                        return
                    }

                    updateSuggestDataList(dl, variants, ev.target.value)
                }).catch(error => {
                    if (error.name == "AbortError") {
                        return
                    }
                    console.error("Error suggest", error, typeof error)
                }).finally(() => {
                    oldRequestStopper = null
                })
            }, suggestDelayMs)
        }
        el.addEventListener('input', (ev) => doSuggestOnEvent(ev))
        el.addEventListener('dblclick', ev => doSuggestOnEvent(ev))

        //el.dispatchEvent(new InputEvent('input')) - сформировать начальный список подсказок.
    })
    
    function updateSuggestDataList(dl, variants, query) {
        let opts = [], i=1
        for (let v of variants) {
            let op = document.createElement('option')
            let opVal, opLabel;
            
            if (typeof v === 'object') {
                if (!v.hasOwnProperty('value')) {
                    console.error("Suggest item must be String or object with 'value' field")
                    return
                }                
                // все поля кроме .value сохраним как data-атрибуты
                let val = v.value
                delete v.value
                Object.assign(op.dataset, v)
                opVal = val.trim()
            } else {
                opVal = v.trim()
            }
            
            // если подсказка не содержит текст в input, то input+datalist её не покажет
            // (datalist фильтруется по вхождению текущего значения input)
            // Делаем option с атрибутом label = текст подсказки + значение input
            // Тогда в списке подсказок будет отображаться label, а при выборе
            // проставляться атрибут value, так что лишний текст в input не впишется.
            // Протестировано в Chromium и Firefox.
            if (!opVal.toLowerCase().includes(query.toLowerCase())) {
                opLabel = opVal + ` (${query})`; 
            }
            
            // Добавим в конец невидимых пробелов - по номеру подсказки,
            // чтобы после выбора понять, какую именно подсказку выбрали
            op.setAttribute("value", opVal + TheNbsp.repeat(i))
            if (opLabel) {
                op.setAttribute("label", opLabel)
            }

            opts.push(op)
            i++
        }
        dl.replaceChildren(...opts)
    }    

    function sf(string) {
        return LIB.escapeForHtml(string)
    }

    function makeUniqueId(prefix) {
        return LIB.makeUniqueId(prefix)
    }

    function clearDataSet(elem) {
        Object.keys(elem.dataset).forEach(e => {
            delete elem.dataset[e]
        })
    }

    function countAtEnd(s, what) {
        let i=0
        while(s[s.length-1-i] == what) {
            i++
        }

        return i
    }

})



