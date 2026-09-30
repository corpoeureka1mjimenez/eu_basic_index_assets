# eu_fast_config — Preparación de Entorno

Funcionalidad de `eu_fast_config` que automatiza y organiza la preparación de un entorno de Odoo. Cuando se crea una instancia desde cero, en lugar de instalar los addons uno a uno, configurar la compañía a mano y cargar data de ejemplo registro por registro, permite definir **perfiles por industria** (aplicaciones + parametrización + data de prueba) y ejecutar todo el flujo en un solo paso, guiado por un modal visible en todo el sistema.

- **Versión:** 19.0.1.17.x (ver `__manifest__.py` para el patch exacto)
- **Licencia:** OPL-1
- **Responsable:** Manuel Jimenez
- **Soporte:** proyectos@corpoeureka.com

---

## ¿Qué hace?

### 1. Flujo general

1. Se instala `eu_fast_config` en una instancia nueva.
2. Un `post_init_hook` crea automáticamente una preparación llamada **"Iniciar Preparación Demo"** (solo en la primera instalación, no en upgrades).
3. Al entrar al webclient, el administrador ve un **FAB flotante** en el lateral derecho (arrastrable verticalmente, posición persistida en `localStorage`).
4. Al hacer click en el FAB se abre el **modal de preparación**: elige una industria (perfil) y/o aplicaciones individuales, revisa las **Opciones Avanzadas** (parametrización automática / data de prueba) y pulsa **Iniciar Preparación**.
5. El backend guarda la selección en la preparación y ejecuta, en orden, los tres pasos del perfil:
   1. **Instala** las aplicaciones en un solo lote (Odoo resuelve el orden de dependencias). No respalda la base antes: eso es responsabilidad de infraestructura, no de este flujo.
   2. **Parametriza** la instancia aplicando la plantilla JSON exportada desde `eu_fast_config` (moneda, diarios, almacenes, impuestos, etc.), si el perfil la tiene y la opción está activa.
   3. **Carga data de prueba**: los datasets CSV del perfil (clientes, proveedores, productos, listas de precio, órdenes, facturas, etc.), en el orden definido, si el perfil los tiene y la opción está activa.

   Al terminar, la preparación queda marcada como ejecutada y el modal no vuelve a aparecer.
6. Alternativamente, el usuario puede **Ignorar** la preparación (con confirmación), lo que también oculta el modal de forma permanente.

### 2. Modelos

| Modelo | Descripción |
|---|---|
| `profile.entorno` | **Perfil Demo / Industria.** Agrupa las aplicaciones, la parametrización y la data de prueba de un tipo de negocio. Hereda `mail.thread` (chatter) para poder avisar ahí los faltantes al importar. Campos: `name`, `description`, `image_1024`/`image_128`, `addon_image` (fallback de imagen), `addons_ids`, `config_json`/`config_json_filename` (plantilla Fast Config) + `automatic_parameterization` (bool), `data_demo_ids` (datasets) + `demo_data` (bool). Botón **Exportar Perfil** (`action_export_profile`) para bajarlo como `.zip` portable — ver sección "Exportar / Importar Perfiles". |
| `module.entorno` | **Línea de aplicación.** Vincula un `ir.module.module` a un perfil (`profile_id`) o a una preparación (`preparation_id`). Campos related de solo lectura: `technical_name` y `status`. Constraints únicos por perfil y por preparación. |
| `data.entorno` | **Dataset de data de prueba.** Línea de un perfil (`profile_id`) con `name`, `sequence` (orden de carga), `res_model` (modelo destino, ej. `res.partner`, `product.template`, `sale.order`), `data_file`/`data_file_filename` (CSV), `active` (permite desactivar un dataset sin borrarlo) y `required_module_ids` (m2m a `ir.module.module`: módulos que deben estar instalados para que los campos del CSV existan, ej. `stock` para `is_storable` en `product.template`). Un perfil puede tener varios, cargados en orden con el motor nativo `Model.load()`. Botón **Validar** (`action_validate_dataset`) para probar el CSV contra el modelo destino sin guardar nada. |
| `entorno.preparation` | **Preparación de Entorno.** El registro que dispara el modal. Campos: `name`, `status_preparation` (Preparando/Realizado/Cancelado), `profile_id`, `apply_parametrization`/`load_demo_data` (Opciones Avanzadas: override por preparación de lo configurado en el perfil), `addons_ids`, `executed`+`datetime_executed`, `ignore_preparation`+`datetime_ignore`, `datetime_successful_preparation` (computado: se estampa cuando **todos** los addons de la lista están instalados), `error_log`+`datetime_error`, `current_step` (progreso de `start_demo()` en curso: `addons`/`parametrization`/`data`, leído por polling desde el modal). |

### 3. Métodos clave (`entorno.preparation`)

- **`start_demo()`** — Estampa `datetime_executed` e ingresa a un único flujo transaccional:
  1. Instalación en lote de los addons pendientes con `button_immediate_install()` (maneja el reseteo de cursor/registry que provoca la instalación, re-navegando el registro después). **No respalda la base antes**: es responsabilidad de infraestructura (backups del entorno), no de este flujo — `button_immediate_install()` no es reversible con un rollback, así que una instalación fallida puede dejar módulos a medio instalar (ver FAQ).
  2. Si `apply_parametrization` y el perfil tiene `automatic_parameterization` + `config_json`: `_apply_fast_config_template()`.
  3. Si `load_demo_data` y el perfil tiene `demo_data` + `data_demo_ids`: `_load_demo_data()`.

  Marca `executed = True` al finalizar todo el flujo. **El orden es fijo (addons → parametrización → data)**: si un campo de la plantilla de Fast Config referencia un registro (ej. una moneda) que un dataset del MISMO perfil activaría o crearía, la parametrización va a fallar en encontrarlo — corre ANTES que la carga de datos, no después. Esa dependencia tiene que estar resuelta de antemano (ya activa en la instancia, o traída por uno de los addons del perfil).
- **`_apply_fast_config_template()`** — Decodifica el `config_json` del perfil y llama a `FastConfigController()._import_template(...)` (de `eu_fast_config`), que aplica la plantilla portable (moneda, diarios, cuentas, impuestos, ajustes nativos, etc.) resolviendo referencias por código/nombre.
- **`_load_demo_data()`** — Recorre `profile_id.data_demo_ids` (solo los `active`, en orden de `sequence`). Antes de cada dataset chequea `required_module_ids`: si falta alguno por instalar, corta con un `UserError` claro en vez de fallar más adelante con un `ValueError` críptico de "Invalid field name". Si pasa el chequeo, decodifica el CSV y llama a `self.env[dataset.res_model].load(header, data)`. Se detiene en el primer dataset que falle; si el CSV incluye columna `id` (external id), reintentar `start_demo()` actualiza en vez de duplicar.
- **`_set_current_step(step)`** — Marca `current_step` (`addons`/`parametrization`/`data`) y hace `self.env.cr.commit()` de inmediato, justo antes de cada sub-paso de `start_demo()`. Es lo que le permite al modal mostrar progreso real en vez de un spinner genérico: `start_demo()` es una sola petición HTTP larga que no puede "avisar" su propio progreso a mitad de camino, así que lo persiste y el modal lo lee por polling desde una petición HTTP aparte mientras la primera sigue corriendo.
- **`ignore_demo()`** — Marca `ignore_preparation = True` con su fecha.
- **`cancel_demo()`** — Pasa el estado a Cancelado.
- **`action_reset_demo()`** — Vuelve la preparación a "Preparando" para poder ejecutarla de nuevo (no desinstala addons ni deshace parametrización/data ya aplicados).
- **`_log_preparation_error(error)`** — Si algún paso falla, documenta el mensaje + traceback completo en `error_log` usando un **cursor independiente** (la transacción original queda abortada por el fallo), y re-lanza la excepción a la interfaz. El form muestra el error en un panel de alerta.
- **`_onchange_profile_id`** — Al elegir perfil en el form backend, carga sus aplicaciones (más los `required_module_ids` de sus datasets activos) sin duplicar las existentes, y precarga `apply_parametrization`/`load_demo_data` según los flags del perfil. El modal (OWL) hace lo mismo del lado del cliente en `selectProfile()`.

### 3.1 Métodos clave (`data.entorno`)

- **`action_validate_dataset()`** — Botón "Validar" en la lista de datasets del perfil. Corre el mismo `Model.load()` que usa `_load_demo_data()`, pero dentro de un `savepoint()` propio que **siempre** revierte (haya ido bien o mal): permite detectar columnas que no existen en el modelo destino (típicamente porque dependen de un módulo que no está instalado, ver `required_module_ids`) sin tocar la base ni tener que correr `start_demo()` en serio para descubrirlo.

### 4. Modal de preparación (OWL, `main_components`)

Componente global visible en cualquier pantalla de Odoo (`static/src/components/demo_preparation_modal/`):

- **Aparece solo si** existe una `entorno.preparation` con `ignore_preparation = False` y `executed = False`, y el usuario es administrador (`user.isSystem`).
- **Carga diferida (performance):** al hacer F5 solo se ejecuta una consulta ligera en `onMounted` (no bloquea el render del webclient). El catálogo completo de addons y perfiles se carga únicamente al abrir el modal, con pantalla de carga "Verificando y *preparando* las Aplicaciones".
- **Sección Industrias** (colapsable, colapsada por defecto): cards de perfiles con imagen (`image_128` → icono de `addon_image` → ícono genérico), contador de aplicaciones y descripción desplegable. Selección **única**: elegir una industria agrega sus apps a la selección y precarga sus Opciones Avanzadas; deseleccionarla o cambiar de industria las retira automáticamente (respetando las agregadas a mano). Buscador por nombre y paginación (10–100 por página).
- **Sección Opciones Avanzadas** (colapsable, colapsada por defecto, título con el detalle SVG `red_highlight_bold_05.svg`): mientras no haya industria seleccionada, muestra un aviso; con industria seleccionada, dos checkboxes — **Aplicar Parametrización Automática** y **Cargar Data de Prueba** — precargados según el perfil, editables solo para esta preparación (no modifican el perfil), y deshabilitados si el perfil no tiene esa pieza configurada.
- **Sección Aplicaciones** (colapsable, colapsada por defecto): todas las apps de la instancia agrupadas por categoría, con badge de "ya instalada", buscador por nombre / nombre técnico / categoría (insensible a acentos) y paginación.
- **Restauración de estado al abrir:** si la `entorno.preparation` ya tenía `profile_id`/`apply_parametrization`/`load_demo_data` seteados por otra vía (form backend, script), `_loadExistingSelection()` los restaura al abrir el modal (además de los addons ya seleccionados) — sin esto, "Iniciar Preparación" los pisaba con los defaults del estado (false/vacío) y `start_demo()` corría sin error pero sin parametrizar ni cargar data (ver FAQ).
- **Panel de selección:** lista con íconos y botón X para quitar, contador, botón **Iniciar Preparación** (guarda selección + perfil + Opciones Avanzadas y llama a `start_demo`, luego recarga la página) y botón secundario **Ignorar Preparación** con `ConfirmationDialog` de Odoo (se muestra por encima del modal). Mientras `start_demo()` corre, el botón muestra el **paso actual** (Respaldando la base de datos… / Instalando aplicaciones… / Aplicando configuración… / Cargando datos de prueba…) en vez de un spinner genérico: el JS hace polling a `current_step` cada 900ms en paralelo a la llamada RPC principal (`_pollCurrentStep`).
- **Minimizado:** los botones − y × minimizan el modal a un FAB lateral arrastrable (pointer capture, umbral anti-click de 4px). Click en el FAB reabre y re-verifica los datos.
- **Estética:** fuente **Caveat** alojada localmente (`static/fonts/`), resaltados SVG tipo marcador (`static/img/`: verde para "Aplicaciones", rojo para "Industria", rojo bold para "Avanzadas", amarillo para "preparando"), paleta ciruela de Odoo (#714b67), fondo `#f4f5f7`.

### 5. Menús (ícono Fast Config → Preparación de Entorno)

- **Preparación de Entorno**
  - *Preparación* — list/form de `entorno.preparation` (Opciones Avanzadas, botones Ejecutar/Ignorar/Cancelar/Resetear, panel de error).
  - *Perfiles de Entorno* — list/form de `profile.entorno` (imagen, descripción, addons en lista editable, pestaña de Data de Prueba con los datasets, configuración de Fast Config).

### 6. Seguridad

- Acceso CRUD a los cuatro modelos (`profile.entorno`, `module.entorno`, `data.entorno`, `entorno.preparation`) **solo para `base.group_system`** (administradores). El modal se autoprotege con `user.isSystem` para no generar errores de acceso a usuarios normales.

### 7. Dependencia: `eu_fast_config`

La parametrización automática reutiliza el asistente `eu_fast_config` (no reinventa la lógica de configuración): `profile.entorno.config_json` es una plantilla exportada desde `/eu_fast_config/export`, y `_apply_fast_config_template()` llama directamente a `FastConfigController()._import_template(...)`. Cualquier campo/paso que `eu_fast_config` sepa configurar (compañía, plan de cuentas, ajustes nativos de Productos/Inventario/Contabilidad/Compras/Ventas, retenciones, secuencias, etc.) queda disponible para los perfiles de entorno sin trabajo adicional.

### 8. Exportar / Importar Perfiles

Un perfil completo (apps + plantilla de Fast Config + datasets con sus CSV) se puede llevar como un solo archivo portable a cualquier otra instancia con `eu_fast_config` instalado:

- **Exportar Perfil** — botón en el header del formulario de `profile.entorno` (`action_export_profile`). Descarga un `.zip` (`perfil_demo_<nombre>.zip`) armado al vuelo por un controller HTTP (`/eu_fast_config/export_profile/<id>`, mismo patrón que `/eu_fast_config/export`: nada se persiste como `ir.attachment`). Adentro: `manifest.json` (metadata del perfil y de cada dataset), `image.png` (si el perfil tiene imagen propia), `config.json` (la plantilla de Fast Config, si tiene) y `datasets/<n>_<archivo>.csv` por cada dataset. Los módulos (del perfil y los `required_module_ids` de cada dataset) viajan por **nombre técnico**, nunca por id — el id de un `ir.module.module` no significa nada en otra base.
- **Importar Perfil Demo** — menú propio (Ajustes → Técnico → Automatización → Preparación Demo → Importar Perfil Demo), abre un wizard de un solo campo: subís el `.zip` y apretás Importar. Reconstruye el perfil completo — apps, plantilla, datasets con sus CSV — y **redirige directo al perfil recién creado**. Cualquier módulo (del perfil o requerido por un dataset) o modelo destino (`res_model` de un dataset) que no exista en esta instancia se omite sin frenar el resto del import, y queda avisado en el **chatter** del perfil (por eso `profile.entorno` hereda `mail.thread`) — nunca falla en silencio ni revienta el import completo por una pieza faltante.

### 9. Notas técnicas (Odoo 19)

- CSV de accesos: `security/ir.model.access.csv` (con puntos — el nombre del archivo define el modelo destino).
- Constraints SQL con la sintaxis nueva `models.Constraint` (reemplaza `_sql_constraints`).
- `post_init_hook(env)` recibe `env` directamente.
- SCSS validado con **libsass** (el compilador de Odoo): sin `@import url()` externos ni `min()/max()` de unidades mixtas.
- `data.entorno.data_file` usa `attachment=True` para no inflar la tabla con los CSV de cada dataset.
- **`status_preparation` no pasa a "Realizado" solo.** Ningún método transiciona ese campo a `done` tras un `start_demo()` exitoso — se queda en `preparing` aunque `executed=True` y `datetime_successful_preparation` ya estén estampados. El badge verde (`decoration-success`) de la lista de preparaciones nunca se activa automáticamente; hoy es un estado que hay que setear a mano si se lo quiere reflejar. Pendiente decidir si es intencional (alguien lo marca al revisar la demo) o si conviene que `start_demo()` lo setee solo al terminar.

---

## Cómo armar un dataset de Data de Prueba

`data.entorno` no reinventa nada: es un contenedor (nombre + modelo destino + archivo CSV) alrededor del motor **nativo** de carga de datos de Odoo — el mismo `Model.load()` que usa el asistente de importación cuando arrastrás un Excel a una lista, y el mismo que procesan los CSV de `data/` en cualquier manifest. Si entendés ese mecanismo, ya sabés armar un dataset.

### 1. El formato del CSV

```csv
id,name,default_code,type,list_price
demo_transporte.flete_nacional,Servicio de Flete Nacional,TRN-001,service,350.00
```

| Columna | Qué es | Regla |
|---|---|---|
| `id` | **External ID** (no el id numérico de la tabla) | Clave de idempotencia — ver punto 2. Formato libre: `modulo.slug`, ej. `demo_transporte.flete_nacional`. |
| `name`, `default_code`, `type`, ... | Nombres **técnicos** de campos del modelo destino | Tal cual están en `_fields` del modelo, no la etiqueta que ves en la UI. |
| `campo_relacional/id` | Referencia a otro registro por external ID | Ver punto 3. |

Tipos, sin sorpresas: booleanos como `True`/`False` o `1`/`0`; decimales con punto (`350.00`); `Selection` con el valor interno (`service`, no "Servicio"); encoding siempre UTF-8 (el código maneja el BOM con `utf-8-sig`, así que un CSV exportado de Excel con BOM no rompe).

### 2. La columna `id` — por qué es la pieza clave (idempotencia)

Sin columna `id`, cada `start_demo()` crea registros NUEVOS — duplicás todo en cada reintento. Con columna `id`: la primera carga crea el registro y lo registra en `ir.model.data` con ese external ID; las cargas siguientes con el mismo `id` **actualizan** el mismo registro en vez de duplicar. Por eso `action_reset_demo()` es seguro: podés recorrer `start_demo()` las veces que haga falta mientras el `id` no cambie. Usá un prefijo que identifique el dataset (`demo_transporte.*`, `demo_agro.*`) para que nunca choque con external IDs de otro módulo.

### 3. Referencias entre registros — el sufijo `/id`

Cuando un campo apunta a otro modelo (many2one, many2many), agregás `/id` al nombre de columna y el valor es el external ID del registro referenciado:

```csv
id,name,is_company,country_id/id
demo_transporte.cliente_valle,Agroindustrial El Valle C.A.,True,base.ve
```

`country_id/id` con valor `base.ve` apunta al external ID nativo del país Venezuela (todos los `res.country` de Odoo lo tienen). Funciona igual entre TUS propios datasets: si un dataset de `sale.order` necesita un cliente cargado en otro dataset de `res.partner`, referencialo con `partner_id/id` apuntando al `id` que le pusiste ahí — siempre que ese dataset ya se haya cargado antes (punto 4). Para líneas one2many dentro del mismo CSV (ej. `sale.order.line` de una orden), se usa `order_line/product_id/id` — filas con el mismo `id` principal se agrupan como líneas del mismo registro padre.

### 4. `sequence` — el orden importa cuando hay referencias

`data.entorno.sequence` define el orden de carga dentro de un perfil. Regla simple: **lo que se referencia va primero**.

```
10 → Clientes y Proveedores (res.partner)
20 → Productos (product.template)
30 → Órdenes de venta (sale.order)  ← referencia partner_id/id y los productos de arriba
```

Invertir el orden rompe: la orden de venta fallaría porque el partner todavía no existe cuando se procesa ese dataset.

### 5. Cómo saber qué campos existen (esto rompió el CSV de ejemplo una vez)

Un campo puede depender de un módulo que no está instalado en la instancia — `Model.load()` no adivina, explota con `Invalid field name` si no está en `_fields` del modelo en ese momento (pasó de verdad con `is_storable` en `product.template`, que solo existe con `stock` instalado). Antes de escribir un CSV, chequeá:

```bash
docker exec <container_web> python3 /usr/bin/odoo shell -c /etc/odoo/odoo.conf -d <db> --no-http
>>> 'is_storable' in env['product.template']._fields
```

o desde la UI, en developer mode: Ajustes → Técnico → Base de Datos → Campos, filtrando por modelo. Si el campo lo aporta un módulo que no es parte del núcleo de la instancia, **declaralo en `required_module_ids`** del dataset (ver FAQ más abajo): así `_load_demo_data()` corta con un mensaje claro si falta, y el formulario/modal ya sugieren instalarlo apenas elegís el perfil.

### 6. Paso a paso

1. Armá el CSV con las reglas de arriba (usá cualquiera de los dos `data_samples/` como plantilla).
2. Ajustes → Técnico → Preparación Demo → Perfiles de Entorno → abrí (o creá) el perfil → pestaña "Data de Prueba".
3. Nueva línea: `name` descriptivo, `sequence`, `res_model` (nombre técnico del modelo destino), subí el CSV en `data_file`, marcá `required_module_ids` si aplica.
4. **Antes de guardar en serio, apretá "Validar"** (`action_validate_dataset`) — corre el mismo `load()` en un savepoint que siempre revierte. Si tira `danger`, arreglá el CSV y volvé a validar hasta que dé `success`. Te ahorra descubrir el error a mitad de un `start_demo()` real.
5. Marcá `demo_data = True` en el perfil para que el flujo de preparación lo tenga en cuenta.

### Datasets de ejemplo (`data_samples/`)

Archivos CSV de referencia para armar un perfil "Transporte", pensados para subirse a mano como líneas de `data.entorno` en el perfil (no se cargan automáticamente vía manifest — son plantillas de partida):

- `transporte_productos.csv` → modelo `product.template` (fletes, seguros, repuestos y consumibles de flota). Secuencia 20, sin dependencias entre sí.
- `transporte_clientes_proveedores.csv` → modelo `res.partner` (clientes y proveedores tipo del sector transporte). Secuencia 10, sin dependencias.

## Posibles mejoras futuras

- Sumar más datasets de ejemplo por industria en `data_samples/` (inventario inicial, listas de precio, órdenes de venta/compra, facturas en distintos estados).

## FAQ

### "Iniciar Preparación" se queda cargando para siempre y al final el webclient tira "¡Vaya!"

**Causa:** `start_demo()` instala los addons pendientes con `button_immediate_install()` en un solo request HTTP, que Odoo corta por default a los 120s (`limit_time_real`). Un perfil con pocas apps sueltas (ej. una sola app liviana) no tiene problema, pero un perfil con muchas aplicaciones —o una sola app con muchas dependencias transitivas, como Enterprise + contabilidad + una localización fiscal completa— puede arrastrar 80+ módulos y superar ese límite. El worker HTTP es matado a mitad de camino: la instalación puede terminar de todos modos en la base, pero la respuesta nunca vuelve al navegador, y en el peor caso algunos módulos quedan en estado `to install`/`to upgrade` colgado, lo que rompe el resto del webclient hasta que se recompongan.

Se confirmó en pruebas: instalar solo `eu_fast_config` (que arrastra 81 módulos por las dependencias de Enterprise/contabilidad/localización venezolana ya instaladas en la base) tardó ~100s y en un caso llegó a cortarse justo al final.

**Solución:** subir `limit_time_cpu` / `limit_time_real` en el `odoo.conf` real de la instancia (no alcanza con dejarlo solo en un archivo plantilla si el deployment reescribe su propio conf — revisá cuál archivo está montado en `/etc/odoo/odoo.conf`):

```ini
limit_time_cpu = 1200
limit_time_real = 1800
```

y reiniciar el servicio de Odoo para que tome el cambio. Es la misma recomendación que aplica a cualquier instalación masiva de módulos en Odoo (no es específico de este addon), pero `eu_fast_config` la dispara con más frecuencia porque su propósito es justamente instalar muchos addons de golpe.

**Si la base ya quedó con módulos a medio instalar** (se ve en los logs como `odoo.addons.base.models.ir_cron: Skipping database <db> because of modules to install/upgrade/remove.`), un simple restart del contenedor NO alcanza — Odoo solo termina de aplicar módulos pendientes si se lo pedís explícitamente:

```bash
odoo -c /etc/odoo/odoo.conf -d <nombre_db> -u all --stop-after-init --no-http
```

Confirmá que el log termine con `Modules loaded.` sin errores antes de seguir usando la base. Este flujo no genera un respaldo propio antes de instalar (es responsabilidad de infraestructura): si algo sale mal, la restauración depende del mecanismo de backup que tenga configurado ese entorno.

### `start_demo()` falla con `ValueError: Invalid field name '<algún_campo>'` al cargar la data de prueba

**Causa:** el CSV de un dataset (`data.entorno`) usa un campo que **no existe en el modelo destino** porque lo aporta un módulo que todavía no está instalado. Ejemplo real detectado en pruebas: `data_samples/transporte_productos.csv` traía la columna `is_storable` en `product.template`, pero ese campo lo aporta el módulo `stock` (Inventario) — si el perfil no lo incluye entre sus aplicaciones, `_load_demo_data()` explota con `Invalid field name 'is_storable'` y, como todos los datasets de una misma corrida comparten transacción, el rollback también deshace los datasets anteriores que sí habían cargado bien en esa ejecución.

**Solución (dos capas, ambas ya implementadas):**

1. **Declará las dependencias del dataset** en `required_module_ids` (campo m2m en `data.entorno`, columna "Módulos Requeridos" en la lista de datasets del perfil). `_load_demo_data()` chequea esto ANTES de tocar el CSV: si falta algún módulo, corta con un mensaje claro (`El dataset "X" ... requiere el/los módulo(s) Y, que no está(n) instalado(s)`) en vez de un `ValueError` críptico. Además, `_onchange_profile_id` (form backend) y `selectProfile()` (modal) suman automáticamente esos módulos a la selección de apps a instalar cuando elegís el perfil, para que ni siquiera llegues a ese error.
2. **Usá el botón "Validar"** (`action_validate_dataset`) en la fila del dataset antes de confiar en él: corre el mismo `Model.load()` dentro de un savepoint que siempre revierte, mostrando los errores de campo (o un "OK, N registros se cargarían") sin escribir nada en la base. Es la forma rápida de descubrir un campo inválido en cualquier modelo, sin tener que ejecutar `start_demo()` en serio.

### `start_demo()` termina con `executed=True` y sin `error_log`, pero la parametrización y la data de prueba no se aplicaron

**Causa (corregida):** si la `entorno.preparation` ya tenía `profile_id`, `apply_parametrization` y `load_demo_data` seteados por fuera del modal (form backend, script, otro canal), `_loadExistingSelection()` solo restauraba los addons ya seleccionados al abrir el modal — nunca esos tres campos. Al apretar "Iniciar Preparación" sin volver a clickear la industria, el `write()` los pisaba con los defaults del estado del componente (`false`/vacío). `start_demo()` corría igual, pero como `self.apply_parametrization` y `self.load_demo_data` llegaban en `false`, ninguno de los dos pasos condicionales se ejecutaba — sin ningún error visible, porque técnicamente no se intentó nada.

Detectado probando un perfil real ("Requerimientos Fiscales Venezuela") armado por script: el módulo se instaló bien, pero ni la parametrización de `l10n_ve_fiscal_requirements` (RIF/contribuyente/moneda de retenciones vía `eu_fast_config`) ni los partners de ejemplo con RIF se cargaron.

**Solución:** `_loadExistingSelection()` ahora también lee y restaura `profile_id`, `apply_parametrization` y `load_demo_data` del registro. Si armás o editás una preparación por fuera del modal, abrilo al menos una vez y confirmá en el panel de "Opciones Avanzadas" que los checkboxes reflejan lo esperado antes de "Iniciar Preparación".

### `_apply_fast_config_template()` falla con `RuntimeError: object is not bound`

**Causa:** este método llama directamente a `FastConfigController()._import_template(...)`, que depende de `odoo.http.request` (el contexto de la petición HTTP activa) para resolver la compañía y hacer `savepoint()`. Esto funciona sin problema cuando `start_demo()` corre como consecuencia de un click real en el navegador (botón del formulario o modal), pero **falla si se llama `start_demo()` fuera de un contexto HTTP** — por ejemplo desde `odoo shell`, un test, o un `ir.cron`. No es un bug del dataset ni de la parametrización en sí: es una limitación de diseño de `_apply_fast_config_template()`, heredada de que reutiliza el controller de `eu_fast_config` tal cual en vez de una lógica de servicio independiente de `request`.

**Solución:** ejecutá `start_demo()` siempre desde el modal o el botón "Ejecutar Preparación" del formulario (un click real de usuario), nunca desde shell/cron/tests. Si en algún momento hace falta dispararlo por código sin un usuario real de por medio, `eu_fast_config` necesitaría extraer `_import_template` a un método que no dependa de `request` (fuera del alcance actual de este addon).

Si armás datasets nuevos para otras industrias, corré "Validar" con el perfil recién instalado (los módulos que aporta ya activos) para confirmar que el CSV es compatible antes de dejarlo como parte del perfil.
