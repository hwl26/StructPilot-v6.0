(() => {
const all = document.body.innerText;
const idx = all.indexOf('DEBUG');
if (idx >= 0) {
    return all.substring(Math.max(0, idx-10), idx + 500);
}
return 'NO DEBUG FOUND. Tail of page: ' + all.substring(all.length - 1500);
})()
