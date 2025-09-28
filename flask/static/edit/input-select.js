'use strict'
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('input-select').forEach(el => {        
        let placeholder = el.innerText.trim()

        let sid = makeUniqueId("suggest")
        el.innerHTML = `
            <input placeholder="${sf(placeholder)}" list="${sid}">
            <datalist id="${sid}">
                <option value="ссылка не нужна">
                <option value="ещё что-то">
            </datalist>
        `
        let suggestFunc = window[el.getAttribute('suggest')]
        if (typeof suggestFunc === 'function') {
            let curTimer, oldInput, oldRequestStopper
            el.addEventListener('keyup', (ev) => {
                if (oldInput == ev.target.value) return
                oldInput = ev.target.value
                
                // Механизм подсказки запускается с задержкой - отменяем предыдущую попытку
                clearTimeout(curTimer)

                // Просим предыдущую пользовательскую функцию-подсказку прерваться
                if (oldRequestStopper) oldRequestStopper.abort()
                oldRequestStopper = new AbortController()
                
                // Запускаем механизм подсказки с задержкой
                let suggestDelayMs = 100
                curTimer = setTimeout(() => {
                    Promise.try(suggestFunc, ev.target.value, oldRequestStopper.signal).then(variants => {
                        if (!variants || !variants[Symbol.iterator] === 'function') {
                            console.log("Suggest func must return iterable, but got", variants)
                            return
                        }
                        let dl = document.getElementById(sid)
                        let opts = []
                        for (let v of variants) {
                            let op = document.createElement('option')
                            op.setAttribute("value", v)
                            opts.push(op)
                        }
                        dl.replaceChildren(...opts)
                    }).catch(error => {
                        if (error.name == "AbortError") {
                            return
                        }
                        console.log("Error suggest", error, typeof error)
                    }).finally(() => {
                        oldRequestStopper = null
                    })
                }, suggestDelayMs)
            })
        }
    })


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

})



