(() => {
    const button = document.getElementById('download-catalog');
    const dialog = document.getElementById('catalog-download-dialog');
    const confirm = document.getElementById('confirm-catalog-download');
    const status = document.getElementById('catalog-download-status');
    if (!button || !dialog || !confirm || !status) return;
    let generating = false;
    button.addEventListener('click', () => { if (!generating) dialog.showModal(); });
    document.getElementById('cancel-catalog-download').addEventListener('click', () => dialog.close());
    confirm.addEventListener('click', async () => {
        if (generating) return;
        generating = true;
        button.disabled = true;
        confirm.disabled = true;
        dialog.close();
        const originalText = button.textContent;
        button.textContent = 'Generando catálogo...';
        status.hidden = false;
        status.textContent = 'Generando publicaciones... Mantén esta página abierta hasta que comience la descarga.';
        try {
            const response = await fetch(confirm.dataset.url, { credentials: 'same-origin' });
            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                throw new Error(data.error || 'No se pudo preparar el catálogo. Intenta nuevamente.');
            }
            if (!response.headers.get('Content-Type')?.includes('application/zip')) {
                throw new Error('La sesión pudo haber expirado. Recarga la página e inicia sesión nuevamente.');
            }
            const blob = await response.blob();
            const disposition = response.headers.get('Content-Disposition') || '';
            const encoded = disposition.match(/filename\*=utf-8''([^;]+)/i);
            const plain = disposition.match(/filename="([^"]+)"/i);
            const filename = encoded ? decodeURIComponent(encoded[1]) : (plain?.[1] || 'CATALOGO_LUJOSHOP.zip');
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            link.remove();
            setTimeout(() => URL.revokeObjectURL(url), 60000);
            status.textContent = 'Catálogo preparado. La descarga del ZIP ha comenzado.';
        } catch (error) {
            status.textContent = error.message || 'Ocurrió un error al descargar el catálogo.';
        } finally {
            generating = false;
            button.disabled = false;
            confirm.disabled = false;
            button.textContent = originalText;
        }
    });
})();
