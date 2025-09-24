'use strict'
document.addEventListener('DOMContentLoaded', function() {
    console.log('inp')
    document.querySelectorAll('input-select').forEach(el => {        
        let placeholder = el.innerText.trim()
        el.innerHTML = `
            <input placeholder="${sf(placeholder)}" >
        `
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
})



