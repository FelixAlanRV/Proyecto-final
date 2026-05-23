# Manual de Instalación y Uso: Bot de Visión por Computadora para Google Dino

Este proyecto es una implementación de un agente autónomo que juega al clásico juego del Dinosaurio de Google (T-Rex Runner) utilizando técnicas clásicas de Visión por Computadora, sin la utilización de Machine Learning o Aprendizaje por Refuerzo.

## 1. Requisitos Previos del Sistema

Antes de comenzar, asegúrate de tener lo siguiente:
- **Sistema Operativo**: Windows 10/11, macOS o Linux.
- **Python**: Versión 3.8 o superior.
- **Navegador Web**: Google Chrome (para abrir el juego en `chrome://dino`).

---

## 2. Instalación de Dependencias

Para que el bot funcione correctamente, es necesario instalar algunas librerías de terceros. Abre tu terminal (Símbolo del sistema o PowerShell) y ejecuta el siguiente comando para instalarlas usando el archivo `requirements.txt`:

```bash
pip install -r requirements.txt
```

Si prefieres instalarlas manualmente, los paquetes requeridos son:

- `opencv-python`: Procesamiento de imágenes (cv2).
- `numpy`: Cálculos matemáticos y manipulación de matrices.
- `mss`: Captura de pantalla a altísima velocidad.
- `keyboard`: Automatización y simulación de teclas de hardware.
- `requests`: Peticiones HTTP para el OCR basado en Deep Learning en la nube.

---

## 3. Guía de Uso del Bot

### Paso 3.1: Preparar el juego
1. Abre Google Chrome.
2. Desconéctate de internet o simplemente escribe en la barra de direcciones: `chrome://dino`
3. Lo ideal es usar pantalla dividida: coloca la ventana de Chrome en una mitad de la pantalla y tu terminal (para ejecutar el código) en la otra mitad.

### Paso 3.2: Ejecutar el Script
En tu terminal con el entorno virtual activado, ejecuta el archivo principal `Proyecto final.py`:

```bash
python "Proyecto final.py"
```

### Paso 3.3: Pantalla de Calibración
Una vez que ejecutes el comando, el script tomará una "fotografía" inmediata de todo tu monitor y abrirá una ventana llamada **"Calibracion - Selecciona el area y presiona Enter"**.

1. Haz clic izquierdo sostenido y arrastra el ratón para **dibujar un rectángulo**.
2. **IMPORTANTE:** El rectángulo debe encerrar al dinosaurio en el lado izquierdo y cubrir una buena porción de camino vacío hacia la derecha. (Asegúrate de dejar algo de espacio vertical arriba para que el sistema detecte las aves).
3. Si te equivocas, vuelve a dibujar el rectángulo.
4. Una vez dibujado correctamente, presiona la tecla **ENTER** o **ESPACIO**.

### Paso 3.4: Menú Principal
En la consola de comandos (terminal) te aparecerá el menú interactivo:

```text
Selecciona una opción:
1. Jugar usando detección de contornos.
2. Jugar usando conteo de píxeles.
3. Recalibrar pantalla (Seleccionar ROI de nuevo)
4. Salir
```

1. Escribe **1** y presiona Enter para iniciar.
2. **ACCIÓN INMEDIATA:** Haz clic rápidamente en la ventana de Google Chrome para enfocar el juego. El bot empezará a correr en 3 segundos, y el juego comenzará a moverse.

### Paso 3.5: Supervisión y Visualización
Durante la ejecución del juego, el bot generará 3 ventanas de OpenCV que muestran el flujo de procesamiento en tiempo real:
1. **Frame Original y ROI**: Muestra lo que el bot está viendo y dibuja un cuadro azul que representa la "Región de Interés" (ROI). También incluye métricas (FPS, tiempo, método).
2. **Imagen Binaria**: Visualiza la umbralización del ROI (píxeles blancos sobre fondo negro).
3. **Detecciones en ROI**: Enmarca los obstáculos encontrados (Cactus o Aves) y calcula la toma de decisiones.

---

## 4. Finalizar la Partida y Ver el Reporte

Para detener el bot en cualquier momento:
1. Asegúrate de tener activa una de las ventanas de visualización de OpenCV o la terminal.
2. Presiona la tecla **Q** en tu teclado.
3. El bot se detendrá y la terminal imprimirá un **Reporte de Desempeño**, el cual incluye:
   - Tiempo de Supervivencia (segundos).
   - Promedio de Fotogramas Por Segundo (FPS).
   - Total de acciones de evasión (saltos/agachadas).
   - Lectura de Puntaje (OCR en la nube vía Roboflow DocTR): Extrae el Récord Histórico y el Puntaje Actual directamente de la pantalla y los imprime en consola.
   - Una guía teórica para apuntar manualmente los **Falsos Positivos** (el bot saltó a la nada) o **Falsos Negativos** (el bot chocó y no vio el obstáculo).

## 5. Consejos y Consideraciones Importantes

- **Foco de Ventana:** Para que el bot pueda inyectar la simulación de teclado (hacer saltar al dinosaurio), asegúrate de hacer clic dentro de la ventana de Google Chrome durante la cuenta regresiva inicial de 3 segundos.
- **Rendimiento Visual:** Evita arrastrar o mover agresivamente las ventanas de visualización de OpenCV mientras el bot juega, ya que esto puede pausar el hilo principal y hacer que el bot se estrelle.
- **Guardado de Calibración:** Al terminar de trazar el cuadro de calibración (ROI), recuerda presionar la tecla "ENTER" o "ESPACIO" en tu teclado para confirmar. No presiones la X de la ventana.
- **Precisión del OCR:** Para que la lectura del puntaje final sea impecable, el cuadro de calibración debe ser grande y abarcar tanto al dinosaurio como la sección superior derecha donde aparece el puntaje. Si el cuadro está mal dibujado, el bot tomará una foto de otro elemento y podría leer caracteres sin sentido.
- **Conexión a Internet:** El motor de extracción de texto DocTR se ejecuta en la nube de Roboflow, por lo que requieres una conexión a internet activa al momento de detener el bot para que pueda leer los puntajes.
