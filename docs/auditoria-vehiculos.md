# Auditoría de vehículos — 19 de octubre de 2026

## Aplicación autorizada y completada

Después de la autorización explícita del usuario se aplicaron los siguientes cambios a la base PostgreSQL **local** configurada en `.env`:

| ID | Antes | Después | Productos vinculados |
|---|---|---|---:|
| 4 | 150 BRONCO | BRONCO | 50 |
| 16 | 150 BRONCO | BRONCO | 31 |
| 25 | CRV | CR-V | 1 |
| 9 | CK SILVERADO CHEYENNE | C/K SILVERADO / CHEYENNE | 94 |

Los 176 productos relacionados conservan todos sus campos. Se compararon **todas las filas y columnas** de marcas, categorías, modelos y productos antes y después dentro de la transacción: únicamente cambiaron los cuatro nombres anteriores. Se conservaron IDs, años, fechas, precios, referencias, observaciones, rutas y claves foráneas. No hubo cambios de esquema, fusiones ni eliminaciones.

Respaldo previo verificado: `.vehicle-audit/backup-20261019154624133428/` contiene `database.dump`, `media.zip` y `manifest.json` con los hashes SHA-256. Se restauró la base completa en `vehicle_restore_20261019154624133428` y se comprobó que todas las filas del catálogo coincidían. El archivo de media contiene 3.759 archivos verificados individualmente con SHA-256. Se conservaron las bases de ensayo y los intentos de respaldo anteriores; ninguno sustituyó ni borró una base existente. La comparación inicial de restauración detectó una diferencia de interpretación de zona horaria: la conexión de prueba ahora se inicializa con la zona de Django antes de comparar; se repitió el respaldo y pasó la verificación antes de modificar datos.

Comando ejecutado:

```powershell
.\.venv\Scripts\python.exe manage.py normalize_vehicle_names --apply --backup-dir '.vehicle-audit/backup-20261019154624133428'
```

El comando bloquea escrituras concurrentes a las cuatro tablas durante la transacción, valida marca/ID/años/nombres originales, comprueba conflictos y la coincidencia con el respaldo, actualiza únicamente `nombre` y aborta ante cualquier diferencia inesperada. Una segunda ejecución terminó con `Sin cambios`, confirmando idempotencia. El registro de reversión se conserva en `applied-20261019T154716215163Z.json`; su estado se anota antes del commit para que un fallo de escritura del registro también provoque rollback. La consulta posterior confirmó que los cuatro nombres quedaron guardados.

Pruebas: 8 de auditoría, 8 de normalización sobre PostgreSQL aislado y 8 de navegación pasaron. Incluyen rollback ante cambios inesperados o fallo al escribir el registro, corrupción de respaldo, conflictos y cambios posteriores al respaldo. Antes y después de aplicar se ejecutaron 19 comprobaciones de vistas (HTTP 200), validación de formularios de edición y filtros por los cuatro modelos en transacciones de solo lectura. Se conservaron los 611 productos y se verificó que ninguna de sus imágenes referenciadas falta. Estas comprobaciones renderizan las vistas de Django; no son una prueba visual en navegador ni un despliegue remoto.

Archivos nuevos de esta fase: `catalogo/vehicle_safety.py`, `catalogo/management/commands/backup_vehicle_catalog.py`, `catalogo/management/commands/normalize_vehicle_names.py`, `catalogo/test_vehicle_normalization.py`. También se amplió `catalogo/test_vehicle_audit.py` con la comparación de instantes entre zonas horarias.

Auditoría posterior: `.vehicle-audit/20261019T154723191001Z/report.json`. Mantiene 7 marcas, 28 modelos y 611 productos; quedan ocho propuestas pendientes (siete registros F150_LOBO y un SILVEADO). No se alteraron esas denominaciones, las aplicaciones GMC ni los rangos de compatibilidad por falta de evidencia técnica. La autorización permite las correcciones correspondientes, pero no demuestra compatibilidad de piezas. No se subieron cambios a GitHub ni se ejecutaron sobre otra base remota.

Para revertir estos cuatro nombres: utilizar los valores `antes` del registro, comprobar primero que cada ID conserve el nombre `despues`, su marca y sus años, revisar colisiones y actualizar únicamente el campo `nombre` en una transacción. Verificar después que todos los demás campos coincidan. No restaurar indiscriminadamente el dump o el snapshot sobre la base activa; la base de ensayo conserva la copia previa para una recuperación aislada.

Las secciones siguientes conservan el análisis **anterior a la aplicación** como antecedente.

## Resultado y alcance

Se ejecutó únicamente análisis y simulación sobre la conexión PostgreSQL configurada en este entorno. No se puede afirmar que sea la misma base de producción sin verificar el despliegue. Se detectaron 7 marcas, 28 modelos y 611 productos. No se modificaron registros, imágenes, filtros, formularios ni diseño. No se ejecutaron migraciones.

El comando nuevo `audit_vehicle_models --dry-run` usa una transacción PostgreSQL `REPEATABLE READ, READ ONLY`. No contiene opción de aplicación. Guarda el detalle de todos los modelos y productos vinculados, observaciones, referencias, precios y rutas originales en archivos locales excluidos de Git mediante `.vehicle-audit/`.

## Registros reales

| ID | Marca | Modelo actual | Años | Productos |
|---|---|---|---|---:|
| 1 | FORD | F150_LOBO | 1997–2003 | 108 |
| 2 | FORD | F150_LOBO | 2004–2008 | 61 |
| 4 | FORD | 150 BRONCO | 1992–1996 | 50 |
| 8 | FORD | F150_LOBO | 2009–2014 | 43 |
| 9 | CHEVROLET | CK SILVERADO CHEYENNE | 1988–1998 | 94 |
| 12 | FORD | F150_LOBO | 2015–2017 | 57 |
| 13 | FORD | F150_LOBO | 2018–2020 | 50 |
| 14 | FORD | F150_LOBO | 2021–2023 | 47 |
| 15 | FORD | F150_LOBO | 2024–2026 | 35 |
| 16 | FORD | 150 BRONCO | 1987–1991 | 31 |
| 17 | CHEVROLET | SILVERADO | 1995–1998 | 1 |
| 18 | CHEVROLET | SILVERADO | 2004–2008 | 1 |
| 19 | CHEVROLET | SILVERADO | 1992–1998 | 1 |
| 20 | FORD | EXPLORER | 1993–2000 | 1 |
| 21 | CHEVROLET | SILVERADO | 1997–2000 | 1 |
| 22 | CHEVROLET | C10 | 1981–1987 | 1 |
| 23 | JEEP | CHEROKEE XJ | 1984–2001 | 1 |
| 24 | BMW | SERIE 3 E90 | 2006–2008 | 1 |
| 25 | HONDA | CRV | 2012–2016 | 1 |
| 26 | AUDI | Q5 | 2012–2023 | 1 |
| 27 | FORD | EDGE | 2007–2010 | 17 |
| 28 | CHEVROLET | TRAILBLAZER | 2002–2008 | 1 |
| 29 | VOLKSWAGEN | GOLF MK4 | 1999–2005 | 1 |
| 30 | FORD | RANGER | 2001–2008 | 1 |
| 31 | CHEVROLET | SILVERADO | 1990–1998 | 1 |
| 32 | CHEVROLET | SILVEADO | 1992–1994 | 1 |
| 33 | FORD | RANGER | 2023–2024 | 1 |
| 34 | FORD | EDGE | 2011–2014 | 2 |

Se detectaron seis superposiciones entre los IDs 17, 19, 21 y 31 (cada combinación de dos). Al considerar también los nombres candidatos C/K y SILVEADO, hay 13 cruces de años que requieren revisión; agruparlos para el informe no significa que sean el mismo vehículo. No se detectaron duplicados exactos ni colisiones de nombre y rango para las propuestas. Tampoco hay productos fuera del rango de su modelo, modelos con años invertidos ni productos sin modelo en el snapshot.

## Correcciones recomendadas y pendientes

| IDs | Propuesta | Productos vinculados | Decisión |
|---|---|---:|---|
| 25 | CRV → CR-V | 1 | Proponer solo escritura, conservar 2012–2016 |
| 4, 16 | 150 BRONCO → BRONCO | 81 | Proponer solo escritura, conservar ambos períodos |
| 9 | CK SILVERADO CHEYENNE → C/K SILVERADO / CHEYENNE | 94 | Proponer escritura; revisar aplicaciones GMC |
| 1, 2, 8, 12, 13, 14, 15 | F150_LOBO → F-150 | 401 | Pendiente: existe evidencia explícita de LOBO |
| 32 | SILVEADO → C/K SILVERADO | 1 | Pendiente: no está confirmada la carrocería |

Las 12 propuestas de nombre abarcan 578 productos, pero ninguna está aplicada ni aprobada. El resto conserva sus nombres. Los rangos candidatos del pedido son hipótesis comerciales, no compatibilidades verificadas. No se investigaron fuentes externas ni se confirmó equivalencia técnica por pieza: hace falta referencia de fabricante/proveedor, número de parte y mercado para cada aplicación dudosa.

Evidencia interna relevante:

- Producto **77**, modelo **1**: `EXTENSION SUPERIOR BUMPER DELANTERO 1999- 2003`, observaciones `LOBO 1999- 2003`. No quitar LOBO: no existe campo de variante en el modelo actual. Conservar el nombre hasta decidir cómo mantener esa distinción sin perder información.
- Productos **273** (`EMBLEMA GMC`) y **311** (`PERSIANA GMC FONDO NEGRO BOCEL CROMADO`) están vinculados al modelo Chevrolet **9**. No trasladarlos ni asumir equivalencia entre GMC y Chevrolet.
- Modelo **17**, producto **556**: cubre millare gris 1995–1998.
- Modelo **19**, producto **558**: header de acero inoxidable 1992–1998. No aplicar segmentación de farolas o carrocería a esta pieza mecánica.
- Modelo **21**, producto **560**: cubre millare beige 1997–2000. No fusionarlo automáticamente con el producto 556; cambian color y rango.
- Modelo **31**, producto **575**: farolas con cocuyos LED 1990–1998; requiere verificación de ópticas y carrocería.
- Modelo **32**, producto **577**: millare esqueleto 1992–1994, sin evidencia adicional en observaciones.
- Modelo **18**, producto **557**: spoiler tercer stop 2004–2008. Tampoco convertir este rango al esquema candidato de Silverado sin verificar la pieza.
- Explorer **20**, producto **559**: set clutch 1993–2000. Los cambios visuales de carrocería no prueban compatibilidad de embrague.
- CRV **25**, producto **564**: rieles de techo 2012–2016. No dividir automáticamente en 2012–2014 y 2015–2016.
- Q5 **26**, producto **565**: tapetes diamantados 2012–2023. No dividir ni ampliar el rango por generaciones sin verificar molde y aplicación.

El detalle completo de los 611 productos, con sus IDs y observaciones, está en el informe JSON local.

## Estructura y validaciones existentes

- Tablas: `marcas`, `modelos_vehiculo`, `categorias`, `productos`.
- `modelos_vehiculo.marca_id → marcas.id`: `PROTECT` en Django.
- `productos.modelo_id → modelos_vehiculo.id`: `PROTECT` en Django. Las restricciones reales PostgreSQL se exportan al informe JSON.
- La relación es un modelo por producto. Dividir generaciones y representar una pieza en varios modelos requeriría diseñar la compatibilidad; no se implementó un cambio estructural.
- La unicidad actual cubre marca, nombre y años; con años nulos la unicidad PostgreSQL predeterminada no garantiza evitar todos los duplicados. La auditoría detecta coincidencias también con nulos y normaliza espacios/capitalización solo para comparar.
- Ya existen restricciones para impedir años finales menores a iniciales.
- `ModeloVehiculoForm` normaliza mayúsculas y espacios exteriores y bloquea superposiciones del mismo nombre. El administrador usa su formulario propio; `ProductoForm.save()` puede crear modelos directamente. Por ello la validación de superposición no es uniforme entre vías de entrada.
- Se recomienda tratar superposiciones como advertencia y exigir justificación de versión/aplicación antes de permitirlas. El sistema no tiene campo de justificación o variante. No se cambió esta política sin acordar cómo conservar la justificación.
- La búsqueda pública utiliza IDs de marca/modelo y el selector obtiene años desde productos activos. Conservar IDs y años evita cambiar esas relaciones; un renombrado sí puede cambiar resultados de búsquedas por texto y documentos nuevos.

## Código y comandos

Archivos modificados en esta fase:

- `.gitignore`: excluir informes locales que incluyen datos comerciales.
- `catalogo/management/commands/audit_vehicle_models.py`: auditoría exclusivamente de lectura y snapshot verificable.
- `catalogo/test_vehicle_audit.py`: siete pruebas de detección y protección.
- `docs/auditoria-vehiculos.md`: este informe.

Para repetir la simulación desde PowerShell:

```powershell
.\.venv\Scripts\python.exe manage.py audit_vehicle_models --dry-run
.\.venv\Scripts\python.exe manage.py test catalogo.test_vehicle_audit --noinput
```

No se propone una migración de esquema para corregir escritura. Después de autorización y de delimitar los IDs aprobados, se prepararía un comando de aplicación específico: transacción atómica, bloqueo de filas, verificación de valores originales y colisiones, renombrado por ID e idempotencia. Debe abortar ante diferencias con el plan aprobado y verificar productos, FKs y rutas antes/después. No existe todavía un comando de aplicación ejecutable.

## Respaldo y reversión

Snapshot final de esta fase:

`.vehicle-audit/20261019T153725919806Z/snapshot.json`

SHA-256: `5abc673e7eca373bacdf526fd964706b26e91636ad29a400391593a203feadba`

Se verificaron lectura del archivo, hash, conteos por entidad y referencias producto→modelo→marca. Es un respaldo de los registros auditados, con precios, observaciones, rutas y relaciones originales, no un backup integral de PostgreSQL. No incluye bytes de imágenes ni las tablas de trabajos de imágenes, usuarios u otras aplicaciones. No se realizó ensayo de restauración. Antes de aplicar, generar y probar un backup integral PostgreSQL más media en un entorno aislado y obtener un snapshot nuevo.

Para revertir un futuro renombrado, restaurar únicamente el nombre anterior por ID dentro de una transacción, comprobando que el nombre actual siga siendo el aplicado y que las relaciones no hayan cambiado. No cargar indiscriminadamente el snapshot sobre una base activa: podría sobrescribir cambios comerciales posteriores. Divisiones, fusiones y borrados no están autorizados ni implementados.

## Pruebas, límites y autorización

Las siete pruebas pasaron: límites inclusivos de superposición, aislamiento por marca, colisiones de alias conservando datos e IDs, repetibilidad, años desconocidos, revisión Chevrolet, evidencia de variante Lobo y rechazo de backend sin garantía PostgreSQL (varios aspectos se comprueban en una misma prueba). La comprobación de Django no reportó problemas.

Se ejecutó la simulación dos veces; ambas detectaron 7 marcas, 28 modelos, 611 productos y 12 propuestas de nombre. La transacción PostgreSQL impide escrituras durante las lecturas. No se probaron navegación ni formularios en navegador, restauración integral o una aplicación de cambios: no se han alterado esas funciones ni datos. Las pruebas actuales no sustituyen la validación posterior a un futuro renombrado.

Se requiere autorización explícita del usuario antes de modificar datos reales. Recomendación inicial: aprobar únicamente escritura de los modelos **4, 16, 25 y 9**, conservando años e IDs, y dejar **F150_LOBO**, **SILVEADO**, las segmentaciones y las aplicaciones GMC pendientes de revisión comercial. El nombre de marca del modelo 9 sigue siendo Chevrolet; el renombrado no resuelve sus productos GMC.
