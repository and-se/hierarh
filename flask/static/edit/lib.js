let LIB = {
    escapeForHtml(string) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;',
            "/": '&#x2F;',
        };
        const reg = /[&<>"'/]/ig;
        return string.replace(reg, (match) => (map[match]));
    },

    makeUniqueId(prefix) {
        if (prefix && !document.getElementById(prefix)) {
            return prefix
        }
        
        if (!prefix) prefix = "id_";
        let i = 0
        
        let res = prefix + i;
        while (document.getElementById(res)) {
            i++
            res = prefix + i
        }
        
        return res
    },

    createElementByHtml(html) {
        let t = document.createElement('template');
        t.innerHTML = html;
        return t.content.firstElementChild;
    },

    /**
     * Обёртка для запуска функции с задержкой.
     * @param {*} func функция
     * @param {Number} delay величина задержки
     * @returns функция-обёртка, которую надо использовать вместо исходной функции
     */
    debounce(func, delay) {
        let timeoutId;
        return function (...args) {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => func.apply(this, args), delay);
        };
    },

    }
}