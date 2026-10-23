# Investigación de los registros recibidos · DJI REPAIR Studio 1.2.1

Se analizó sin ejecutar programas ni cargar DLL el ZIP de configuración/registros
aportado por el usuario. Los archivos originales y números de serie no se incluyen
en esta publicación. Tampoco se contactaron servidores DJI ni un dron.

## Resultados verificables

- 89 registros y dos configuraciones cifradas; no hay DLL, descriptores USB ni
  manifiestos/archivos de calibración en este ZIP reducido.
- 367 registros CMD y 367 registros ACK: 734 tramas completas. Todas coinciden con
  la longitud declarada y los CRC de cabecera/trama del informe.
- Las 367 entradas ACK contienen **150 tramas diferentes**. Se confirma ese recuento
  sobre estos registros; una etiqueta ACK no acredita éxito de una operación.
- 175 asociaciones CMD/ACK tienen direcciones inversas, conjunto/comando, secuencia
  y bit de respuesta concordantes. Su resultado de aplicación sigue sin interpretar.
- Cuatro entradas ACK son idénticas al CMD anterior: ecos, no respuestas confirmadas.
- 188 asociaciones registradas no cumplen la correlación de cabeceras usada arriba.
  No se ha relajado el cliente USB para aceptarlas como respuestas.
- 81 registros no son UTF-8 y se leyeron con GB18030; ocho son UTF-8/ASCII. El lector anterior trataba
  todo como UTF-8. El nuevo conserva la codificación identificada.

## Sensores y contexto histórico

Hay 188 peticiones de la familia `24/26`, asociadas en los registros al flujo
`GetPerceptionSN`. Cuatro payloads de petición difieren en su último selector:
`04`, `08`, `40`, `80`. Se observan etiquetas `frontleft`, `frontright`, `backleft`
y `backright`, respectivamente. Esto describe la asociación histórica observada;
no demuestra que sean funciones de solo lectura en el firmware del usuario.

Se encontraron 184 etiquetas de serie alfanuméricas de 14 caracteres (46 por
posición). El lector puede mostrar esas etiquetas con su línea de procedencia,
identificadas expresamente como históricas. No identifica con ellas el equipo
conectado ni deriva compatibilidad por unidad.

Las 188 tramas etiquetadas ACK de esa familia tienen payload de 20 bytes, flags
`00` y secuencia distinta de la petición. Las etiquetas de serie no aparecen como
ASCII directo en esos payloads. Falta determinar su estructura y decodificación;
no se presenta una conversión de serie inventada.

Los registros abarcan distintas fechas y estaciones e incluyen referencias a
WM162 y al software ET8DY35/WA140. El nombre de la carpeta no confirma que todo el
tráfico corresponda al Mini 4 Pro. También aparecen flujos de modo fábrica,
transferencia y copia de calibraciones. Ninguno de esos flujos se ha reproducido.

## USB y archivos pendientes

Los registros muestran búsquedas con VID `2CA3`, PID `0020` e interfaz `4`, además
de otras interfaces del dispositivo compuesto. **MI_04 es una interfaz, no una
dirección de endpoint.** No hay `bEndpointAddress`, `wMaxPacketSize` ni descriptores
que permitan fijar los endpoints del equipo actual.

Siguiente evidencia útil, de la misma versión del paquete Mini 4 Pro:

- `bin/DJI_Protocol_Comm.dll`: analizar estáticamente apertura bulk, configuración
  de transporte y uso de endpoints, sin cargarla ni ejecutar sus exportaciones.
- `Up and Side Vision Cali Download/dji_test_userlibs.dll`: investigar el manejo
  de las respuestas de sensores y sus dependencias de contexto/modo.
- Descriptores USB del dron actual y su firmware para contrastar cualquier
  conclusión estática. No deben cambiarse controladores para obtenerlos.

Las configuraciones recibidas están cifradas. Se conserva su inventario; no se
reutilizan credenciales, cookies o tokens ni se elude autenticación. El sondeo
manual de servidores de la aplicación no se ejecutó durante esta investigación.

## Cambio implementado y validación

`vision_history.py` reconoce únicamente marcas explícitas de tráfico DJI. Prefiere
la capa CMD/ACK y descarta su copia de la capa `cmd Send` para evitar doble conteo.
Distingue ecos, asociación de registro y correlación de cabeceras, sin inferir éxito.

En el conjunto recibido, el lector anterior contabilizaba 1107 tramas y 66
incidencias al interpretar texto y copias de envíos como tráfico. El lector nuevo
contabiliza las 734 tramas CMD/ACK, con cero incidencias de framing. La ausencia
de errores de framing no es un diagnóstico de salud del dron.

Se agregaron pruebas con datos sintéticos de marcas CMD/ACK, duplicados, ecos,
secuencias discordantes, CRC, registros truncados, GB18030/UTF-16, textos de
autenticación ignorados y etiquetas históricas. Los resultados concretos de
aplicación, empaquetado y ejecución bajo Wine están en `validacion-1.2.1.json`.

La lectura USB, selección/descarga para un equipo e instalación siguen
**deshabilitadas**. No hay validación en Windows nativo ni con hardware real.
