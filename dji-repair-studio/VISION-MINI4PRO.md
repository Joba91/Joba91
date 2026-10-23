# Visión Mini 4 Pro · DJI REPAIR Studio 1.2.0

Estado: diagnóstico sin conexión implementado. El módulo de calibración completo
sigue pendiente; lectura USB, descarga e instalación no están habilitadas.

## Uso

1. Abre la pestaña **Visión Mini 4 Pro**. El lateral se desplaza a sus acciones.
2. **Importar carpeta visión** o **Importar ZIP visión** inventaría el paquete en
   solo lectura. No se extraen ZIP, ejecutan programas, cargan DLL ni instalan datos.
3. Revisa **Inventario local** y **Resultados y evidencia**. Se calculan MD5 y
   SHA-256. Se distinguen estados confirmado, desconocido y error.
4. **Analizar captura visión** lee un registro o una captura sin conexión. Formatos:
   `binary` (bytes crudos), `hexlog` (texto HEX) y `auto`. `.bin/.raw/.dump` se
   consideran binarios en auto. Los registros admiten UTF-8/UTF-16 y volcados HEX
   con marcas TX/RX o direcciones de línea. Para otros formatos, falta evidencia.
5. **Identificación visión** informa por qué la consulta activa no está disponible.
6. Opcional: escribe un servidor autorizado `https://host:puerto` y pulsa
   **Comprobar servidor visión**. No hay dirección ni comprobación automática.
   El sondeo verifica solo TCP/TLS y su certificado, sin HTTP, autenticación ni
   descarga. No acepta credenciales, tokens ni cookies en la URL. Los errores no
   demuestran que el servidor esté apagado. Se limita a 3/5/10 segundos, incluyendo
   DNS e inicio del proceso. El proveedor no implementa todavía la API de descarga.
7. **Guardar informe** exporta los últimos resultados de cada categoría en JSON.
   El inventario visual muestra hasta 500 archivos y los detalles hasta 200;
   el informe conserva todo el inventario y hasta 200 tramas/incidencias de muestra,
   junto con los contadores totales. Solo se conserva el último paquete/captura/servidor.

## Integridad y compatibilidad

Se reconocen manifiestos de texto GNU `MD5SUMS`/`.md5` y BSD `MD5 (archivo) = hash`.
Las rutas son relativas a la carpeta del manifiesto. Las entradas duplicadas,
rutas no admitidas, archivos ausentes, MD5 distintos, lectura fallida o líneas no
reconocidas producen error. Sin manifiesto o con cobertura parcial, el estado es
desconocido. Otros formatos del paquete DJI requieren inspeccionar los archivos
reales y añadir su lector; no se presupone que utilicen uno de estos formatos.

**Una coincidencia MD5 solo acredita la coincidencia con ese manifiesto local.**
No verifica autoría, autenticidad, modelo, firmware, sensores ni números de serie.
SHA-256 registra una huella local, sin aportar autenticidad por sí solo.
Los archivos `.bin/.dat/.cal/.cali` se enumeran como candidatos sin compatibilidad
confirmada; no son seleccionables para instalación. No se interpretan números de
serie a partir de nombres ni se promete generar calibración óptica nueva.

Límites: 5000 archivos, 256 MiB por archivo, 2 GiB por paquete, 4 MiB por manifiesto;
capturas hasta 32 MiB y 100000 tramas. Se rechazan ZIP cifrados, enlaces, nombres
ambiguos para Windows y relaciones de compresión excesivas. La cancelación detiene
la lectura local; no actúa sobre el dron.

## Arquitectura

- `vision_packages.py`: inventario, huellas y verificación MD5, sin red ni interfaz.
- `vision_protocol.py`: tramas y registros; reutiliza el CRC de `studio_protocol.py`.
- `vision_interfaces.py`: contratos de transporte pasivo, identificación y proveedor
  de calibraciones. Proveedor local y estado explícito de identificación no disponible.
- `vision_services.py`: proveedor de servicios configurable y sondeo en un proceso
  separado con tiempo máximo. TLS conserva la validación de certificados.
- `vision_view.py`: controles Tk; no abre archivos, red ni USB por su cuenta.
- `studio_app.py`: acciones laterales, trabajo en segundo plano, progreso e informes.

No hay puente a DLL propietarias. Ninguna DLL del paquete se carga o redistribuye.
La implementación nueva no tiene instalador de calibraciones ni escritura USB.
Al seleccionar **Mini 4 Pro**, también se bloquean las acciones activas genéricas
de la aplicación, para que no se reutilice por accidente un protocolo de otro modelo.
Los módulos anteriores para otros modelos conservan su comportamiento y restricciones.

## Evidencia y bloqueos reales

El informe y paquete de las rutas de Windows indicadas no están disponibles en
este entorno. Es necesario adjuntarlos. Sus afirmaciones se mantienen como pendientes,
no como resultados verificados. En particular:

- No se han contado ni contrastado las supuestas 150 respuestas ACK del Mini 4 Pro.
- Longitud `LE16 & 0x03FF`, CRC8 `0x8C/0x77` y CRC16 `0x8408/0x3692`, sin XOR final,
  coinciden con el código previo y con una trama real aportada antes en este chat:
  `55 0e 04 66 04 0a 8e ad 80 04 08 01 fb 95`. Esa trama es de otro contexto de
  gimbal; NO demuestra compatibilidad ni comandos de visión del Mini 4 Pro.
- Las pruebas adicionales usan tramas y paquetes sintéticos, identificados como tales.
- VID `2CA3`, PID `0020` y `MI_04` proceden del texto recibido. Los endpoints y su
  correspondencia con firmware siguen sin verificar; no se implementa transporte USB.
- La arquitectura x86, las firmas C++, dependencias internas y las dos variantes de
  Device_Manager.dll deben comprobarse contra los binarios reales. No se deducen
  firmas por nombres ni se cargan DLL. Si se necesitara un componente x86 autorizado,
  haría falta un auxiliar de 32 bits y completar antes su análisis y condiciones de uso.
- Las dos IP privadas históricas y GCAC son referencias del texto. No se han consultado, no se configuran como valores predeterminados y no
  se da por válido ni actual el resultado anterior de disponibilidad.

Para habilitar **lectura USB**: capturas con peticiones y respuestas completas,
descriptores/endpoints reales, firmware, identificadores y efectos de comandos
verificados. Para **descarga**: API/servicio vigentes, acceso autorizado, autenticación
configurada sin reutilizar secretos del paquete y correspondencia demostrada entre
identificadores de módulos/sensores y datos. Para una futura **escritura**: además,
protocolo validado, correspondencia por unidad, secuencia transaccional, recuperación
ante fallos y pruebas físicas. Ninguna de estas etapas se declara completada.

## Verificación

Consulta `validacion-1.2.0.json` y `test-results-1.2.0.txt` para los resultados de
esta entrega. Las pruebas cubren tramas válidas, CRC dañados, truncadas, concatenadas,
longitudes incorrectas, recuperación, manifiestos, errores de importación, cancelación,
límites, bloqueo de USB, sondeo solo solicitado y exportación desde la interfaz.
No hay validación con paquete Mini 4 Pro real, servidores DJI ni hardware físico.
