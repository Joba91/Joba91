# DJI REPAIR Studio 1.1.0

- Una sola ventana principal. Se retira la apertura automática del segundo panel.
- Marca visible unificada: **DJI REPAIR Studio**.
- Botones de ejecución en el lateral izquierdo; opciones y registro en pestañas centrales.
- Configuración de conexión compartida y una operación por vez.
- Barra y porcentaje basados en consultas, confirmaciones o hitos recibidos.
  Cuando no hay datos cuantificables se muestra una barra de espera.
- Un error no se convierte en 100 % de calibración. El fin debe ser informado por el equipo.
- Se conserva la corrección del error **ordinal 380** mediante Common Controls v6.

El rediseño conserva los protocolos y restricciones existentes. No añade validación
de calibración para Mavic 4 Pro o Classic ni movimiento manual por ejes.

Validación: 38 pruebas de aplicación/transporte/progreso/interfaz y 8 de empaquetado.
El EXE se prueba bajo Wine 10, sin abrir ni enumerar un dron. No está validado en
Windows nativo ni con hardware DJI real. Detalles dentro del ZIP.
