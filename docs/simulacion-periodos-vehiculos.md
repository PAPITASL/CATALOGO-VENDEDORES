# Simulación de períodos y compatibilidad — Lujoshop

## Aplicación posterior autorizada: dos períodos comerciales corregidos

Tras la instrucción del usuario de realizar las correcciones correspondientes se aplicó únicamente la parte respaldada por evidencia interna coincidente:

| Producto | Antes | Después | Relación conservada |
|---|---|---|---|
| **301**, manijas interiores | 1988–1998 | **1995–1998** | Modelo **9** |
| **345**, tablero rojo | 1988–1998 | **1990–1994** | Modelo **9** |

Esto reconcilia campos con la información comercial del catálogo, no certifica una equivalencia OEM. Los productos 107 y 108 siguen pendientes por contradicción entre observaciones y nombres de archivo. El 291 requiere identificar la aplicación TBI/motor antes de reducir su cobertura. Los productos 287, 346, 347 y 348 mantienen pendiente la discrepancia 1995–1999. No se ejecutaron divisiones por generaciones ni modificaciones en los modelos.

Se creó `catalogo/management/commands/normalize_product_periods.py`: simula por defecto; al aplicar exige respaldo verificado y coincidencia de ID, nombre, modelo, marca, años del modelo, observaciones y ruta de imagen. Bloquea escrituras concurrentes durante la transacción; comprueba el estado previo contra el respaldo y que el estado posterior de las cuatro tablas solo difiera en esos cuatro campos de años. Ante diferencias o fallo al guardar el registro de reversión revierte toda la transacción. Una segunda ejecución devolvió `Sin cambios`.

Respaldo nuevo: `.vehicle-audit/backup-20261019161530178898/`, con dump PostgreSQL completo, `media.zip` de 3.759 archivos verificados y manifiesto de hashes. Se restauró y comparó el catálogo en la base aislada `vehicle_restore_20261019161530178898` antes de aplicar. Registro con valores originales: `product-periods-20261019T161628602857Z.json` dentro del respaldo. Para revertir, comprobar primero los años aplicados y la FK 9 y restaurar solo los dos pares originales 1988–1998 en una transacción; no sobrescribir otros campos ni restaurar indiscriminadamente el dump sobre la base activa.

Pasaron **29 pruebas** de auditoría, normalización de nombres/períodos y navegación en PostgreSQL separado. Los cuatro casos nuevos de `catalogo/test_product_periods.py` comprueban conservación de campos y FK, límites de filtros públicos, idempotencia, simulación sin escrituras, rechazo de evidencia modificada y rollback ante fallo del registro. Después de aplicar se comprobaron por HTTP las páginas reales del puerto **8002** para 1989, 1990, 1994, 1995 y 1998: el producto 345 aparece en su rango nuevo y el 301 en el suyo; ambos están ausentes en 1989. Todas respondieron 200.

Permanecen 7 marcas, 28 modelos y 611 productos; no se eliminaron ni reasignaron registros, ni se cambiaron rutas, imágenes, categorías, precios o campos comerciales adicionales. Auditoría posterior: `.vehicle-audit/20261019T161641872743Z/report.json` y snapshot verificable. El rango del modelo C/K sigue siendo 1988–1998 porque conserva otros productos pendientes: estas dos correcciones se ven en los productos y filtros por año, no como una división nueva en la pantalla de Modelos.

Las secciones siguientes conservan la simulación anterior como antecedente; sus cinco candidatos no deben confundirse con los dos cambios efectivamente aplicados.

19 de octubre de 2026. **Sin cambios en PostgreSQL.** Se revisaron 10 registros y sus 103 productos: 100 Chevrolet, un Explorer, un CR-V y un Q5. Se leyeron todos los nombres, categorías, observaciones, años y rutas de imágenes. Se inspeccionaron visualmente 16 imágenes representativas; no se afirma inspección visual individual de las 103.

## Resultado técnico

No es correcto eliminar todas las superposiciones imponiendo un mismo corte a iluminación, tableros, techos y mecánica. Actualmente los registros mezclan nombres de vehículos con rangos comerciales de aplicaciones. Dos rangos que se cruzan no demuestran que las filas o sus piezas sean duplicados.

Hay evidencia comercial interna útil que faltaba explicitar en el diagnóstico anterior: **nueve** productos del modelo C/K 9 tienen años específicos en sus observaciones, aunque sus campos de años dicen uniformemente 1988–1998. Son datos a contrastar con proveedor, no compatibilidades OEM ya verificadas. Esto permite preparar cinco correcciones acotadas de producto sin crear modelos ni mover asociaciones; las otras cuatro notas incluyen 1999, fuera del rango registrado, y necesitan revisión adicional.

## Tabla de registros y operaciones

| Registro actual / ID | Corrección o clasificación propuesta | Productos | Justificación | Operación sobre el modelo |
|---|---|---:|---|---|
| C/K SILVERADO / CHEYENNE 1988–1998, **9** | Conservar como agrupación heredada mientras se valida por pieza. Evaluar frontal 1988–1993 / 1994–1998 y tableros tempranos / tardíos por separado, sin imponer los mismos cortes | 94 | Hay observaciones 1990–1994, 1995–1998 y 1995–1999; mezcla luces, interior, mecánica y aplicaciones GMC | **Conservar**; cinco candidatos a editar años de productos, no del modelo |
| SILVERADO 1995–1998, **17** | Candidato C/K Silverado, interior tardío, mismos años, solo si se confirma plataforma | 1: **556**, cubre millare gris | Molde del tablero; no se puede clasificar mediante el cambio de persiana. Foto sin número de parte | **Conservar**; editar denominación únicamente tras confirmar aplicación |
| SILVERADO 1992–1998, **19** | Mantener aplicación mecánica independiente de fases estéticas | 1: **558**, header | La aplicación depende de motor, montaje y escape; no de farolas | **Conservar**; no fusionar con modelos de carrocería |
| SILVERADO 1997–2000, **21** | Identificar plataforma del tablero: C/K/Classic, Tahoe/Suburban u otra aplicación confirmada | 1: **560**, cubre millare beige | La imagen comercial incluye una SUV; no prueba aplicación exclusiva a pickup. Difiere del producto 556 en color y años | **Conservar**; no reasignar por la foto |
| SILVERADO 1990–1998, **31** | Aplicación de frente/óptica por verificar; no aceptar un único rango universal | 1: **575**, kit farolas | Comparar forma, soportes, esquineros, conectores y si requiere conversión de frente | **Conservar**; editar años solo con ficha de este kit |
| SILVERADO 1992–1994, **32** | Candidato C/K, tablero temprano; conservar años y producto | 1: **577**, estructura de millare | La imagen tiene un tablero distinto del cubre millare 556. La foto de pickup no certifica plataforma ni anclajes | **Conservar**; no fusionar con 17, 19, 21 o 31 |
| SILVERADO 2004–2008, **18** | Verificar cabina y montaje del tercer stop antes de distinguir Silverado/Classic | 1: **557**, spoiler tercer stop | El registro cruza años que requieren distinguir versiones; la imagen de montaje no certifica todos los años | **Conservar**; no crear automáticamente 2003–2006, 2007 Classic y 2007–2008 |
| EXPLORER 1993–2000, **20** | Conservar rango comercial pendiente de motor, caja, diámetro y estrías | 1: **559**, set clutch | Las fases candidatas 1991–1994, 1995–1997 y 1998–2001 son insuficientes para clasificar un embrague | **Conservar**; no crear fases de farolas sin productos de ese tipo |
| CR-V 2012–2016, **25** | Conservar cobertura provisional del riel; dividir 2012–2014 / 2015–2016 solo si este accesorio cambia de aplicación | 1: **564**, rieles de techo | Honda documenta cambios de diseño en 2015, pero falta identificar referencia y anclajes de este riel | **Conservar**; no duplicar el producto ni crear dos modelos vacíos |
| Q5 2012–2023, **26** | Determinar si se vende un molde concreto o un producto fabricado por encargo para varias generaciones | 1: **565**, tapetes diamantados | Una foto de un interior no prueba el molde de todas las generaciones. No hay una lista de variantes por año | **Conservar**; no crear cuatro períodos sin tapetes identificados para cada uno |

Las propuestas de clasificación C/K, Classic y fases no son cambios ya aprobados o verificados por número de parte. Ninguna fusión está justificada con la evidencia actual. No se crean registros para Q5 2009–2011, 2024, Explorer 1991–1992, 2001 u otros años sin productos confirmados.

## Cinco correcciones de compatibilidad candidatas

Estas operaciones modifican `Producto.anio_inicio` y `Producto.anio_fin`, manteniendo **modelo_id=9**, categorías, nombres, SKU, precios, observaciones e imágenes originales. Son una simulación basada en las observaciones existentes; requieren validar que esas observaciones son la aplicación comercial correcta y autorización antes de ejecutarse.

| Producto | Pieza | Campos actuales | Candidato | Evidencia interna y límite |
|---|---|---|---|---|
| **107** | Carátula tablero azul | 1988–1998 | **1990–1994** | Observación explícita 1990–1994; el nombre del archivo dice 1988–1994, por lo que existe contradicción y debe confirmarse cuál es correcto |
| **108** | Kit farolas y esquineros smoke | 1988–1998 | **1990–1994** | Misma contradicción observación/archivo que 107; verificar frente y kit específico |
| **291** | Kit admisión de aire | 1988–1998 | **1990–1994** | Observación indica 1990–1994 **TBI**; comprobar motor y montaje, no clasificar por diseño de luces |
| **345** | Tablero rojo | 1988–1998 | **1990–1994** | Coinciden observación y nombre del archivo; aún falta referencia del tablero y versión |
| **301** | Manijas interiores | 1988–1998 | **1995–1998** | Observación explícita; comprobar puerta, lado y aplicación |

Las operaciones serían cinco `UPDATE` por ID, limitados a los campos de años y con condición de estado anterior 1988–1998 y FK 9. **No ejecutados.** Los otros 89 productos de C/K conservarían sus campos; eso no implica que su aplicación 1988–1998 haya quedado técnicamente validada.

Productos **287, 346, 347 y 348**: las observaciones dicen **1995–1999**. No se propone ampliar automáticamente a 1999 ni truncar la nota a 1998. Antes debe identificarse si se trata de C/K continuada/Classic, otra carrocería o un error del catálogo. Son cuatro casos adicionales de discrepancia, separados de los cinco candidatos.

## Diferencias de diseño que deben guiar la clasificación

- **Farolas/persianas C/K:** el kit 108 tiene nota 1990–1994; el 349 tiene nombre de archivo 1995–1999. Las imágenes muestran conjuntos distintos, pero ni el nombre de archivo ni la similitud visual prueban que sean intercambiables. No convertir esos indicios en una regla 1988–1993 / 1994–1998 sin saber versión, óptica original y piezas incluidas en una eventual conversión.
- **Tableros C/K:** las imágenes de estructuras, cubiertas y carátulas distinguen piezas diferentes. Hay notas tempranas 1990–1994 y tardías 1995–1999. Esto requiere una clasificación de interior independiente del frente; un corte general en 1994 puede clasificar mal el tablero.
- **Stops y bómperes:** distinguir cabina, caja/platón, ubicación, soportes y conectores. Un cambio de farola no demuestra que cambie un stop. En el modelo 9 están los stops 317–326, terceros stops 336–337 y bómperes/molduras 261–263, 282, 298, 313 y 316, sin referencia suficiente para repartirlos entre fases.
- **GMC:** productos 273 y 311 nombran GMC; el archivo del 312 también incluye GMC. No clasificarlos como frente Chevrolet solo por estar asociados al modelo 9. Requieren confirmar aplicación y marca sin mover la FK automáticamente.
- **Explorer:** hoy solo se tiene un embrague en ese registro. Las divisiones de diseño de farolas no aportan una clasificación comprobada para esa pieza.
- **CR-V:** hoy solo hay rieles de techo, no kits de farolas o bómperes. Hay que confirmar referencia y puntos de anclaje antes de materializar dos fases.
- **Q5:** hoy solo hay tapetes. Distinguir molde, túnel, anclajes, posición de volante y generación; cambios de farolas o bómperes no identifican el molde vendido.

## Fuentes y aplicación al mercado colombiano

- [Honda, dossier oficial CR-V 2015](https://hondanews.com/en-US/honda-automobiles/releases/release-68e1b3fc42af42a9a3cd90cc1d99c9d2-2015-honda-cr-v-overview): documenta cambios de frente y parte trasera, diferencias de iluminación por versión y rieles de techo. No establece que el riel Lujoshop 564 deje de servir entre 2014 y 2015.
- [Instrucciones originales American Honda para rieles CR-V 2012, conservadas por distribuidor](https://www.hondapartsnow.com/resources/installation/hpn/2012-honda-crv-roof-rack-rails.pdf): identifican aplicación y referencia 08L02-T0A-110. Sirven para contrastar el producto real; su referencia no consta en el registro 564.
- [Audi, presentación de la segunda generación Q5](https://magazine.audi.com.au/article/second-generation-q5-unveiled): anuncia lanzamiento australiano en 2017. No trasladar ese límite sin comprobar año modelo y mercado del vehículo colombiano.
- [Audi, actualización Q5 de 2020](https://www.audi.com/en/press-releases/a-bestseller-gets-even-betteraudi-unveils-a-new-look-for-the-q5-12872): documenta una actualización de diseño. No certifica el tapete 565 ni permite asumir cuatro moldes disponibles.
- [Ford, catálogo original de tren motriz](https://parts.ford.com/content/dam/ford-parts/wcdocs/PowertrainCatalog.pdf): las aplicaciones de embragues se distinguen por motor, transmisión y especificaciones. El registro 559 no contiene esos datos. El enlace fue localizado en búsqueda, pero la apertura completa falló; no se validó allí una equivalencia exacta para ese producto.
- [Chevrolet, manual oficial Silverado Classic 2007](https://www.chevrolet.com/ownercenter/content/dam/gmownercenter/gmna/dynamic/manuals/2007/chevrolet/silverado_1500/2007_chevrolet_silverado_classic_owners.pdf): confirma que Classic requiere identificación específica; no identifica el tercer stop 557.

Se consultaron fuentes originales de fabricantes de otros mercados. No se obtuvo ficha técnica del proveedor de estas piezas ni VIN/versiones de aplicación para Colombia. Por ello **no hay una división universal verificada para todos los productos colombianos**. El filtro comercial debe reflejar aplicaciones confirmadas por pieza y no garantizar compatibilidad por pertenecer a una generación.

## Ejecución simulada y condiciones de una aplicación futura

La simulación utilizó PostgreSQL con `REPEATABLE READ, READ ONLY` y comparó hashes antes/después. Resultado: **10 modelos, 103 productos, cinco candidatos de edición de años; cero altas, fusiones, reasignaciones o escrituras de base de datos**. Se generó inventario de 103 filas con IDs, años, observaciones, categoría, SKU y ruta de imagen. La ejecución no incluye una opción de aplicación.

Evidencia local:

- `.vehicle-audit/20261019T161051289672Z/report.json` y snapshot verificable.
- `.vehicle-audit/periodos-20261019/productos-simulacion.csv`.
- `.vehicle-audit/periodos-20261019/resumen.json`.
- `.vehicle-audit/periodos-inspeccion.jpg`, lámina de inspección de 16 imágenes sin modificar originales.

Para ejecutar cualquiera de los cinco candidatos hace falta confirmar su aplicación, recibir autorización y generar un respaldo nuevo verificable. El comando de aplicación debe comprobar ID, rango anterior, modelo 9, observaciones de evidencia y ausencia de cambios desde el respaldo; actualizar solo los campos de años en una transacción; verificar que el resto de campos y las FKs se mantengan idénticos; probar filtros antes/después y conservar valores originales para revertir. La normalización anterior de nombres no autoriza estos cambios de compatibilidad.

Para una división real de generaciones, primero debe completarse una matriz `producto → plataforma/versión → años confirmados → referencia/fuente`. Cuando una pieza sirva a más de un período, la FK única actual no permite asignarla a varios registros sin una representación adicional. Cualquier cambio de estructura se propondrá aparte; no se duplicará el producto ni se perderá su asociación para forzar el esquema.

**Pendiente:** revisión comercial/técnica de las discrepancias y aprobación del plan concreto antes de actualizar datos reales. No se recomienda aprobar una división o fusión global con la evidencia disponible.
