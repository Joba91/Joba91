# DJI REPAIR Studio 1.3.0

[Descargar Windows 10/11 x64](https://raw.githubusercontent.com/Joba91/Joba91/main/downloads/DJI_Repair_Studio_1.3.0.zip)

Extrae el ZIP en una carpeta nueva y abre **DJI REPAIR Studio 1.3.0.exe**.

## Prueba de identificación de sensores

1. Conecta el Mini 4 Pro encendido en modo normal. Cierra DJI Assistant y otros
   clientes USB del PC; conserva el controlador existente.
2. En **Visión Mini 4 Pro**, escribe **01.00.1100** en Firmware declarado,
   si coincide con la versión de aeronave en DJI Fly.
3. Pulsa **Consultar SN visión (prueba)** y guarda un **nuevo** `.bin`.
4. Espera las cuatro ventanas de consulta y comparte el **ZIP Mini4Pro-SN-....zip**
   creado junto al BIN. Contiene recepción e informe con peticiones y errores.

Esta acción sí envía consultas SN, hasta cuatro, una por selector. Las peticiones
coinciden byte por byte con 188 consultas históricas. No envía comandos de fábrica,
calibración, configuración o firmware. Si falla un envío, no lo repite ni cambia
el modo de la aeronave. La recepción está limitada a 15 segundos después de abrir
USB o 1 MiB; una llamada USB en curso puede terminar después del límite.

**Es una prueba experimental: falta validar la consulta en modo normal con tu firmware.**
Los SN aparecen como **observados**, sin afirmar correlación, identidad o salud
confirmadas. Sin respuesta no significa avería. 100 % indica cuatro ventanas
completadas, no diagnóstico o calibración. Detener conserva el resultado parcial.
Los nombres de posición son etiquetas históricas, no ubicación física verificada.

La recepción pasiva anterior sigue disponible y conserva su funcionamiento sin
peticiones de servicio. Ambas acciones generan ZIP incluso con fallo o cero bytes.
No sobrescriben ni suben archivos. Revisa el informe antes de publicarlo: puede
contener series. Guardar informe permite exportar el JSON manualmente.

205 pruebas de aplicación/interfaz y 9 de empaquetado aprobadas. El EXE arranca
bajo Wine y prueba consultas, tabla y ZIP con cuatro respuestas sintéticas.
No se ha realizado aquí la consulta activa física ni prueba en Windows nativo.
La captura pasiva 1.2.6 recibida del usuario se reanalizó: 6123 bytes y 104 tramas
válidas; no acredita las nuevas consultas SN. No se habilita calibración óptica.

[Uso y arquitectura](../dji-repair-studio/VISION-MINI4PRO.md) ·
[Investigación](../dji-repair-studio/INVESTIGACION-REGISTROS-MINI4PRO.md) ·
[Código](../dji-repair-studio). Fuentes y licencias incluidas, sin DLL oficiales DJI,
credenciales, capturas originales, instaladores o drivers binarios.
Consulta **SHA256SUMS.txt** para verificar la descarga.
