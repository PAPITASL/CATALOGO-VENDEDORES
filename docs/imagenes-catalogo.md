# Ajustar imagenes de catalogo

Este flujo es independiente de Descargar catalogo. Usa todos los productos
filtrados antes de paginar, igual que el total del listado.

No utiliza IA, API, claves ni servicios externos. Solo requiere Pillow.
Se ajusta proporcionalmente la foto completa dentro de 800 x 600, se centra
y se rellena el espacio libre con blanco. No se recorta ni elimina el fondo
original. Se conserva la orientacion EXIF. Las transparencias se componen
sobre blanco y se exporta JPG de calidad 95; el original no se sobrescribe.

## Uso

Productos -> Generar imagenes catalogo -> Generar.
Mantener abierta la pagina para procesar las fotos y ver el progreso.
Si se cierra, los resultados se conservan y se continua al regresar.
No requiere iniciar otro proceso. El comando opcional
`python manage.py process_catalog_images` permite continuar en segundo plano.

Los JPG quedan en `catalogo_limpio/<trabajo>/<resultado>/` con nombres
MARCA_MODELO_ANIO-ANIO_PIEZA.jpg. Los duplicados reciben un sufijo.
Se pueden descargar individualmente o en ZIP al finalizar. Los fallos
se informan por producto y en errores.txt dentro del ZIP.

## Instalacion y pruebas

Instalar requirements.txt y aplicar `python manage.py migrate`.
Ejecutar `python manage.py collectstatic --noinput` en produccion.
`python manage.py test` verifica filtros, ajuste, permisos, archivos y ZIP.
