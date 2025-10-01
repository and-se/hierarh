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
            <input placeholder="${sf(placeholder)}" list="${sid}" style="width:inherit">
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

        let dl = document.getElementById(sid)
        let curTimer, oldInput, oldRequestStopper
        el.addEventListener('input', (ev) => {
            if (oldInput == ev.target.value) throw new Error("why?")
            oldInput = ev.target.value // todo delete
            
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
                return
            }

            el.dispatchEvent(new CustomEvent('suggestOutdated', {bubbles:true}))
            
            // В противном случае запускаем механизм подсказки с задержкой
            let suggestDelayMs = 100
            curTimer = setTimeout(() => {
                Promise.try(suggestFunc, ev.target.value, oldRequestStopper.signal).then(variants => {
                    if (!variants || !variants[Symbol.iterator] === 'function') {                            
                        console.error(el, "Suggest func must return iterable, but got", variants)
                        return
                    }

                    updateSuggestDataList(dl, variants)
                }).catch(error => {
                    if (error.name == "AbortError") {
                        return
                    }
                    console.error("Error suggest", error, typeof error)
                }).finally(() => {
                    oldRequestStopper = null
                })
            }, suggestDelayMs)
        })
    })
    
    function updateSuggestDataList(dl, variants) {
        let opts = [], i=1
        for (let v of variants) {
            let op = document.createElement('option')
            
            if (typeof v === 'object') {
                if (!v.hasOwnProperty('value')) {
                    console.error("Suggest item must be String or object with 'value' field")
                    return
                }                
                // все поля кроме .value сохраним как data-атрибуты
                let val = v.value
                delete v.value
                Object.assign(op.dataset, v)
                
                // Добавим в конец невидимых пробелов - по номеру подсказки
                op.setAttribute("value", val.trim() + TheNbsp.repeat(i))
            } else {
                op.setAttribute("value", v.trim() + TheNbsp.repeat(i))
            }
            opts.push(op)
            i++
        }
        dl.replaceChildren(...opts)
    }    

    function sf(string) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;',
            "/": '&#x2F;',
        };
        const reg = /[&<>"'/]/ig;
        return string.replace(reg, (match)=>(map[match]));
    }

    function makeUniqueId(prefix) {
        if (prefix && !document.getElementById(prefix)) {
            return prefix
        }
        
        if (!prefix) prefix = "id_";
        let i = 0
        
        let res = prefix + i;
        while(document.getElementById(res)) {
            i++
            res = prefix+i
        }
        
        return res
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



