(() => {
    const status = document.getElementById('clean-image-progress');
    if (!status || status.dataset.active !== 'true') return;
    const form = document.getElementById('clean-image-process');
    async function poll() {
        try {
            const processed = await fetch(form.action, {
                method: 'POST', credentials: 'same-origin',
                headers: {'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value}
            });
            if (!processed.ok || processed.redirected) throw new Error('process');
            const url = new URL(window.location.href);
            url.searchParams.set('status', '1');
            const response = await fetch(url, {credentials: 'same-origin'});
            if (!response.ok || response.redirected) throw new Error('session');
            const data = await response.json();
            status.textContent = `Procesados ${data.processed} de ${data.total}. Exitosos: ${data.successful}. Con error: ${data.failed}.`;
            if (!data.active) { window.location.reload(); return; }
            setTimeout(poll, 100);
        } catch (_) {
            status.textContent = 'No se pudo consultar el progreso. Recarga la página para volver a consultar; el trabajo guardado se conserva.';
        }
    }
    poll();
})();
