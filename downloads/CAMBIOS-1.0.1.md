# Correccion 1.0.1

Corrige el mensaje de Windows «The ordinal 380 could not be located» al iniciar.
El cargador de PyInstaller importaba COMCTL32 ordinal 380 sin el recurso RT_MANIFEST
24/1/0 que selecciona Common Controls v6. Ahora se incorpora el manifiesto estandar
de PyInstaller y se recalcula el checksum PE.

No se modificaron bytecode de aplicacion, protocolos ni rutinas de calibracion.
El payload PyInstaller conserva exactamente el mismo SHA-256. No necesitas
copiar bibliotecas ni modificar Windows. Descarga el paquete 1.0.1, extraelo
en una carpeta nueva y ejecuta el archivo cuyo nombre termina en 1.0.1.

Verificacion: 7 pruebas nuevas, con inspeccion independiente mediante pefile.
El arranque en Windows nativo queda pendiente de comprobar.
