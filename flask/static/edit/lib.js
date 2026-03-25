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

    /**
     * Единственный запрос на объект менеджера. Старый отменяется
     */
    SingleFetchManager: class SingleFetchManager {
        /**
         * @param {String} name - имя для логов
         * @param {*} cancelResponse что отвечать при отмена запроса. Если не задано - кидается исключение.
         */
        constructor(name, cancelResponse) {
            this.currentFetchStopper = null;
            this.name = name;
            this.cancelResponse = cancelResponse;
        }

        async fetch(url, options = {}) {
            this.cancel(); // останавливаем текущий запрос

            this.currentFetchStopper = new AbortController();
            const signal = this.currentFetchStopper.signal;

            try {
                const resp = await fetch(url, {
                    ...options,
                    signal
                });

                this.currentFetchStopper = null;
                return resp;
            } catch (error) {
                if (error.name == 'AbortError') {
                    console.debug(`SingleFetchManager<${this.name}> CANCEL request ${url}`);
                    
                    if (this.cancelResponse !== undefined)
                        console.debug(`SingleFetchManager<${this.name}> return default answer ${this.cancelResponse}`);
                        return this.cancelResponse;
                }

                throw error;
            }
        }

        cancel() {
            if (this.currentFetchStopper) {
                this.currentFetchStopper.abort();
                this.currentFetchStopper = null;
                return true;
            }

            return false;
        }
    },
}