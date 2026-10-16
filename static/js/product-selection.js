(() => {
    const panel = document.getElementById('product-selection');
    if (!panel) return;
    const boxes = [...document.querySelectorAll('.product-select')];
    const page = document.getElementById('select-page');
    const clear = document.getElementById('clear-selection');
    const params = new URLSearchParams(location.search);
    params.delete('page');
    params.sort();
    const key = `product-selection:${panel.dataset.user}`;
    const scope = params.toString();
    let selected = new Set();
    try {
        const saved = JSON.parse(sessionStorage.getItem(key));
        if (saved?.scope === scope && Array.isArray(saved.ids)) selected = new Set(saved.ids);
    } catch (_) { /* Selection still works if browser storage is unavailable. */ }
    const links = [...document.querySelectorAll('[data-selection-action]')].map(link => ({
        link, url: link.href, text: link.textContent,
    }));
    const button = document.getElementById('download-catalog');
    const confirm = document.getElementById('confirm-catalog-download');
    const summary = document.getElementById('catalog-download-summary');
    const title = document.getElementById('catalog-download-title');
    const defaults = {url: confirm.dataset.url, button: button.textContent,
        confirm: confirm.textContent, summary: summary.textContent, title: title.textContent,
        disabled: button.disabled};
    const urlFor = original => {
        const url = new URL(original, location.href);
        url.searchParams.delete('selected');
        if (selected.size) url.searchParams.set('selected', [...selected].join(','));
        return url.href;
    };
    function update() {
        boxes.forEach(box => { box.checked = selected.has(box.value); });
        page.checked = boxes.length > 0 && boxes.every(box => box.checked);
        page.indeterminate = boxes.some(box => box.checked) && !page.checked;
        page.disabled = !boxes.length;
        clear.disabled = !selected.size;
        document.getElementById('selection-status').textContent = selected.size
            ? `${selected.size} productos seleccionados. Los botones usarán solo estos productos, incluidos los marcados en otras páginas.`
            : 'Sin selección: los botones usan los filtros actuales. Puedes marcar productos en varias páginas; al cambiar los filtros se limpia la selección.';
        links.forEach(({link, url, text}) => {
            link.href = urlFor(url);
            link.textContent = selected.size ? text.replace(/\(\d+\)/, `(${selected.size} seleccionados)`) : text;
        });
        confirm.dataset.url = urlFor(defaults.url);
        button.disabled = selected.size ? false : defaults.disabled;
        button.textContent = selected.size ? `Descargar catálogo (${selected.size} seleccionados)` : defaults.button;
        confirm.textContent = selected.size ? `Descargar ${selected.size} imágenes` : defaults.confirm;
        summary.textContent = selected.size ? `Se generarán ${selected.size} publicaciones de los productos seleccionados.` : defaults.summary;
        title.textContent = selected.size ? 'Descargar productos seleccionados' : defaults.title;
        try { sessionStorage.setItem(key, JSON.stringify({scope, ids: [...selected]})); } catch (_) {}
    }
    boxes.forEach(box => box.addEventListener('change', () => {
        if (box.checked) selected.add(box.value); else selected.delete(box.value);
        update();
    }));
    page.addEventListener('change', () => {
        boxes.forEach(box => { if (page.checked) selected.add(box.value); else selected.delete(box.value); });
        update();
    });
    clear.addEventListener('click', () => { selected.clear(); update(); });
    update();
})();
