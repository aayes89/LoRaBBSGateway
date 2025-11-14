#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Slam (2025"
LoRa BBS Gateway - versión 0.1
 - DuckDuckGo con parsing robusto (fallback regex)
 - Wikipedia con encoding UTF-8 y headers
 - LLM: timeout 180s, bucle de prompts hasta 'salir'/'quit', cambio de modelo
 - Sesión persistente, estable, solo responde a órdenes
"""
import serial
import threading
import time
import http.client
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import json
import calendar
from datetime import datetime  # (Opcional) usa time para timestamp
import re
# ---------------- CONFIG ----------------
SERIAL_PORT = "COM14"  # /dev/ttyACM0 o /dev/ttyS0 en Linux
BAUDRATE = 115200 # velocidad por defecto
LM_BASE_URL = "127.0.0.1:1234"  # cambiar IP a servidor LM Studio local
LLM_TIMEOUT = 180  # 3 min para carga de modelo
# ------------ MENU PRINCIPAL -------------------
MENU_TEXT = (    
    "\n=== 📡 LoRa BBS Gateway v0.1 ===\n"    
    "1) Buscar en DuckDuckGo\n"
    "2) Buscar en Wikipedia\n"
    "3) Ver clima actual\n"
    "4) Noticias recientes (Google News)\n"
    "5) Consultar LLM local\n"
    "6) Chat/Foro\n"
    "7) Tablón de anuncios\n"
    "8) Jugar Trivia\n"
    "9) Calendario\n"
    "10) Tasas de Cambio\n"
    "0) Créditos\n"
    "q) Desconectar\n"
    "> "
)
# ------------------------------------------------
class LoRaBBS:
    def __init__(self, port, baud):
        self.ser = serial.Serial(port, baud, timeout=0.1)
        self.lock = threading.Lock()
        self.session_active = False
        self.session_name = None
        # --- Foro/Chat conf ---
        self.online_users = set()
        self.chat_public = []
        self.private_messages = {}
        self.chat_file = "chat_public.json"
        self.private_file = "private_chat.json"
        self.load_chat()
        self.load_private()        
        
        # --- Tablero de anuncios ---
        self.boards = {}  # {categoria: [{'user': msg, 'timestamp': ts}]}
        self.boards_file = "boards.json"
        self.load_boards()        
        
        # --- Juego interactivo por LLM ---
        self.score = 0 # Puntaje por sesión
        
        # --- MultiTareas ---        
        threading.Thread(target=self._reader_loop, daemon=True).start()
        print(f"[*] Servidor BBS activo en {port} @ {baud} bps")

    # --- utilidades ---
    def send(self, text: str):
        with self.lock:
            self.ser.write(text.encode('utf-8', errors='ignore'))
            self.ser.flush()

    def read_line_blocking(self, timeout=None):
        buf = b""
        start = time.time()
        while True:
            if self.ser.in_waiting:
                b = self.ser.read(1)
                if b in (b'\n', b'\r'):
                    if buf:
                        break
                    else:
                        continue
                buf += b
            else:
                if timeout and (time.time() - start) > timeout:
                    break
                time.sleep(0.02)
        return buf.decode('utf-8', errors='ignore').strip()

    # --- funcionalidades ---
    def search_duckduckgo(self, query):
        import http.client
        import urllib.parse
        import re

        try:
            q = urllib.parse.quote_plus(query)
            conn = http.client.HTTPSConnection("duckduckgo.com", timeout=10)
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "es-ES,es;q=0.9"
            }

            conn.request("GET", f"/html/?q={q}&kl=es-es", headers=headers)
            resp = conn.getresponse()

            if resp.status != 200:
                conn.close()
                return f"Error de servidor DuckDuckGo: {resp.status} {resp.reason}\n"

            html = resp.read().decode('utf-8', errors='ignore')
            conn.close()

            # Patrón robusto: cualquier <a> que sea un resultado de búsqueda
            pattern = (
                r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>'
                r'(.*?)</a>'
            )

            matches = re.findall(pattern, html, re.S | re.I)

            # fallback: intentar encontrar la primera coincidencia aunque sea parcial
            if not matches:
                fb = re.search(pattern, html, re.S | re.I)
                if fb:
                    matches = [(fb.group(1), fb.group(2))]

            if not matches:
                return "No se encontraron resultados.\n"

            link_raw, title_raw = matches[0]

            # Limpieza del título
            title = re.sub(r'<.*?>', '', title_raw)
            title = re.sub(r'\s+', ' ', title).strip()
            if len(title) > 200:
                title = title[:200] + "..."

            # Normalización del enlace
            link = link_raw.strip()

            # Formatos típicos de DuckDuckGo
            if link.startswith('//'):
                link = "https:" + link
            elif link.startswith('/l/?uddg='):
                # Redirección codificada
                target = link.split("uddg=", 1)[1]
                link = urllib.parse.unquote(target)
            elif link.startswith('/'):
                link = "https://duckduckgo.com" + link

            return f"{title}\n{link}\n"

        except Exception as e:
            return f"Error DuckDuckGo: {e}\n"


    def search_wikipedia(self, term, lang="es"):
        try:
            # Encoding robusto para títulos con acentos/español
            title = urllib.parse.quote(term.replace(" ", "_").encode('utf-8').decode('utf-8'))
            conn = http.client.HTTPSConnection(f"{lang}.wikipedia.org", timeout=10)
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            conn.request("GET", f"/api/rest_v1/page/summary/{title}", headers=headers)
            resp = conn.getresponse()
            raw = resp.read().decode('utf-8', errors='ignore')
            conn.close()
            if resp.status != 200:
                return f"No se encontró página para '{term}' ({resp.status})\n"
            data = json.loads(raw)
            summary = data.get("extract") or "Sin resumen disponible."
            if len(summary) > 900:
                summary = summary[:900] + "..."
            return f"{summary}\n"
        except json.JSONDecodeError:
            return f"Respuesta inválida de Wikipedia para '{term}'\n"
        except Exception as e:
            return f"Error Wikipedia: {e}\n"

    def get_weather(self, city):
        try:
            conn = http.client.HTTPSConnection("wttr.in", timeout=6)
            path = f"/{urllib.parse.quote(city)}?format=3"
            conn.request("GET", path)
            resp = conn.getresponse()
            data = resp.read().decode('utf-8', errors='ignore')
            conn.close()
            return f"{data}\n"
        except Exception as e:
            return f"Error clima: {e}\n"

    def get_news_google_rss(self, country, hl="es-419"):
        # Mapeo de nombres de países comunes a códigos ISO (gl y ceid)
        country_to_code = {
            "México": "MX", "Mexico": "MX","MX":"MX",
            "Estados Unidos": "US", "USA": "US", "United States": "US",
            "España": "ES", "Spain": "ES",
            "Argentina": "AR",
            "Brasil": "BR", "Brazil": "BR",
            "Chile": "CL",
            "China":"CH",
            "Colombia": "CO",
            "Cuba":"CU","CU":"CU",
            "Perú": "PE", "Peru": "PE",
            "Puerto Rico":"PR",
            "Venezuela": "VE",
            "Francia": "FR", "France": "FR",
            "Alemania": "DE", "Germany": "DE",
            "Reino Unido": "GB", "UK": "GB", "United Kingdom": "GB",
            "Italia": "IT", "Italy": "IT",
            "Canadá": "CA", "Canada": "CA",
            "Australia": "AU"            
        }
        code = country_to_code.get(country.title().strip(), None)
        if code is None:
            return f"País no reconocido: '{country}'. Usa ej. 'México', 'España', 'USA'.\n"
        # Ajustar hl según el país (español para América Latina, es-ES para España)
        if code == "ES":
            hl = "es-ES"
        try:
            conn = http.client.HTTPSConnection("news.google.com", timeout=8)
            conn.request("GET", f"/rss?hl={hl}&gl={code}&ceid={code}:{hl}")
            resp = conn.getresponse()
            xml_data = resp.read().decode('utf-8', errors='ignore')
            conn.close()
            root = ET.fromstring(xml_data)
            items = root.findall(".//item")[:10]
            if not items:
                return "No hay noticias disponibles para este país.\n"
            out = f"Últimas noticias de {country.title()}:\n"
            for it in items:
                title = it.findtext("title", "Sin título")
                out += f"- {title}\n"
            return out
        except ET.ParseError:
            return "Error al parsear el feed RSS.\n"
        except Exception as e:
            return f"Error noticias: {e}\n"

    # --- LLM ---
    def get_llm_models(self):
        try:
            conn = http.client.HTTPConnection(LM_BASE_URL, timeout=8)
            conn.request("GET", "/v1/models")
            resp = conn.getresponse()
            raw = resp.read().decode('utf-8', errors='ignore')
            conn.close()
            if resp.status != 200:
                return [], f"Error al obtener modelos ({resp.status})\n"
            j = json.loads(raw)
            if isinstance(j, dict) and "data" in j:
                models = [m.get("id", "sin_id") for m in j["data"]]
            elif isinstance(j, list):
                models = [m.get("id", "sin_id") for m in j]
            else:
                models = ["modelo_por_defecto"]
            return models, ""
        except Exception as e:
            return [], f"Error LLM/models: {e}\n"

    def call_llm(self, model, prompt):
        try:
            conn = http.client.HTTPConnection(LM_BASE_URL, timeout=LLM_TIMEOUT)
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 4096  # Aumentado para respuestas más largas; ajusta según el modelo si es necesario
            }
            body = json.dumps(payload)
            headers = {"Content-Type": "application/json"}
            conn.request("POST", "/v1/chat/completions", body, headers)
            resp = conn.getresponse()
            # Leer la respuesta completa hasta EOF
            raw = b""
            while True:
                chunk = resp.read(4096)  # Leer en chunks para manejar respuestas muy grandes
                if not chunk:
                    break
                raw += chunk
            raw = raw.decode('utf-8', errors='ignore')
            conn.close()
            if resp.status != 200:
                return f"Error LLM ({resp.status}): {raw}\n"
            j = json.loads(raw)
            text = None
            if "choices" in j and len(j["choices"]) > 0:
                c = j["choices"][0]
                if isinstance(c, dict) and "message" in c and "content" in c["message"]:
                    text = c["message"]["content"]
                elif "text" in c:
                    text = c["text"]
            if not text:
                text = json.dumps(j)
            # Sin truncado: retorna el texto completo
            return text + "\n"
        except Exception as e:
            return f"Error LLM/chat: {e}\n"
    # --- Foro/Chat ---
    # Añadir estos métodos nuevos a la clase LoRaBBS:
    def load_chat(self):
        try:
            with open(self.chat_file, 'r', encoding='utf-8') as f:
                self.chat_public = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.chat_public = []

    def save_chat(self):
        try:
            with open(self.chat_file, 'w', encoding='utf-8') as f:
                json.dump(self.chat_public, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load_private(self):
        try:
            with open(self.private_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.private_messages = {to_user: {sender: msg_list for sender, msg_list in senders.items()} 
                                         for to_user, senders in data.items()}
        except (FileNotFoundError, json.JSONDecodeError):
            self.private_messages = {}

    def save_private(self):
        try:
            with open(self.private_file, 'w', encoding='utf-8') as f:
                json.dump(self.private_messages, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def chat_system(self):
        self.send("=== Modo Chat/Foro ===\n")
        self.send("Comandos:\n")
        self.send("- public <mensaje>: Postear en sala pública\n")
        self.send("- to <usuario> <mensaje>: Enviar privado (se guarda si no está presente)\n")
        self.send("- getusers: Listar usuarios presentes\n")
        self.send("- viewpublic: Ver últimos 10 mensajes públicos\n")
        self.send("- viewprivate: Ver privados pendientes\n")
        self.send("- salir: Volver al menú\n")
        self.send("> ")
        while True:
            line = self.read_line_blocking()
            if not line:
                continue
            cmd = line.strip()
            if cmd.lower() == "salir":
                break
            elif cmd == "getusers":
                if self.online_users:
                    self.send(f"Usuarios presentes: {', '.join(sorted(self.online_users))}\n")
                else:
                    self.send("No hay usuarios presentes.\n")
            elif cmd == "viewpublic":
                if self.chat_public:
                    recent = self.chat_public[-10:]
                    self.send("Sala pública (últimos 10):\n---\n")
                    for msg in recent:
                        self.send(f"{msg}\n")
                    self.send("---\n")
                else:
                    self.send("Sala pública vacía.\n")
            elif cmd == "viewprivate":
                if self.session_name in self.private_messages and self.private_messages[self.session_name]:
                    self.send("Mensajes privados pendientes:\n---\n")
                    for sender, msg_list in self.private_messages[self.session_name].items():
                        for msg in msg_list:
                            self.send(f"{sender}: {msg}\n")
                    self.send("---\n")
                else:
                    self.send("No hay mensajes privados pendientes.\n")
            elif cmd.startswith("public "):
                msg = cmd[7:].strip()
                if msg:
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    entry = f"[{timestamp}] {self.session_name}: {msg}"
                    self.chat_public.append(entry)
                    self.save_chat()
                    self.send("Mensaje enviado a la sala pública.\n")
                else:
                    self.send("Mensaje vacío, ignoro.\n")
            elif cmd.startswith("to "):
                parts = cmd[3:].split(maxsplit=1)
                if len(parts) != 2:
                    self.send("Uso: to <usuario> <mensaje>\n")
                    continue
                target, msg = parts[0].strip(), parts[1].strip()
                if not msg:
                    self.send("Mensaje vacío, ignoro.\n")
                    continue
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                stored_msg = f"[{timestamp}] {msg}"
                if target not in self.private_messages:
                    self.private_messages[target] = {}
                if self.session_name not in self.private_messages[target]:
                    self.private_messages[target][self.session_name] = []
                self.private_messages[target][self.session_name].append(stored_msg)
                self.save_private()
                if target in self.online_users:
                    self.send(f"Mensaje privado enviado a {target}.\n")
                else:
                    self.send(f"{target} no está presente. Mensaje guardado para cuando se conecte.\n")
            else:
                self.send("Comando desconocido. Revisa la ayuda implícita con los comandos.\n")
        self.send("Saliendo del modo Chat/Foro.\n")
    # --- Tablero de anuncios --- 
    def load_boards(self):
        try:
            with open(self.boards_file, 'r', encoding='utf-8') as f:
                self.boards = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.boards = {"General": [], "LoRa": [], "Off-Topic": []}

    def save_boards(self):
        try:
            with open(self.boards_file, 'w', encoding='utf-8') as f:
                json.dump(self.boards, f, ensure_ascii=False, indent=2)
        except Exception:
            pass 
    def bulletin_system(self):
        self.send("=== Tablón de Anuncios ===\nCategorías: General, LoRa, Off-Topic\n")
        self.send("Comandos: list (categorías), read <cat>, post <cat> <msg>, salir\n> ")
        while True:
            line = self.read_line_blocking()
            if not line:
                continue
            cmd = line.strip().lower()
            if cmd == "salir":
                break
            elif cmd == "list":
                self.send(f"Categorías disponibles: {', '.join(self.boards.keys())}\n")
            elif cmd.startswith("read "):
                cat = cmd[5:].strip().title()
                if cat in self.boards:
                    posts = self.boards[cat][-5:]  # Últimos 5
                    self.send(f"Tablón '{cat}' (últimos 5):\n---\n")
                    for post in posts:
                        self.send(f"[{post['timestamp']}] {post['user']}: {post['msg']}\n")
                    self.send("---\n")
                else:
                    self.send("Categoría no existe.\n")
            elif cmd.startswith("post "):
                parts = cmd[5:].split(maxsplit=1)
                if len(parts) == 2:
                    cat, msg = parts[0].strip().title(), parts[1].strip()
                    if cat in self.boards and msg:
                        ts = time.strftime("%Y-%m-%d %H:%M:%S")
                        self.boards[cat].append({"user": self.session_name, "msg": msg, "timestamp": ts})
                        self.save_boards()
                        self.send("Post enviado.\n")
                    else:
                        self.send("Categoría inválida o mensaje vacío.\n")
                else:
                    self.send("Uso: post <cat> <msg>\n")
            else:
                self.send("Comando desconocido.\n")
        self.send("Saliendo del tablón.\n")    
    # --- Juego Trivia con LLM ---
    def trivia_game(self):
        self.send("=== Trivia Tech ===\nResponde preguntas generadas por LLM. ¡Acumula puntos!\n'salir' para parar.\n")
        models, err = self.get_llm_models()
        if err or not models:
            self.send("Error en LLM. Juego cancelado.\n")
            return
        model = models[0]  # Usa el primero
        self.score = 0
        while True:
            prompt = "Genera una pregunta trivia simple sobre tecnología/LoRa, con 4 opciones (A,B,C,D) y la respuesta correcta al final (ej. 'Respuesta: B'). Mantén corto."
            q_out = self.call_llm(model, prompt)
            self.send(f"Pregunta:\n{q_out}\nTu respuesta (A/B/C/D): ")
            ans = self.read_line_blocking().strip().upper()
            if ans.lower() == 'salir':
                break
            check_prompt = f"Pregunta: {q_out}\nRespuesta usuario: {ans}\n¿Es correcta? Responde solo 'Sí' o 'No'."
            check = self.call_llm(model, check_prompt).strip().lower()
            if 'sí' in check or 'si' in check:
                self.score += 1
                self.send("¡Correcto! +1 punto.\n")
            else:
                self.send("Incorrecto. Sigue intentándolo.\n")
            self.send(f"Puntuación: {self.score}\n")
        self.send(f"¡Fin del juego! Puntuación final: {self.score}\n")    
    # --- Calendario ---    
    def calendar_system(self):
        self.send("=== 📅 Calendario ===\n")
        # Configurar calendario con domingo como primer día (firstweekday=7)
        cal = calendar.TextCalendar(firstweekday=7)
        # Obtener mes actual
        now = datetime.now()
        year, month = now.year, now.month
        # Generar calendario del mes actual
        month_cal = cal.formatmonth(year, month, w=2, l=1)  # w=2 ancho día, l=1 líneas
        # Reemplazar headers en inglés por español abreviado (D L M M J V S)
        spanish_days = " D  L  M  M  J  V  S"
        month_cal = month_cal.replace("Mo Tu We Th Fr Sa Su", spanish_days)
        month_cal = month_cal.replace("Mo", " L").replace("Tu", " M").replace("We", " M").replace("Th", " J").replace("Fr", " V").replace("Sa", " S").replace("Su", " D")
        # Nombres de meses en español (simple mapeo)
        months_es = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
                     7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}
        month_name = months_es.get(month, f"Mes {month}")
        #self.send(f"{month_name} {year}\n")
        self.send(month_cal)
        self.send(f"\nMes actual: {month_name} {year}\n")
        self.send("Ingresa año y mes (ej: 2025 12) para ver otro, o 'salir':\n> ")
        while True:
            line = self.read_line_blocking()
            if not line:
                continue
            cmd = line.strip().lower()
            if cmd == "salir":
                break
            parts = line.strip().split()
            if len(parts) == 2:
                try:
                    y, m = int(parts[0]), int(parts[1])
                    if 1 <= m <= 12:
                        other_cal = cal.formatmonth(y, m, w=2, l=1)
                        # Aplicar headers españoles
                        other_cal = other_cal.replace("Mo Tu We Th Fr Sa Su", spanish_days)
                        other_cal = other_cal.replace("Mo", " L").replace("Tu", " M").replace("We", " M").replace("Th", " J").replace("Fr", " V").replace("Sa", " S").replace("Su", " D")
                        other_month = months_es.get(m, f"Mes {m}")
                        #self.send(f"{other_month} {y}\n")
                        self.send(other_cal)
                    else:
                        self.send("Mes inválido (1-12).\n")
                except ValueError:
                    self.send("Formato inválido. Usa: año mes (ej: 2025 12)\n")
            self.send("Ingresa año y mes o 'salir':\n> ")
        self.send("Saliendo del calendario.\n")
    # --- Tasas de cambio ---
    def exchange_rates_system(self):
        self.send("=== 💱 Tasas de Cambio ===\n")
        self.send("Ingresa el país (ej: México, España, USA, Japón):\n> ")
        country_input = self.read_line_blocking().strip()
        if not country_input:
            self.send("País no ingresado.\n")
            return

        # Mapeo de países comunes a códigos de moneda base (ISO 4217)
        country_to_currency = {
            "México": "MXN", "Mexico": "MXN", "MX": "MXN",
            "Cuba":"CUP",
            "Estados Unidos": "USD", "USA": "USD", "United States": "USD", "US": "USD",
            "España": "EUR", "Spain": "EUR", "ES": "EUR",
            "Alemania": "EUR", "Germany": "EUR", "DE": "EUR",
            "Francia": "EUR", "France": "EUR", "FR": "EUR",
            "Italia": "IT", "Italy": "EUR",
            "Reino Unido": "GBP", "UK": "GBP", "United Kingdom": "GBP", "GB": "GBP",
            "Japón": "JPY", "Japan": "JPY", "JP": "JPY",
            "Argentina": "ARS", "AR": "ARS",
            "Brasil": "BRL", "Brazil": "BRL", "BR": "BRL",
            "Chile": "CLP", "CL": "CLP",
            "Colombia": "COP", "CO": "COP",
            "Perú": "PEN", "Peru": "PEN", "PE": "PEN",
            "Venezuela": "VES", "VE": "VES",
            "Canadá": "CAD", "Canada": "CAD", "CA": "CAD",
            "Australia": "AUD", "AU": "AUD",
            "China": "CNY", "CH": "CNY"
        }
        base_currency = country_to_currency.get(country_input.title(), None)
        if not base_currency:
            self.send(f"País '{country_input}' no reconocido. Moneda base no disponible.\n")
            self.send("Países disponibles: México, USA, España, UK, Japón, etc.\n")
            return

        self.send(f"Moneda base para {country_input}: {base_currency}\n")
        self.send("Obteniendo tasas... (usando API gratuita)\n")

        # Monedas fiat objetivo
        fiat_targets = {"USD": "Dólar EE.UU.", "EUR": "Euro", "JPY": "Yen Japonés", "GBP": "Libra Esterlina"}

        try:
            # Fetch de exchangerate-api.com (gratuito, sin clave para uso básico)
            url = f"https://api.exchangerate-api.com/v4/latest/{base_currency}"
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                rates = data.get('rates', {})

            if not rates:
                self.send("Error al obtener tasas fiat.\n")
                return

            self.send("Tasas de cambio (1 {base} ≈):\n".format(base=base_currency))
            for code, name in fiat_targets.items():
                rate = rates.get(code, 0)
                if rate > 0:
                    self.send(f"{name} ({code}): {rate:.4f}\n")
                else:
                    self.send(f"{name} ({code}): No disponible\n")

        except Exception as e:
            self.send(f"Error en tasas fiat: {e}\n")
            return

        # Opcional: Criptomonedas
        """
        self.send("\n¿Mostrar tasas a criptos (BTC, XMR, DASH, XRP)? (s/n):\n> ")
        crypto_choice = self.read_line_blocking().strip().lower()
        if crypto_choice in ('s', 'si', 'y', 'yes'):
            self.send("Obteniendo tasas a criptos (usando CoinGecko API gratuita)...\n")
            crypto_targets = {
                "bitcoin": "BTC - Bitcoin",
                "monero": "XMR - Monero",
                "dash": "DASH - Dash",
                "ripple": "XRP - Ripple"
            }

            try:
                # Fetch de CoinGecko para precios en USD, luego convertir
                # Primero, obtener precio de base en USD si no es USD
                base_to_usd = 1.0 if base_currency == "USD" else rates.get("USD", 1.0)
                usd_to_base = 1 / base_to_usd if base_to_base > 0 else 1.0

                # IDs de CoinGecko para criptos
                crypto_ids = "bitcoin,monero,dash,ripple"
                url_crypto = f"https://api.coingecko.com/api/v3/simple/price?ids={crypto_ids}&vs_currencies=usd"
                with urllib.request.urlopen(url_crypto, timeout=10) as response:
                    crypto_data = json.loads(response.read().decode('utf-8'))

                self.send("Tasas de cambio a criptos (1 {base} ≈):\n".format(base=base_currency))
                for id_, name in crypto_targets.items():
                    usd_price = crypto_data.get(id_, {}).get('usd', 0)
                    if usd_price > 0:
                        # crypto por base: (usd_price / base_to_usd)
                        crypto_per_base = usd_price / base_to_usd
                        self.send(f"{name}: {crypto_per_base:.8f}\n")
                    else:
                        self.send(f"{name}: No disponible\n")

            except Exception as e:
                self.send(f"Error en tasas cripto: {e}\n")
                return
        """
        self.send("\nSaliendo de Tasas de Cambio.\n")
    # --- bucle principal ---
    def _reader_loop(self):
        while True:
            try:
                if not self.session_active:
                    line = self.read_line_blocking(timeout=1)  # Polling ligero
                    if line:
                        self.session_active = True
                        self.send("\n>>> Conexión aceptada.\n")
                        #self.send(MENU_TEXT) # mostrar el menu directamente
                        self.send("Nombre de usuario:\n> ")
                        name = self.read_line_blocking(timeout=30)
                        if name:
                            self.session_name = name.strip() or "Anon"
                        else:
                            self.session_name = "Anon"
                        self.online_users.add(self.session_name)
                        self.send(f"Bienvenido a LoRa BBS Gateway v0.1, {self.session_name}!\n")
                        # Mostrar privados pendientes al conectar
                        if self.session_name in self.private_messages and self.private_messages[self.session_name]:
                            self.send("Tienes mensajes privados pendientes:\n---\n")
                            for sender, msg_list in list(self.private_messages[self.session_name].items()):
                                for msg in msg_list:
                                    self.send(f"{sender}: {msg}\n")
                            del self.private_messages[self.session_name]
                            self.save_private()
                            self.send("---\n(Mensajes leídos y eliminados.)\n")
                        self.send(MENU_TEXT)
                    continue

                cmd = self.read_line_blocking()
                if not cmd:
                    continue
                cmd = cmd.strip()
                if cmd.lower() in ("q", "quit", "exit", "disconnect"):
                    self.online_users.discard(self.session_name)
                    self.send("Desconectando sesión...\n")
                    self.ser.flush()
                    self.session_active = False
                    continue

                if cmd == "1":
                    self.send("Término para buscar (DuckDuckGo):\n> ")
                    q = self.read_line_blocking(timeout=30)
                    if q:
                        out = self.search_duckduckgo(q)
                        self.send(out)
                    else:
                        self.send("Sin entrada.\n")
                    self.send(MENU_TEXT)
                    continue

                if cmd == "2":
                    self.send("Término para Wikipedia:\n> ")
                    q = self.read_line_blocking(timeout=30)
                    if q:
                        out = self.search_wikipedia(q)
                        self.send(out)
                    else:
                        self.send("Sin entrada.\n")
                    self.send(MENU_TEXT)
                    continue

                if cmd == "3":
                    self.send("Ciudad para el clima:\n> ")
                    q = self.read_line_blocking(timeout=30)
                    if q:
                        out = self.get_weather(q)
                        self.send(out)
                    else:
                        self.send("Sin entrada.\n")
                    self.send(MENU_TEXT)
                    continue

                if cmd == "4":
                    self.send("País para ver noticias:\n>")
                    q = self.read_line_blocking(timeout=30)
                    if q:
                        out = self.get_news_google_rss(q)
                        self.send(out)
                    else:
                        self.send("Sin entrada.\n")
                    self.send(MENU_TEXT)
                    continue

                if cmd == "5":
                    models, err = self.get_llm_models()
                    if err:
                        self.send(err)
                        self.send(MENU_TEXT)
                        continue
                    if not models:
                        self.send("No hay modelos disponibles.\n")
                        self.send(MENU_TEXT)
                        continue
                    self.send("Modelos disponibles:\n")
                    for i, m in enumerate(models):
                        self.send(f"{i+1}) {m}\n")
                    self.send("Selecciona modelo (número o nombre):\n> ")
                    choice = self.read_line_blocking(timeout=40)
                    if not choice:
                        self.send("Sin selección.\n")
                        self.send(MENU_TEXT)
                        continue
                    if choice.isdigit() and 1 <= int(choice) <= len(models):
                        model = models[int(choice)-1]
                    else:
                        model = choice.strip()
                    self.send(f"\nUsando modelo: {model}\n")
                    self.send("Comandos: 'modelos' para cambiar, 'salir'/'quit' para volver al menú\n")
                    while True:
                        self.send("Prompt:\n> ")
                        prompt = self.read_line_blocking(timeout=120)
                        if not prompt:
                            self.send("Tiempo agotado. Intenta de nuevo.\n")
                            continue
                        p_lower = prompt.lower().strip()
                        if p_lower in ("salir", "quit"):
                            self.send("Saliendo del modo LLM...\n")
                            break
                        if p_lower in ("modelos", "modelo", "cambiar"):
                            models, err = self.get_llm_models()
                            if err:
                                self.send(err)
                                continue
                            self.send("Modelos disponibles:\n")
                            for i, m in enumerate(models):
                                self.send(f"{i+1}) {m}\n")
                            self.send("Selecciona nuevo modelo:\n> ")
                            new_choice = self.read_line_blocking(timeout=40)
                            if new_choice:
                                if new_choice.isdigit() and 1 <= int(new_choice) <= len(models):
                                    model = models[int(new_choice)-1]
                                else:
                                    model = new_choice.strip()
                                self.send(f"Modelo cambiado a: {model}\n")
                            continue
                        out = self.call_llm(model, prompt)
                        self.send(out)
                        self.send("(Escribe otro prompt, 'modelos' para cambiar o 'salir'/'quit' para volver)\n")
                    self.send(MENU_TEXT)
                    continue
                if cmd == "6":
                    self.chat_system()
                    self.send(MENU_TEXT)
                    continue  
                if cmd == "7": 
                    self.bulletin_system();
                    self.send(MENU_TEXT); 
                    continue   
                if cmd == "8":
                    self.trivia_game()
                    self.send(MENU_TEXT)
                    continue
                if cmd == "9":
                    self.calendar_system()
                    self.send(MENU_TEXT)
                    continue
                if cmd == "10":
                    self.exchange_rates_system()
                    self.send(MENU_TEXT)
                    continue    
                if cmd == "0":
                    self.send("Hecho por Slam (2025)\n")
                    self.send("Github.com: https://github.com/aayes89\n")
                    self.send(MENU_TEXT)
                    continue
                self.send("Comando desconocido.\n")
                self.send(MENU_TEXT)
            except Exception as e:
                print(f"[ERROR en reader_loop] {e}")
                time.sleep(1)

def main():
    bbs = LoRaBBS(SERIAL_PORT, BAUDRATE)
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()