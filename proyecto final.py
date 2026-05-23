import cv2
import numpy as np
import mss
import keyboard
import time
import os

class DinoBot:
    """
    Clase principal que contiene la lógica de visión por computadora para interactuar 
    automáticamente con el juego del Dinosaurio de Google.

    Utiliza captura de pantalla en tiempo real y algoritmos de procesamiento de imágenes 
    (detección de contornos) para detectar obstáculos y evadirlos.
    """
    def __init__(self):
        """
        Inicializa las variables de estado, métricas y la instancia de captura de pantalla.

        Proceso:
            1. Crea una instancia de mss para la captura rápida.
            2. Inicializa las variables para las coordenadas de la pantalla (Bounding Boxes).
            3. Prepara las listas y contadores para medir el desempeño (Métricas).

        Args:
            Ninguno.

        Returns:
            None.
        """
        self.method = 'contours' # Define el algoritmo de visión a usar ('contours' = detección de contornos)
        self.sct = mss.mss()     # Instancia de mss para tomar capturas de pantalla a alta velocidad
        self.game_bbox = None    # Coordenadas (Bounding Box) del área completa del juego en la pantalla
        self.roi_bbox = None     # Coordenadas de la Región de Interés (ROI) justo delante del dinosaurio
        self.score_bbox = None   # Coordenadas de la región del puntaje
        self.center_bbox = None  # Coordenadas de la región central para detectar el "Game Over"
        
        # Variables de control de teclas no bloqueantes
        self.space_release_time = None
        self.down_press_time = None
        self.down_release_time = None
        self.needs_fast_fall = False
        self.air_wait_time = 0
        self.fast_fall_duration = 0.09
        
        # Métricas
        self.fps_list = []      # Lista para guardar los FPS de cada ciclo y calcular un promedio final
        self.start_time = None  # Instante de inicio para medir tiempo de supervivencia y aceleración del juego
        self.jumps = 0          # Contador del número total de saltos que hace el bot en la partida
        
    def calibrate(self):
        """
        Permite al usuario seleccionar la región de la pantalla que contiene el juego.

        Proceso:
            1. Toma una captura de todo el monitor utilizando mss.
            2. Redimensiona la imagen si la resolución es mayor a 1080p para ajustarla a la vista.
            3. Muestra una ventana de OpenCV (cv2.selectROI) pidiendo al usuario trazar un rectángulo 
               que cubra al dinosaurio y el camino por delante.
            4. Calcula y guarda matemáticamente una 'Región de Interés' (ROI) más pequeña 
               justo enfrente del dinosaurio, optimizando el área que se va a procesar en el futuro.

        Args:
            Ninguno.

        Returns:
            bool: True si la calibración fue exitosa (el usuario seleccionó un área). 
                  False si se canceló la operación o el área seleccionada es nula.
        """
        print("Capturando pantalla completa para calibración...")
        monitor = self.sct.monitors[1] # Monitor principal
        screenshot = np.array(self.sct.grab(monitor))
        screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
        
        # Redimensionar si la pantalla es muy grande (ej. 4K) para que quepa en la ventana de calibración
        screen_height, screen_width = screenshot.shape[:2]
        scale = 1.0
        if screen_width > 1920:
            scale = 1920 / screen_width
            screenshot = cv2.resize(screenshot, (0, 0), fx=scale, fy=scale)

        cv2.putText(screenshot, "Selecciona el AREA DEL JUEGO y presiona SPACE/ENTER", (50, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.putText(screenshot, "El area debe contener al dinosaurio y el camino por delante.", (50, 90), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        bbox = cv2.selectROI("Calibracion - Selecciona el area y presiona Enter", screenshot, fromCenter=False, showCrosshair=True)
        cv2.destroyWindow("Calibracion - Selecciona el area y presiona Enter")
        
        if bbox == (0, 0, 0, 0):
            print("Calibración cancelada o inválida.")
            return False
            
        # Ajustar por la escala si hubo redimensionamiento
        real_bbox = [int(v / scale) for v in bbox]

        # mss requiere top, left, width, height
        self.game_bbox = {
            "top": monitor["top"] + real_bbox[1],
            "left": monitor["left"] + real_bbox[0],
            "width": real_bbox[2],
            "height": real_bbox[3]
        }
        
        # Configurar región del puntaje (esquina superior derecha)
        # Aproximadamente el 25% superior y el 40% derecho del área de juego
        self.score_bbox = {
            "top": self.game_bbox["top"],
            "left": self.game_bbox["left"] + int(self.game_bbox["width"] * 0.60),
            "width": int(self.game_bbox["width"] * 0.40),
            "height": int(self.game_bbox["height"] * 0.25)
        }
        
        # Tomar la subimagen del juego (con escala de pantalla) y analizarla para detectar el dinosaurio
        game_img = screenshot[bbox[1]:bbox[1]+bbox[3], bbox[0]:bbox[0]+bbox[2]]
        gray = cv2.cvtColor(game_img, cv2.COLOR_BGR2GRAY)
        
        # Umbralización binaria adaptativa (soporte día/noche) para la detección
        if np.mean(gray) < 127:
            _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        else:
            _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
            
        # Buscar contornos (el dinosaurio debe estar en la mitad izquierda al inicio de la calibración)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        dino_bbox = None
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = w / h
            # El dinosaurio típicamente está en el primer 35% de la anchura de la ventana de calibración,
            # tiene relación de aspecto cercana a 1.0 (entre 0.6 y 1.4) y un tamaño razonable
            if x < bbox[2] * 0.35 and 0.6 < aspect_ratio < 1.4 and w > 15 and h > 15:
                # Convertir a coordenadas de píxeles reales (sin redimensionar)
                dino_bbox = (int(x / scale), int(y / scale), int(w / scale), int(h / scale))
                break

        if dino_bbox is not None:
            dx, dy, dw, dh = dino_bbox
            print(f"¡Dinosaurio detectado automáticamente en calibración! Posición: x={dx}, y={dy}, w={dw}, h={dh}")
            # Definir la ROI con precisión milimétrica basada en la silueta real del dinosaurio
            # Si es detectado, recalculamos los límites de la ROI píxel por píxel a partir de las coordenadas del dinosaurio:
            # - roi_left: 45 píxeles a la derecha del dinosaurio (antes 32). Este margen ampliado evita al 100% que la silueta del dinosaurio, incluso estirándose al agacharse, entre en contacto físico con la ROI.
            # - roi_width: 4.2 veces el ancho del dinosaurio (óptima distancia de escaneo).
            # - roi_top: Un 40% del alto del dinosaurio por encima de su cabeza (para aves medianas y altas).
            roi_left = dx + dw + 45          
            roi_width = int(dw * 4.2)        
            roi_top = dy - int(dh * 0.4)     
            roi_height = int(dh * 1.15)      
        else:
            print("No se detectó la silueta del dinosaurio. Usando porcentajes por defecto para la ROI.")
            # Fallback a porcentajes fijos si no se detectó el dinosaurio
            roi_left = int(real_bbox[2] * 0.35)  
            roi_width = int(real_bbox[2] * 0.40) 
            roi_top = int(real_bbox[3] * 0.3) 
            roi_height = int(real_bbox[3] * 0.50) # Reducido de 0.60 a 0.50 para mayor seguridad terrestre en fallback
        
        # Asegurar límites dentro de la imagen para evitar coordenadas fuera de rango (como top: -1)
        # que causan errores de aserción en cv2.cvtColor
        roi_top = max(0, min(roi_top, real_bbox[3] - 10))
        roi_left = max(0, min(roi_left, real_bbox[2] - 10))
        roi_width = max(10, min(roi_width, real_bbox[2] - roi_left))
        roi_height = max(10, min(roi_height, real_bbox[3] - roi_top))

        self.roi_bbox = {
            "top": roi_top,
            "left": roi_left,
            "width": roi_width,
            "height": roi_height
        }
        
        w, h = real_bbox[2], real_bbox[3]
        # Definir la región del puntaje (esquina superior derecha)
        self.score_bbox = {
            'top': self.game_bbox['top'] + int(h * 0.05),
            'left': self.game_bbox['left'] + int(w * 0.60),
            'width': int(w * 0.40),
            'height': int(h * 0.15)
        }
        
        # Definir la región central para detectar si el juego terminó
        self.center_bbox = {
            'top': self.game_bbox['top'] + int(h * 0.30),
            'left': self.game_bbox['left'] + int(w * 0.30),
            'width': int(w * 0.40),
            'height': int(h * 0.40)
        }
        
        print(f"Área de juego configurada: {self.game_bbox}")
        print(f"ROI configurado: {self.roi_bbox}")
        return True

    def process_frame(self, frame):
        """
        Aplica los métodos de visión por computadora elegidos sobre el frame actual 
        para detectar y enmarcar posibles obstáculos.

        Proceso:
            1. Recorta el frame usando la Región de Interés (ROI) definida en calibración.
            2. Convierte el recorte a escala de grises.
            3. Calcula el valor medio de los píxeles para determinar si el juego está en 
               modo de día (fondo claro) o modo noche (fondo oscuro).
            4. Aplica una umbralización binaria adaptándose al modo día/noche.
            5. Dependiendo de `self.method`, ejecuta `cv2.findContours` (Búsqueda de contornos) 
               o realiza sumatorias sobre las columnas de la matriz (Conteo de píxeles) para 
               identificar agrupaciones de píxeles que representan obstáculos.
            6. Clasifica cada obstáculo encontrado evaluando sus coordenadas.

        Args:
            frame (numpy.ndarray): Matriz tridimensional que representa el frame original a color capturado de la pantalla.

        Returns:
            tuple: Contiene los siguientes elementos:
                - frame (numpy.ndarray): Frame original sin recortes pero con información superpuesta.
                - roi (numpy.ndarray): Recorte de la imagen procesada a color donde se dibujan las cajas.
                - binary (numpy.ndarray): Imagen en blanco y negro producto de la umbralización.
                - obstacles (list): Lista de diccionarios, donde cada diccionario contiene la posición (x, y, w, h) y el tipo de obstáculo.
        """
        # Extraer ROI (Región de Interés)
        roi = frame[self.roi_bbox["top"]:self.roi_bbox["top"]+self.roi_bbox["height"], 
                    self.roi_bbox["left"]:self.roi_bbox["left"]+self.roi_bbox["width"]]
        
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        
        # Soporte para Modo Día/Noche
        if np.mean(gray) < 127:
            # Modo noche (fondo oscuro, obstáculos claros ~172)
            _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        else:
            # Modo día (fondo claro ~247, obstáculos oscuros ~83)
            _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)

        # Apertura morfológica con kernel VERTICAL (1,3):
        # Elimina líneas horizontales delgadas (suelo en modo noche, 1-2px de alto)
        # SIN destruir estructuras verticales como cactus delgados.
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 3))
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        
        # Cierre morfológico HORIZONTAL para agrupar cactus que están muy cerca
        # Esto soluciona el problema de que el bot veía un grupo de cactus como varios obstáculos individuales delgados.
        merge_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, merge_kernel)

        obstacles = []

        if self.method == 'contours':
            # Método 1: Detección de Contornos
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                if cv2.contourArea(cnt) > 80: # Ajustado a 80
                    x, y, w, h = cv2.boundingRect(cnt)
                    
                    # FILTRADO DE INTRUSIONES DEL DINOSAURIO (HOCICO/CUERPO):
                    # Cualquier contorno extremadamente cercano al borde izquierdo (x < 18) se descarta,
                    # previniendo que el hocico estirado del dinosaurio al saltar o agacharse en el aire sea detectado.
                    if x < 18:
                        continue
                        
                    # FILTRADO DE SUELO Y RUIDO PLANO DE TEXTURAS:
                    # Los cactus y aves tienen estructuras consistentes. Las texturas del suelo son bajas y/o estiradas.
                    # Filtramos de forma segura cualquier objeto menor a 10px de altura o muy alargado horizontalmente.
                    if h < 10 or (w / h > 3.0 and h < 15):
                        continue
                        
                    obs_type = self.classify_obstacle(y, h, self.roi_bbox["height"])
                    obstacles.append({"x": x, "y": y, "w": w, "h": h, "type": obs_type})
                    
                    # Dibujar bounding box para la visualización
                    if obs_type == 'cactus': color = (0, 0, 255)
                    elif obs_type == 'mid_bird': color = (0, 255, 255)
                    else: color = (255, 0, 0)
                    cv2.rectangle(roi, (x, y), (x+w, y+h), color, 2)
                    cv2.putText(roi, obs_type, (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        elif self.method == 'pixel_count':
            # Método 2: Conteo de Píxeles (Proyección Vertical)
            # Sumar verticalmente los píxeles blancos (valor 255)
            col_sums = np.sum(binary, axis=0) // 255
            
            # Buscaremos intervalos contiguos donde el número de píxeles activos sea mayor a 1 píxel (umbral de ruido)
            active_cols = np.where(col_sums > 1)[0]
            if len(active_cols) > 0:
                # Segmentar columnas activas en obstáculos independientes
                diffs = np.diff(active_cols)
                split_indices = np.where(diffs > 1)[0] + 1
                segments = np.split(active_cols, split_indices)
                
                for seg in segments:
                    if len(seg) == 0:
                        continue
                    x_start = int(seg[0])
                    x_end = int(seg[-1])
                    w = x_end - x_start + 1
                    
                    # Para encontrar los límites verticales y e h, sumamos horizontalmente en esta sub-región
                    row_sums = np.sum(binary[:, x_start:x_end+1], axis=1) // 255
                    active_rows = np.where(row_sums > 0)[0]
                    
                    if len(active_rows) > 0:
                        y = int(active_rows[0])
                        y_end = int(active_rows[-1])
                        h = y_end - y + 1
                        
                        # FILTRADO DE INTRUSIONES DEL DINOSAURIO (HOCICO/CUERPO):
                        if x_start < 18:
                            continue
                            
                        # FILTRADO DE SUELO Y RUIDO PLANO DE TEXTURAS:
                        if h < 10 or (w / h > 3.0 and h < 15):
                            continue
                            
                        obs_type = self.classify_obstacle(y, h, self.roi_bbox["height"])
                        obstacles.append({"x": x_start, "y": y, "w": w, "h": h, "type": obs_type})
                        
                        # Dibujar bounding box para la visualización
                        if obs_type == 'cactus': color = (0, 0, 255)
                        elif obs_type == 'mid_bird': color = (0, 255, 255)
                        else: color = (255, 0, 0)
                        cv2.rectangle(roi, (x_start, y), (x_end, y_end), color, 2)
                        cv2.putText(roi, obs_type, (x_start, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        return frame, roi, binary, obstacles

    def classify_obstacle(self, y, h, roi_height):
        """
        Evalúa la posición espacial vertical del obstáculo para determinar su tipo.

        Proceso:
            Calcula la posición de la base del obstáculo (y + altura). 
            Compara esta base con un umbral equivalente al 75% de la altura total 
            de la Región de Interés (el suelo). Si la base del obstáculo está por 
            encima del umbral, se asume que es un objeto volador. En caso contrario, 
            está tocando el piso.

        Args:
            y (int): Coordenada vertical (en píxeles) del punto superior izquierdo del obstáculo relativo al ROI.
            h (int): Altura del obstáculo en píxeles.
            roi_height (int): Altura total de la Región de Interés (ROI).

        Returns:
            str: Retorna 'bird' (ave) si el obstáculo flota, o 'cactus' si está posado en el suelo.
        """
        bottom_y = y + h
        
        # Ave muy alta: flota muy cerca del techo del ROI (0-30%)
        if bottom_y < roi_height * 0.3:
            return 'high_bird'
        # Ave media: flota a la altura de la cabeza del dinosaurio (30-75%)
        elif bottom_y < roi_height * 0.75:
            return 'mid_bird'
        # Cactus o ave baja: está cerca del suelo del ROI (75%+)
        else:
            return 'cactus'

    def play(self):
        """
        Bucle principal de ejecución del bot en tiempo real. 
        Maneja la captura de la pantalla, la toma de decisiones basada en el procesamiento 
        y la emisión de comandos de teclado.

        Proceso:
            1. Inicia un ciclo infinito que se rompe únicamente presionando la tecla 'q'.
            2. Captura un frame en cada iteración del área delimitada por `game_bbox`.
            3. Envía el frame a `process_frame` para obtener la lista de obstáculos.
            4. Regla de Decisión: Si existen obstáculos, localiza el más cercano (menor 'x').
               - Calcula un umbral de salto dinámico basado en el tiempo transcurrido, asumiendo 
                 que la velocidad del juego se incrementa.
               - Si el objeto más cercano rebasa el umbral y es un ave alta, simula presionar 
                 la tecla 'Abajo' para agacharse.
               - Si es un cactus o ave baja, simula presionar 'Espacio' para saltar y posteriormente 
                 'Abajo' para forzar una caída rápida.
            5. Superpone elementos visuales y métricas de rendimiento en los frames y los 
               muestra en ventanas de OpenCV (`cv2.imshow`).
            6. Al finalizar el ciclo, dispara `report_metrics` con el total registrado.

        Args:
            Ninguno.

        Returns:
            None.
        """
    def init_windows(self):
        """
        Inicializa las ventanas de visualización de OpenCV y las posiciona en la pantalla.
        
        Proceso:
            Crea las ventanas necesarias antes de iniciar la partida y las mueve a la 
            esquina superior izquierda del monitor. Esto previene que al llamar a imshow 
            durante el juego, el sistema operativo le robe el "foco" a la ventana de Chrome 
            y detenga el dinosaurio.
        
        Args:
            Ninguno.

        Returns:
            None.
        """
        cv2.namedWindow("Dino Bot Vision")
        cv2.moveWindow("Dino Bot Vision", 10, 10)
        
        # Inyectar un frame inicial con las MEDIDAS EXACTAS para evitar redimensionado
        empty_game = np.zeros((self.game_bbox["height"], self.game_bbox["width"], 3), dtype=np.uint8)
        cv2.imshow("Dino Bot Vision", empty_game)
        cv2.waitKey(1)

    def play(self):
        """
        Bucle principal de ejecución del bot en tiempo real. 
        Maneja la captura de la pantalla, la toma de decisiones basada en el procesamiento 
        y la emisión de comandos de teclado de manera asíncrona no bloqueante.

        Proceso:
            1. Inicia un ciclo infinito que se rompe únicamente presionando la tecla 'q'.
            2. Gestiona la liberación programada de teclas ('space' y 'down') de forma no bloqueante.
            3. Captura un frame en cada iteración del área delimitada por `game_bbox`.
            4. Envía el frame a `process_frame` para obtener la lista de obstáculos.
            5. Regla de Decisión: Si existen obstáculos y no hay una acción física activa en curso:
               - Localiza el más cercano (menor 'x').
               - Calcula un umbral de salto dinámico basado en el tiempo transcurrido (aceleración del juego).
               - Si el objeto más cercano rebasa el umbral:
                 * Para 'high_bird': No hace nada (pasa caminando por debajo).
                 * Para 'mid_bird': Presiona 'down' y programa su liberación asíncrona.
                 * Para 'cactus' / 'low_bird': Presiona 'space', calcula tiempos asíncronos y programa el 'down' asíncrono para caída rápida.
            6. Superpone elementos visuales y métricas de rendimiento en los frames y los 
               muestra en ventanas de OpenCV (`cv2.imshow`).
            7. Al finalizar el ciclo, libera de forma segura todas las teclas y reporta métricas.
        """
        print(f"\nIniciando bot con método: {self.method.upper()}")
        print("Asegúrate de haber hecho CLICK en la ventana de Chrome.")
        print("Presiona 'q' en la ventana de OpenCV o en la consola para detener.")
        
        self.fps_list = []
        self.jumps = 0
        self.start_time = time.time()
        self.last_action_time = 0
        
        # Reiniciar variables de control asíncrono de teclas
        self.space_release_time = None
        self.down_press_time = None
        self.down_release_time = None
        self.needs_fast_fall = False
        
        # Parámetros para la distancia de reacción inicial
        # Aumentado de 0.07 a 0.22 para darle mayor anticipación al salto y evitar que salte muy cerca
        base_jump_dist = int(self.roi_bbox["width"] * 0.22) 
        
        history_center = [] # Historial de fotogramas del centro de la pantalla
        
        while True:
            if keyboard.is_pressed('q'):
                print("Detenido por el usuario.")
                break
                
            # --- DETECCIÓN AUTOMÁTICA DE GAME OVER ---
            center_screenshot = np.array(self.sct.grab(self.center_bbox))
            center_gray = cv2.cvtColor(center_screenshot, cv2.COLOR_BGRA2GRAY)
            history_center.append(center_gray)
            
            if len(history_center) > 30: # Mantener historial de ~0.5 segundos
                old_center = history_center.pop(0)
                # Si la pantalla central no se ha movido nada en 30 frames
                diff = cv2.absdiff(old_center, center_gray)
                if cv2.countNonZero(diff) == 0:
                    # Comprobar que no es simplemente el cielo vacío buscando bordes 
                    # (como el botón de reinicio o las letras de "Game Over")
                    edges = cv2.Canny(center_gray, 50, 150)
                    if cv2.countNonZero(edges) > 50:
                        print("\n[!] ¡Juego terminado detectado automáticamente! Deteniendo el bot...")
                        break
            # ----------------------------------------
                
            now = time.time()
            frame_start = now
            
            # --- GESTIÓN ASÍNCRONA DE TECLADO (NO BLOQUEANTE) ---
            # 1. Soltar espacio
            if self.space_release_time is not None and now >= self.space_release_time:
                keyboard.release('space')
                self.space_release_time = None
                
                # Si requiere caída rápida, programamos la pulsación de 'down' tras esperar en el aire
                if self.needs_fast_fall:
                    self.down_press_time = now + self.air_wait_time
                    self.needs_fast_fall = False
            
            # 2. Pulsar 'down' para caída rápida (después de estar en el aire)
            if self.down_press_time is not None and now >= self.down_press_time:
                keyboard.press('down')
                self.down_release_time = now + self.fast_fall_duration  # Duración del pulso ultracorto
                self.down_press_time = None
                
            # 3. Soltar 'down'
            if self.down_release_time is not None and now >= self.down_release_time:
                keyboard.release('down')
                self.down_release_time = None
            
            # --- CAPTURA Y PROCESAMIENTO ---
            # 1. Capturar pantalla en tiempo real
            screenshot = np.array(self.sct.grab(self.game_bbox))
            frame = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
            
            # 2. Procesamiento de imagen y Detección
            frame_drawn, roi, binary, obstacles = self.process_frame(frame.copy())
            
            # --- COMPROBACIÓN DE PANTALLA CONGELADA (Para evitar saltos fantasma) ---
            is_static = False
            if len(history_center) >= 2:
                diff_immediate = cv2.absdiff(history_center[-2], history_center[-1])
                # Si el cambio inmediato es casi nulo, el juego se ha congelado (dinosaurio muerto)
                if cv2.countNonZero(diff_immediate) < 10:
                    is_static = True
            
            # Calcular tiempo transcurrido y umbral de salto para que estén disponibles en el HUD
            elapsed = now - self.start_time
            jump_threshold = base_jump_dist + int(elapsed * 2.1) # Incrementa con el tiempo
            jump_threshold = min(jump_threshold, self.roi_bbox["width"] * 0.85)
            
            # --- TOMA DE DECISIONES ---
            if obstacles:
                # Estimar distancia horizontal al obstáculo más cercano
                closest = min(obstacles, key=lambda o: o['x'])
                dist = closest['x']
                
                # Solo actuar si el bot no está ocupado y el juego no está congelado
                is_busy = (self.space_release_time is not None or 
                           self.down_press_time is not None or 
                           self.down_release_time is not None)
                
                if dist < jump_threshold and not is_busy and not is_static and (now - self.last_action_time > 0.15):
                    if closest['type'] == 'high_bird':
                        # Ave alta: Ignorar por completo (pasar por debajo de pie)
                        pass
                    elif closest['type'] == 'mid_bird':
                        # Ave media: Agacharse asíncronamente
                        keyboard.press('down')
                        self.down_release_time = now + 0.55  # Agachado durante 550ms
                        self.last_action_time = now
                    else:
                        # Cactus / Ave baja: Saltar asíncronamente
                        # A mayor ancho del obstáculo, más tiempo presionamos 'space' para saltar más lejos
                        jump_time = min(0.24, 0.11 + max(0, (closest['w'] - 20) * 0.002))
                        
                        # Ajustamos los tiempos para una caída rápida perfecta.
                        # Al mantener 'down' por 90ms, aplicamos la aceleración gravitacional completa en el aire,
                        # pero soltamos la tecla justo antes de tocar el suelo para evitar que se agache al aterrizar.
                        self.air_wait_time = 0.04       # Espera corta de 40ms en el aire tras soltar espacio
                        self.fast_fall_duration = 0.09  # Pulso de 90ms de caída rápida (se libera antes de aterrizar)
                        
                        keyboard.press('space')
                        self.jumps += 1
                        self.space_release_time = now + jump_time
                        self.needs_fast_fall = True
                        self.last_action_time = now
            
            # Visualización del ROI en el frame principal
            cv2.rectangle(frame_drawn, 
                          (self.roi_bbox["left"], self.roi_bbox["top"]), 
                          (self.roi_bbox["left"]+self.roi_bbox["width"], self.roi_bbox["top"]+self.roi_bbox["height"]), 
                          (255, 0, 0), 2)
            cv2.putText(frame_drawn, "Región de Interés (ROI)", (self.roi_bbox["left"], self.roi_bbox["top"] - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
            
            # Cálculo de FPS
            frame_time = time.time() - frame_start
            fps = 1 / frame_time if frame_time > 0 else 0
            self.fps_list.append(fps)
            
            # HUD de información y métricas en pantalla
            cv2.putText(frame_drawn, f"FPS: {fps:.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
            cv2.putText(frame_drawn, f"Metodo: {self.method}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
            cv2.putText(frame_drawn, f"Tiempo: {elapsed:.1f}s", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
            cv2.putText(frame_drawn, f"Dist. Reaccion: {jump_threshold:.1f}px", (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
            
            # Mostrar solo una ventana consolidada para no molestar
            cv2.imshow("Dino Bot Vision", frame_drawn)
            
            # El waitKey es fundamental para que OpenCV actualice las ventanas
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
        # Asegurar la liberación de teclas SÓLO si se quedaron atascadas apretadas
        if self.space_release_time is not None:
            keyboard.release('space')
        if self.down_press_time is not None or self.down_release_time is not None:
            keyboard.release('down')
        
        # --- NUEVO: CAPTURAR PUNTAJE CON OCR AL FINAL ---
        print("\nEl juego terminó. Esperando 2 segundos a que el puntaje deje de parpadear...")
        time.sleep(2)
        print("Capturando puntaje final con OCR de la pantalla...")
        try:
            score_screenshot = np.array(self.sct.grab(self.score_bbox))
            score_img = cv2.cvtColor(score_screenshot, cv2.COLOR_BGRA2BGR)
            # ==========================================================
            # OCR BASADO EN CLOUD (Roboflow DocTR) - Alternativa a Tesseract
            # Este modelo profundo es infinitamente superior leyendo fuentes raras
            # ==========================================================
            import requests
            import base64
            
            # API Key obtenida de tu práctica YOLO.py
            API_KEY = "azVdtlsMqIztEFFGAtmR"
            ENDPOINT_ROBOFLOW_OCR = f"https://infer.roboflow.com/doctr/ocr?api_key={API_KEY}"
            
            try:
                # Convertimos el pequeño recorte del puntaje (BGB normal) a JPG
                _, buffer = cv2.imencode('.jpg', score_img)
                img_b64 = base64.b64encode(buffer).decode('utf-8')
                
                payload = {
                    "image": {
                        "type": "base64",
                        "value": img_b64
                    }
                }
                
                print("Consultando puntaje en la nube con DocTR...")
                respuesta = requests.post(ENDPOINT_ROBOFLOW_OCR, json=payload, timeout=10)
                
                if respuesta.status_code == 200:
                    datos = respuesta.json()
                    raw_text = datos.get("result", "").strip()
                else:
                    print(f"Error de API: {respuesta.status_code}")
                    raw_text = ""
                    
            except Exception as e:
                print(f"Fallo de conexión OCR: {str(e)}")
                raw_text = ""
                
            # Procesar el resultado para separarlo lógicamente
            import re
            numeros = re.findall(r'\d+', raw_text)
            
            if len(numeros) >= 2:
                final_score_text = f"Récord: {numeros[0]} | Actual: {numeros[-1]}"
            elif len(raw_text) > 5:
                # Si Tesseract omitió el espacio (ej. HI0382500241), separamos por longitud
                # Los últimos 5 dígitos son el actual, los 5 anteriores el récord
                solo_nums = re.sub(r'[^\d]', '', raw_text)
                if len(solo_nums) >= 10:
                    final_score_text = f"Récord: {solo_nums[-10:-5]} | Actual: {solo_nums[-5:]}"
                else:
                    final_score_text = f"Actual: {solo_nums}"
            else:
                final_score_text = raw_text
                
        except Exception as e:
            final_score_text = f"Error de OCR: {e}"
        
        # Calcular y reportar resultados cuando el juego se detiene
        survival_time = time.time() - self.start_time
        avg_fps = np.mean(self.fps_list) if self.fps_list else 0
        
        cv2.destroyAllWindows()
        self.report_metrics(survival_time, avg_fps, final_score_text)

    def report_metrics(self, survival_time, avg_fps, final_score_text="No capturado"):
        """
        Imprime en consola un reporte detallado del desempeño del sistema al terminar la partida.

        Proceso:
            Toma las métricas recabadas durante el ciclo `play()` y formatea su salida 
            para el usuario mediante impresiones en la consola. Además, emite consideraciones 
            teóricas respecto a los falsos positivos y negativos solicitados en el proyecto.

        Args:
            survival_time (float): Cantidad total de segundos transcurridos desde que inició `play()` hasta que finalizó.
            avg_fps (float): Promedio matemático de todos los fotogramas procesados por segundo (FPS) en la sesión.
            final_score_text (str): Texto del puntaje detectado por OCR.

        Returns:
            None.
        """
        print("\n" + "="*50)
        print("=== REPORTE DE DESEMPEÑO ===")
        print("="*50)
        print(f"Método utilizado       : {self.method.capitalize()}")
        print(f"Tiempo de supervivencia: {survival_time:.2f} segundos")
        print(f"Puntaje Final (OCR)    : {final_score_text if final_score_text else 'No se detectó texto'}")
        print(f"FPS Promedio           : {avg_fps:.2f} FPS")
        print(f"Total de saltos (jumps): {self.jumps}")
        print("-" * 50)
        print("Nota sobre Falsos Positivos / Negativos:")
        print(" - Falsos Positivos: Si viste al bot saltar cuando no había")
        print("   obstáculo en la ROI (comúnmente ruido de fondo).")
        print(" - Falsos Negativos: Si el bot chocó con un obstáculo sin intentar")
        print("   esquivarlo a tiempo o detectarlo.")
        print(" (Anotar estos valores requiere observación del usuario tras terminar la corrida)")
        print("="*50 + "\n")


def menu():
    """
    Punto de entrada de la aplicación en la interfaz de línea de comandos.

    Proceso:
        1. Instancia la clase principal `DinoBot`.
        2. Ejecuta obligatoriamente el procedimiento de calibración inicial.
        3. Muestra un menú de opciones iterativo donde el usuario puede elegir 
           iniciar la ejecución del bot, recalibrar la pantalla o salir del programa.
        4. Transfiere el control de ejecución al método `bot.play()` si el 
           usuario elige iniciar.

    Args:
        Ninguno.

    Returns:
        None.
    """
    bot = DinoBot()
    
    print("=====================================================")
    print("--- PROYECTO FINAL VISIÓN Y ANIMACIÓN POR COMPUTADORA ---")
    print("          Juego del Dinosaurio Automático")
    print("=====================================================")
    print("Asegúrate de tener el juego del dinosaurio abierto en tu navegador.\n")
    
    # 1. Calibración obligatoria inicial
    if not bot.calibrate():
        print("No se pudo calibrar correctamente. Saliendo del programa.")
        return
        
    while True:
        print("\nSelecciona una opción:")
        print("1. Jugar usando detección de contornos.")
        print("2. Jugar usando conteo de píxeles.")
        print("3. Recalibrar pantalla (Seleccionar ROI de nuevo)")
        print("4. Salir")
        
        choice = input("\nOpción seleccionada: ")
        
        if choice == '1':
            bot.method = 'contours'
            print("\n> Recuerda: El bot simulará teclas.")
            bot.init_windows()
            print("> Haz click en la ventana de Chrome para darle el foco (importante).")
            print("> Iniciando en 3 segundos...")
            time.sleep(3)
            bot.play()
        elif choice == '2':
            bot.method = 'pixel_count'
            print("\n> Recuerda: El bot simulará teclas.")
            bot.init_windows()
            print("> Haz click en la ventana de Chrome para darle el foco (importante).")
            print("> Iniciando en 3 segundos...")
            time.sleep(3)
            bot.play()
        elif choice == '3':
            bot.calibrate()
        elif choice == '4':
            print("Cerrando programa...")
            break
        else:
            print("Opción inválida. Intenta nuevamente.")

if __name__ == "__main__":
    menu()
