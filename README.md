# LoRa BBS Gateway v0.1
Sistema BBS escrito en Python compatible con LoRa. En los casos de prueba fue utilizado dos Raspberry Pi Pico + SX1278. El firmware se comparte en los adjuntos junto con el esquema de conexiones.<br>
Ha sido probado de PC a PC y PC a celular Android, aunque es compatible con cualquier sistema que admita conexión vía puerto serie.

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

# Licencia
Este proyecto utiliza licencia MIT, leer la licencia para descargo de responsabilidades.
