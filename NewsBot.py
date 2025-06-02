import feedparser
import smtplib
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import requests
import re
import time
import os

# Configuración
GMAIL_USUARIO = os.getenv("GMAIL_USUARIO")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
DESTINATARIOS = [GMAIL_USUARIO]

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS", "").split(",")

# Palabras clave
PALABRAS_CLAVE = [
    "incendio", "fuego", "explosión", "evacuación", "protección civil",
    "accidente", "choque", "volcadura", "colisión", "paralización",
    "paro", "desalojo", "emergencia", "alerta", "muertos", "heridos",
    "planta", "fábrica", "empresa", "siniestro", "riesgo", "crisis",
    "Volkswagen", "VW", "Daimay", "Ramos Arizpe", "proveedor", "automotriz",
    "Audi", "armadora", "ensambladora"
]

PALABRAS_EXCLUIDAS = [
    "deporte", "cultural", "entrevista", "opinión", "gastronómico", "espectáculo"
]

CLAVES_VW = [
    "Volkswagen", "VW", "Daimay", "Ramos Arizpe", "proveedor",
    "automotriz", "Audi", "armadora", "ensambladora", "planta"
]

FUENTES_RSS = [
    ("El Siglo de Torreón", "https://www.elsiglodetorreon.com.mx/rss"),
    ("Reforma", "https://www.reforma.com/rss/portada.xml"),
    ("El Horizonte", "https://www.elhorizonte.mx/rss/portada.xml"),
    ("Google News", "https://news.google.com/rss/search?q=incendio+OR+accidente+OR+Volkswagen+OR+Audi+OR+planta+automotriz&hl=es-419&gl=MX&ceid=MX:es-419"),
    ("El Financiero", "https://www.elfinanciero.com.mx/rss/ultimas-noticias/"),
    ("AutoCosmos", "https://noticias.autocosmos.com.mx/rss"),
    ("Cluster Automotriz NL", "https://www.clusterautomotriz.com.mx/noticias?format=feed&type=rss"),
    ("Vanguardia MX", "https://vanguardia.com.mx/rss/"),
    ("Milenio Laguna", "https://www.milenio.com/rss/feed.xml?section=laguna")
]

URLS_DIRECTAS = [
    "https://www.reforma.com/reportan-perdida-total-en-planta-de-daimay-tras-incendio/ar3003242"
]

def contiene_palabra(lista, texto):
    return any(re.search(p, texto, re.IGNORECASE) for p in lista)

def clasificar_noticia(titulo, resumen):
    texto = f"{titulo} {resumen}"
    if contiene_palabra(CLAVES_VW, texto):
        return "vw"
    return "general"

def obtener_noticias():
    noticias_vw = []
    noticias_generales = []
    hace_un_mes = datetime.now() - timedelta(days=30)

    for fuente_nombre, url in FUENTES_RSS:
        print(f"Revisando {fuente_nombre}...")
        feed = feedparser.parse(url)

        for entrada in feed.entries[:30]:
            titulo = entrada.title
            resumen = entrada.get("summary", "")
            fecha_publicacion = entrada.get("published_parsed")

            if fecha_publicacion:
                fecha = datetime.fromtimestamp(time.mktime(fecha_publicacion))
                if fecha < hace_un_mes:
                    continue
            else:
                fecha = datetime.now()

            enlace = entrada.link
            texto_completo = f"{titulo} {resumen}"

            if contiene_palabra(PALABRAS_CLAVE, texto_completo) and not contiene_palabra(PALABRAS_EXCLUIDAS, texto_completo):
                noticia_formateada = f"📰 {titulo}\n📅 {fecha.strftime('%Y-%m-%d')}\n🔗 {enlace}"
                if clasificar_noticia(titulo, resumen) == "vw":
                    noticias_vw.append(noticia_formateada)
                else:
                    noticias_generales.append(noticia_formateada)

    return noticias_generales, noticias_vw

def obtener_noticias_directas():
    noticias_generales = []
    noticias_vw = []

    for url in URLS_DIRECTAS:
        try:
            print(f"Revisando URL directa: {url}")
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            titulo = soup.title.string.strip() if soup.title else ""
            parrafos = [p.get_text(strip=True) for p in soup.find_all("p")]
            texto = " ".join(parrafos)

            texto_completo = f"{titulo} {texto}"
            if contiene_palabra(PALABRAS_CLAVE, texto_completo) and not contiene_palabra(PALABRAS_EXCLUIDAS, texto_completo):
                noticia_formateada = f"📰 {titulo}\n🔗 {url}"
                if contiene_palabra(CLAVES_VW, texto_completo):
                    noticias_vw.append(noticia_formateada)
                else:
                    noticias_generales.append(noticia_formateada)

        except Exception as e:
            print(f"Error al procesar {url}: {e}")

    return noticias_generales, noticias_vw

def enviar_correo(noticias):
    if not noticias:
        print("No hay noticias para enviar por correo.")
        return

    cuerpo = "\n\n".join(noticias)
    asunto = f"Noticias relevantes - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    msg = MIMEText(cuerpo, "plain", "utf-8")
    msg["Subject"] = asunto
    msg["From"] = GMAIL_USUARIO
    msg["To"] = ", ".join(DESTINATARIOS)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USUARIO, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print("Correo enviado correctamente.")
    except Exception as e:
        print("Error al enviar el correo:", e)

def enviar_telegram(noticias):
    if not noticias:
        print("No hay noticias para enviar por Telegram.")
        return

    def dividir_mensaje(texto, max_len=4096):
        partes = []
        while len(texto) > max_len:
            corte = texto.rfind("\n", 0, max_len)
            if corte == -1:
                corte = max_len
            partes.append(texto[:corte])
            texto = texto[corte:]
        partes.append(texto)
        return partes

    mensaje = "\n\n".join(noticias)
    partes = dividir_mensaje(mensaje)

    for chat_id in TELEGRAM_CHAT_IDS:
        for parte in partes:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = {"chat_id": chat_id, "text": parte}
            try:
                response = requests.post(url, data=data)
                if response.status_code == 200:
                    print(f"Parte enviada a {chat_id}")
                else:
                    print(f"Error al enviar a {chat_id}: {response.text}")
            except Exception as e:
                print(f"Error al enviar a {chat_id}: {e}")

def enviar_mensajes(noticias_generales, noticias_vw):
    if not noticias_generales and not noticias_vw:
        print("No hay noticias para enviar.")
        return

    ahora = datetime.now().strftime('%Y-%m-%d %H:%M')
    saludo = f"Buenos días Eduardo Loranca,\nEstas son tus noticias del día de hoy ({ahora}):\n"

    cuerpo = [saludo]
    if noticias_vw:
        cuerpo.append("🚗 Noticias VW y sector automotriz:\n" + "\n\n".join(noticias_vw))
    if noticias_generales:
        cuerpo.append("🔥 Noticias relevantes:\n" + "\n\n".join(noticias_generales))

    enviar_correo(cuerpo)
    enviar_telegram(cuerpo)

if __name__ == "__main__":
    print("Ejecutando bot de noticias...")
    noticias_generales_rss, noticias_vw_rss = obtener_noticias()
    noticias_generales_directas, noticias_vw_directas = obtener_noticias_directas()

    todas_generales = noticias_generales_rss + noticias_generales_directas
    todas_vw = noticias_vw_rss + noticias_vw_directas

    enviar_mensajes(todas_generales, todas_vw)
