# Manual de usuario — notas de trabajo

El manual está escrito en [MANUAL.md](MANUAL.md), con 26 capturas en `img/`.
Este archivo solo recoge lo que quedó fuera y cómo repetir las capturas.

## Capturas que faltan

Las tres no se pudieron tomar en la base `nueva` y el manual las explica por
texto. Si alguna vez se quieren añadir:

| Captura | Por qué no salió | Cómo conseguirla |
|---|---|---|
| Paso de un **módulo no instalado** (con el botón de instalarlo) | En `nueva` están los 512 módulos instalados: no hay ninguno | Instalar `eu_fast_config` en la base `manual_ve` (127 módulos) y abrir el asistente ahí, desactivando el filtro que oculta los no instalados |
| **Selector de compañía** (multiempresa) | `nueva` tiene una sola compañía | Crear una segunda compañía en una base de pruebas |
| **Modo consulta** (chip y campos bloqueados) | No hay usuario con el grupo de solo lectura | Crear un usuario con *Configuración Rápida → Consultor (solo lectura)* y entrar con él |

## Cómo se tomaron las capturas

Scripts Selenium (`shots_efc.py` … `shots_efc6.py`) en el scratchpad de la sesión
`42f99131-fdd5-4aff-88da-4ccf2261276c`. Patrón: Chrome headless,
`--force-device-scale-factor=2`, viewport 1440×900 y
`Emulation.setDeviceMetricsOverride` ajustando el alto al `scrollHeight` real
para capturar la página entera de una vez. Las capturas de detalle
(diagnóstico, pie, bloque de ayuda) son `element.screenshot()`.

Dos trampas encontradas:

- **`localhost` puede resolver a `::1` y Odoo solo escucha en IPv4** → usar
  `http://127.0.0.1:8069`.
- El **webclient del backend tarda ~30 s la primera vez** mientras compila los
  assets; con esperas de 6 s salían capturas en blanco (no es el bug conocido de
  la base).

## Versión PDF

`Manual_eu_fast_config.pdf` (39 páginas A4, ~7,8 MB) se genera desde el propio
Markdown:

```bash
python docs/build_pdf.py
```

`build_pdf.py` convierte MANUAL.md a un HTML con estilos de impresión (paleta del
propio asistente, tabla con cabecera repetida, figuras que no se parten) y lo
imprime con **Chrome headless** vía `Page.printToPDF` — no con wkhtmltopdf, cuyo
motor es demasiado viejo para este CSS. Después añade los **47 marcadores** de
navegación y los metadatos con pymupdf.

Hay que regenerarlo cada vez que cambie MANUAL.md o una captura. Dependencias:
`markdown` y `selenium` (instalados con `pip install --user`) y `pymupdf`, que ya
viene con Odoo.

Detalle a tener en cuenta si se toca el script: los marcadores **no** se
localizan buscando el texto del título, porque la página del Índice los contiene
todos y el primer acierto sería siempre esa. Se localizan por tamaño de letra
(h2 = 18 pt, h3 = 13 pt, cuerpo = 10,5 pt) recorriendo las páginas en orden.

## Efectos colaterales en la base `nueva`

Al preparar las capturas se escribió en la base (es base de pruebas, pero queda
constancia):

- `res_company.eu_fast_config_profile` quedó en **`comercial`** (antes vacío).
- Se guardó el paso **Precisión Decimal** sin cambiar ningún dígito (los valores
  siguen como estaban); dejó una fila en `eu_fast_config_progress` y otra en
  `eu_fast_config_log`.
