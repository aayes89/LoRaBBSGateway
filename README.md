# LoRa BBS Gateway v0.1
Es un proyecto compuesto que consta de un sistema <b>BBS</b> escrito en Python y un firmware compatible con tecnología <a href="https://es.wikipedia.org/wiki/LoRa">LoRa</a>.<br>
Para la comunicación LoRa, en los casos de prueba fue utilizado dos Raspberry Pi Pico conectadas a un módulo SX1278 (433MHz) respectivamente.<br>
<b>(El firmware se comparte en los adjuntos junto con el esquema de conexiones.)</b><br>
Ha sido probado de PC a PC y PC a celular Android, aunque es compatible con cualquier sistema que admita conexión vía puerto serie.<br>
Queda por definir el alcance de la señal, aunque en promedio y según condiciones (altura de la antena, obstáculos) puede rondar entre algunos metros a algunos kilómetros (ver <a href="https://www-hackster-io.translate.goog/news/another-record-breaking-transmission-for-lorawan-0cca5f6cd032?_x_tr_sl=en&_x_tr_tl=es&_x_tr_hl=es&_x_tr_pto=tc"> Récords de transmisión</a>)

# Funcionalidades
 * Buscar en DuckDuckGo
 * Buscar en Wikipedia
 * Ver clima actual
 * Noticias recientes (Google News)
 * Consultar IA (LM Studio local)
 * Chat/Foro
 * Tablón de anuncios
 * Jugar Trivia (Sobre LoRa usando LM Studio)
 * Calendario
 * Tasas de Cambio

# Esquema de conexión Raspberry Pi Pico a SX1278
* RPI (5) - LORA SS    
* RPI (6) - LORA RST   
* RPI (7) - LORA DIO0  
* RPI (2) - LORA SCK
* RPI (4) - LORA MISO 
* RPI (3) - LORA MOSI 
* RPI LED_PIN 25 (por defecto)

# Configuración PC (servidor)
* Descarga o clona el repositorio.
* Modifica el parámetro del puerto COM según tu Sistema Operativo. Para Windows (COM#) y para Linux/MacOS (/dev/ttyS# o /dev/ttyACM#).
* Ejecuta en tu terminal de preferencia <code>python bbs_server_rpi.py</code>

# Configuración (clientes)
* PC (Windows): descarga e instala TeraTerm/SmartTTY/Putty y configura el puerto COM a 115200 baudios.
* PC (Linux): descarga e instala minicom (otros similares) y configura el puerto (/dev/ttyS# o /dev/ttyACM#) a 115200 baudios.
* Android: descarga e instala <a href="https://play.google.com/store/apps/details?id=de.kai_morich.serial_usb_terminal&hl=es_MX">Serial USB Terminal</a> y configura el puerto (/dev/ttyS# o /dev/ttyACM#) a 115200 baudios. 

# Por mejorar / hacer
* Seguridad: cifrar mensajes al transmitir (actualmente envío transparente).
* Seguridad: sistema de autenticación segura (actualmente sólo login para nick en Foro/Chat y Trivia)
* Seguridad: administración de privilegios para usuarios. (por implementar)
* Reparar la búsqueda en DuckDuckGo (el scrapping de la web cambia constantemente)
* Validar que la tasa cambiaria sea oficial según país. (utiliza API gratuita, puede no ser confiable. Se deja aviso durante el uso.)

# Licencia
Este proyecto utiliza licencia MIT, leer la licencia para descargo de responsabilidades.

# Capturas

<b> Noticias </b>

<img width="1105" height="486" alt="imagen" src="https://github.com/user-attachments/assets/fabb5201-0160-45ee-8e1a-30964fed6f53" />

<b> El Clima </b>

<img width="305" height="323" alt="imagen" src="https://github.com/user-attachments/assets/6cc5e396-d019-4a4f-b29f-be37ebc5228b" />

<b> Calendario </b>

<img width="472" height="706" alt="imagen" src="https://github.com/user-attachments/assets/9afa6b95-875d-4bee-aae0-71d0c15a7490" />

<b> Tasas de cambio </b>

<img width="416" height="508" alt="imagen" src="https://github.com/user-attachments/assets/651e56be-d185-40e1-b9c3-8cf87e69beb2" />

