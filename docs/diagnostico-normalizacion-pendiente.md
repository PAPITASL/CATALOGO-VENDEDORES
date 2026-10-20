# Diagnóstico de normalización pendiente

## Actualización: ocho renombrados autorizados y aplicados

Tras la autorización del usuario se aplicó la primera parte del plan de este documento:

- IDs **1, 2, 8, 12, 13, 14 y 15**: `F150_LOBO` → **F-150 / LOBO**.
- ID **32**: `SILVEADO` → **SILVERADO**, conservando **1992–1994**.

Se verificó dentro de una transacción que las cuatro tablas del catálogo coincidan exactamente con el estado anterior excepto por esos ocho campos `nombre`. Los 402 productos vinculados conservaron todos sus campos y asociaciones. Permanecen 7 marcas, 28 modelos y 611 productos. No se aplicaron divisiones de generaciones ni cambios de compatibilidad.

Respaldo nuevo: `.vehicle-audit/backup-20261019160009506647/`, con dump completo PostgreSQL, `media.zip` de 3.759 archivos y manifiesto SHA-256. Se comprobó la restauración en la base aislada `vehicle_restore_20261019160009506647` antes de aplicar. Registro de valores anteriores para reversión: `applied-20261019T160056708201Z.json` dentro de esa carpeta. Se conserva el procedimiento de reversión descrito más abajo: solo nombres por ID y comprobación del estado actual, sin sobrescribir los demás datos.

El comando `normalize_vehicle_names` ahora incluye las ocho operaciones nuevas además de las cuatro anteriores, que detecta como ya aplicadas. La simulación mostró exactamente ocho actualizaciones; la aplicación terminó correctamente, y repetirla devolvió `Sin cambios`. Pasaron **25 pruebas** de auditoría, normalización y navegación sobre una base de pruebas separada, incluida una prueba nueva que preserva los cambios anteriores, la distinción LOBO y un registro Silverado superpuesto fuera del plan.

Después de aplicar, `/catalogo/modelos/` respondió HTTP 200 al renderizar con administrador y sus 28 registros coincidieron con PostgreSQL. Las siete rutas públicas de marca en el servidor real **127.0.0.1:8002** muestran los IDs, nombres y rangos actuales, incluidos los ocho corregidos. La auditoría posterior está en `.vehicle-audit/20261019T160107674331Z/report.json`: cero propuestas de ortografía de las reglas actuales, lo que **no** implica compatibilidad por generaciones validada.

Continúan pendientes los rangos Silverado, C/K, Q5, Explorer y CR-V indicados en el diagnóstico. La validación general del formulario sigue bloqueando superposiciones; no se cambió esa política ni se afirma que ahora permita editar libremente los registros Silverado superpuestos. No hubo despliegue remoto ni publicación en GitHub.

El diagnóstico siguiente se conserva como antecedente anterior a esta aplicación.

Comprobación del 19 de octubre de 2026. Solo lectura; no se modificaron datos ni código de funcionamiento en esta revisión.

## Causa de la corrección parcial

La corrección previa sí se ejecutó en PostgreSQL, pero su alcance fue únicamente cuatro filas: IDs 4 y 16 a BRONCO, ID 25 a CR-V e ID 9 a C/K SILVERADO / CHEYENNE. El archivo `catalogo/vehicle_safety.py`, constante `PLAN`, contiene exactamente esas cuatro operaciones. El registro `applied-20261019T154716215163Z.json` y los valores actuales corroboran la aplicación. No existe una operación implementada que divida generaciones ni corrija F150_LOBO o SILVEADO. La autorización anterior se utilizó para esos cuatro cambios; las demás propuestas quedaron pendientes de evidencia técnica, no de un fallo al guardar.

La normalización completa, por tanto, **no está terminada**. Ni recargar el navegador ni ejecutar las migraciones existentes completa esas operaciones ausentes.

## Conexión, vista y servidor

- Configuración efectiva: `django.db.backends.postgresql`, host `localhost`, puerto `5432`, base `lujoshop`.
- Confirmación SQL de la conexión: `current_database() = lujoshop`, servidor `::1`, puerto `5432`, esquema `public`.
- En el proceso de comprobación no hay `DATABASE_URL` que reemplace esa configuración. `load_dotenv` no sobrescribe variables ya existentes; `dj_database_url.config` sí puede dar prioridad a `DATABASE_URL` si otro proceso la define.
- Las seis migraciones de catálogo figuran aplicadas. Los renombrados se ejecutaron mediante comando de administración, no mediante migración.
- `/catalogo/modelos/` resuelve a `catalogo:modelovehiculo_list`. Su implementación en `catalogo/views.py` consulta `ModeloVehiculo.objects.all()` y renderiza `catalogo/modelo_list.html`, que muestra directamente `object.nombre`, `anio_inicio` y `anio_fin`.
- Se ejecutó esa misma vista con RequestFactory y un usuario administrador existente, dentro de una transacción PostgreSQL `READ ONLY`. Respondió HTTP 200 y su contexto contiene exactamente los 28 IDs y nombres obtenidos por ORM. Se comparó sin depender del orden: la vista no especifica ordenación y las filas renombradas pueden aparecer al final.
- Se consultaron las siete páginas públicas de selección de marca del servidor real `127.0.0.1:8002`. Todas respondieron HTTP 200; los 28 modelos coinciden en ID, nombre y rango con la consulta local. No hay indicios de otra base o de caché como causa. No se inspeccionó el entorno interno del proceso servidor: la prueba verifica su contenido servido, no sus credenciales.
- El acceso HTTP a `/catalogo/modelos/` requiere autenticación y redirige al login en una sesión anónima. No se utilizó ni alteró la sesión del usuario para probarlo.

Los hashes de las cuatro tablas del catálogo antes/después de esta revisión coinciden. Se mantienen 7 marcas, 28 modelos y 611 productos.

## Comparación y relaciones afectadas

| IDs | Actual en PostgreSQL | Propuesta | Productos vinculados | Operación propuesta ahora |
|---|---|---|---:|---|
| 1, 2, 8, 12, 13, 14, 15 | FORD F150_LOBO | F-150 / LOBO, mismos años | 401 | Renombrar siete filas conservando explícitamente LOBO |
| 32 | CHEVROLET SILVEADO 1992–1994 | SILVERADO 1992–1994 | 1 | Corregir solo ortografía; no asignar C/K sin evidencia |
| 17 | SILVERADO 1995–1998 | Aplicación por verificar; candidatos C/K 1988–1993 y 1994–1998 | 1 | No cambiar rango ni relación todavía |
| 19 | SILVERADO 1992–1998 | Misma revisión, específica para escape | 1 | No dividir según cambios de carrocería |
| 21 | SILVERADO 1997–2000 | Revisar transición C/K/Silverado por pieza y mercado | 1 | No ampliar, reducir ni reasignar |
| 31 | SILVERADO 1990–1998 | Revisar ópticas antes de separar 1988–1993 y 1994–1998 | 1 | No inferir compatibilidad por nombre |
| 18 | SILVERADO 2004–2008 | Revisar candidatos 2003–2006, 2007 Classic y otras carrocerías si corresponde | 1 | No reemplazar por un único período candidato |
| 9 | C/K SILVERADO / CHEYENNE 1988–1998 | Candidatos 1988–1993 y 1994–1998 | 94 | No crear dos modelos vacíos ni repartir piezas automáticamente |
| 26 | AUDI Q5 2012–2023 | Candidatos 2009–2012, 2013–2017, 2018–2020, 2021–2024 | 1 | Sin altas ni ampliación a 2009/2024; verificar tapetes |
| 20 | FORD EXPLORER 1993–2000 | Candidatos 1991–1994, 1995–1997, 1998–2001 | 1 | Sin ampliar a 1991/2001; verificar embrague |
| 25 | HONDA CR-V 2012–2016 | Candidatos 2012–2014 y 2015–2016 | 1 | Verificar rieles de techo antes de dividir |

F150_LOBO conserva los siete rangos actuales: 1997–2003 (108 productos), 2004–2008 (61), 2009–2014 (43), 2015–2017 (57), 2018–2020 (50), 2021–2023 (47), 2024–2026 (35). La propuesta F-150 / LOBO conserva la distinción existente dentro del mismo campo; no declara que cada pieza sirva a todas las versiones ni necesita nueva columna. Renombrar a F-150 sin conservar LOBO perdería información comercial: el producto 77 tiene observación explícita `LOBO 1999- 2003`.

Se detectaron seis pares de rangos superpuestos entre 17, 19, 21 y 31. No son duplicados exactos por marca/nombre/rango y tienen productos distintos. No hay evidencia suficiente para fusionar sus registros ni sus productos. Cambiar SILVEADO a SILVERADO introducirá ese nombre en las advertencias de superposición, pero no colisiona con la restricción única: no existe otro SILVERADO 1992–1994. La validación de formulario actualmente bloquea superposiciones: una corrección controlada por comando debe distinguir una advertencia comercial de una colisión única real, sin desactivar la protección general silenciosamente.

## Piezas que impiden una división automática

| Modelo | Producto / SKU interno | Pieza y evidencia disponible | Falta para decidir |
|---|---|---|---|
| 17 | 556 | Cubre millare gris 1995–1998 | Referencia, molde y aplicación del fabricante |
| 19 | 558 | Header acero inoxidable 1992–1998 | Motor, escape, transmisión si corresponde y número de parte |
| 21 | 560 | Cubre millare beige 1997–2000 | Carrocería/tablero y molde exactos; no es el mismo producto 556 |
| 31 | 575 | Farolas con cocuyos LED 1990–1998 | Frente, fijaciones, conectores y referencia |
| 18 | 557 | Spoiler tercer stop, LED y luz de carga, 2004–2008 | Cabina, montaje y aplicaciones por número de parte |
| 32 | 577 | Millare esqueleto 1992–1994; observación solo entrega inmediata | Confirmar plataforma C/K antes de añadirla al nombre |
| 26 | 565 | Tapetes diamantados 2012–2023 | Molde, carrocería/generación, especificación del proveedor |
| 20 | 559 | Set clutch 1993–2000; sin especificación técnica | Motor, caja, diámetro/estrías y referencia OEM/proveedor |
| 25 | 564 | Rieles techo aluminio 2012–2016 | Tipo de techo, anclajes y referencia |

Los 94 productos del modelo 9 tienen **todos** `anio_inicio=1988` y `anio_fin=1998`. Sus categorías incluyen iluminación, interior, carrocería, emblemas y escape. Además, contiene los productos GMC 273 (emblema) y 311 (persiana). La información actual no permite asignar todos a Chevrolet o GMC ni a un frente concreto. El JSON de auditoría conserva el inventario completo de esos productos, sus observaciones e IDs.

## Fuentes técnicas y límites de la evidencia

- Ford publica la denominación [F-150/Lobo en sus manuales oficiales de 2024](https://www.ford.mx/mi-ford/vehiculo/f-150-lobo/2024/manual-propietario/). Apoya conservar la denominación comercial; no verifica compatibilidad de todos los años del inventario.
- El [catálogo oficial Ford de tren motriz](https://parts.ford.com/content/dam/ford-parts/wcdocs/PowertrainCatalog.pdf) diferencia embragues por motor/caja y especificaciones. Un cambio de frente de Explorer no basta para reasignar el producto 559.
- La [cronología oficial Honda CR-V](https://hondanews.com/en-US/honda-automobiles/releases/release-13f25e90cfe47cd58453f1f710057d45-honda-cr-v-timeline-and-milestones) y el [folleto oficial Honda 2015](https://automobiles.honda.com/images/2015/full-line-brochure.pdf) documentan cambios de diseño. No prueban que los rieles 564 cambien de anclaje.
- Audi presenta la [segunda generación Q5 y su lanzamiento australiano en 2017](https://magazine.audi.com.au/article/second-generation-q5-unveiled). Demuestra que los límites dependen del mercado/año modelo; no confirma sin más el corte 2018 para Colombia ni el molde de tapetes 565.
- Existe un [manual oficial Chevrolet Silverado Classic 2007](https://www.chevrolet.com/ownercenter/content/dam/gmownercenter/gmna/dynamic/manuals/2007/chevrolet/silverado_1500/2007_chevrolet_silverado_classic_owners.pdf). La denominación Classic requiere distinguirse; ese manual no identifica el spoiler 557 ni confirma su rango.

Las fuentes generales no sustituyen fichas de compatibilidad de las piezas que vende Lujoshop. Los rangos candidatos siguen pendientes de verificar por pieza y mercado colombiano. No presento esos candidatos como datos ya comprobados.

## Operaciones exactas propuestas para autorizar

Primera parte, ocho actualizaciones de nombre sobre los IDs existentes:

1. IDs **1, 2, 8, 12, 13, 14 y 15**: `F150_LOBO` → `F-150 / LOBO`. Mantener marca, años, IDs y todos los campos restantes.
2. ID **32**: `SILVEADO` → `SILVERADO`. Mantener 1992–1994 y la FK del producto 577; no añadir C/K ni fusionar con otro registro.

Son **402 productos vinculados** cuya FK y cuyos campos no se actualizarían. Antes de aplicar: nuevo respaldo verificado (el existente es previo a los cuatro cambios anteriores), snapshot de filas/relaciones y plan con valores originales. Dentro de una transacción: bloquear las tablas implicadas, comprobar marca/ID/nombre/años contra el plan, comprobar colisiones únicas, actualizar exclusivamente `nombre` por ID y verificar que el resto de filas/campos sea idéntico. Abortar todo ante discrepancias. La segunda ejecución debe quedar sin cambios.

El comando `normalize_vehicle_names` actual **no incluye** estas ocho actualizaciones: habría que ampliarlo, añadir los casos de prueba correspondientes y ejecutar primero simulación. No requiere migración de esquema. En esta revisión no se modificó ese comando ni se ejecutó `--apply`.

Segunda parte, normalización real de compatibilidad: **cero operaciones sobre datos por ahora**. Preparar una matriz por producto con número de parte, plataforma, mercado, variante, rango confirmado y fuente. Para los productos 556, 557, 558, 559, 560, 564, 565, 575, 577 y los 94 del modelo 9, faltan las comprobaciones específicas de la tabla anterior. Después se podrá entregar un plan que indique exactamente qué registro existente se conserva, qué asociaciones cambian y por qué. No crear generaciones vacías para aparentar que la revisión está terminada.

El esquema actual es `Producto.modelo_id` (una FK protegida), con un rango adicional en cada producto. No permite relacionar un mismo producto con varios registros de generaciones. Dividir Q5, CR-V o C/K y conservar todas las aplicaciones de piezas que abarcan más de una división requiere resolver esa representación. Una tabla explícita de compatibilidades podría ser necesaria, pero sería un cambio estructural sujeto a una propuesta y autorización específicas. No se implementó ni se añadieron modelos/tablas.

Reversión de la primera parte: recuperar exclusivamente los nombres originales por esos ocho IDs, comprobando antes que conserven el nombre aplicado, la marca, los años y las relaciones esperadas. No restaurar un dump completo sobre la base activa ni sobrescribir precios/cambios posteriores.

## Evidencia local y estado final

- Auditoría nueva: `.vehicle-audit/20261019T155656688102Z/report.json` y su `snapshot.json` verificado.
- Diagnóstico de conexión/vista/servidor: `.vehicle-audit/diagnostico-pendientes.json`.
- Comprobaciones ejecutadas: auditoría PostgreSQL de solo lectura, consulta de migraciones, renderizado autenticado sin sesión persistente, comparación de los 28 modelos con las siete rutas públicas del servidor 8002, relaciones y observaciones de productos, comprobación de hash antes/después.
- No se ejecutaron pruebas de aplicación ni una migración nueva: esta fase es diagnóstico y no cambia código de ejecución.
- **Pendiente de autorización nueva para las ocho correcciones de nombre.** La normalización por generaciones sigue pendiente de evidencia y de acordar la representación de compatibilidades múltiples; autorizar los nombres no aprueba ni verifica esas divisiones.
