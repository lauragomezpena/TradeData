import json
import random
import re
import string
import time
from datetime import datetime
from websocket import create_connection, WebSocketConnectionClosedException
import subprocess

# Configuración de Kafka
BOOTSTRAP_SERVERS = [
    "b-1-public.testkafka3.l7t9mi.c2.kafka.eu-south-2.amazonaws.com:9198",
    "b-2-public.testkafka3.l7t9mi.c2.kafka.eu-south-2.amazonaws.com:9198"
]
BOOTSTRAP_STRING = ",".join(BOOTSTRAP_SERVERS)
TOPIC = "imat3b_ADA"

def generate_session():
    return "qs_" + ''.join(random.choices(string.ascii_lowercase, k=12))

def prepend_header(content):
    return f"~m~{len(content)}~m~{content}"

def construct_message(func, param_list):
    return json.dumps({"m": func, "p": param_list}, separators=(",", ":"))

def create_message(func, param_list):
    return prepend_header(construct_message(func, param_list))

def send_message(ws, func, args):
    try:
        ws.send(create_message(func, args))
    except WebSocketConnectionClosedException:
        print("Conexión cerrada mientras se intentaba enviar un mensaje.")
        reconnect(ws)

def send_ping(ws):
    try:
        ws.send("~h~0")
    except Exception as e:
        print(f"Error enviando ping: {e}")

def process_data(data):
    price = data.get("lp")
    
    # Solo continuar si hay precio (es decir, price no es None)
    if price is None:
        return

    change = data.get("ch", "No disponible")
    change_percentage = data.get("chp", "No disponible")
    volume = data.get("volume", "No disponible")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"[{timestamp}] Precio: {price}, Cambio: {change}, % Cambio: {change_percentage}, Volumen: {volume}")

    # Crear mensaje JSON para Kafka
    message_dict = {
        "price": price,
        "change": change,
        "change_percentage": change_percentage,
        "volume": volume,
        "timestamp": timestamp
    }
    json_message = json.dumps(message_dict)

    # Construir el comando Kafka
    kafka_cmd = f'''echo '{json_message}' | /home/ec2-user/kafka_2.13-3.6.0/bin/kafka-console-producer.sh \
--bootstrap-server {BOOTSTRAP_STRING} \
--producer.config ./config/client.properties \
--topic {TOPIC}'''

    # Ejecutar el comando
    try:
        result = subprocess.run(kafka_cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print("Error al enviar a Kafka:", result.stderr)
    except Exception as e:
        print("Excepción al ejecutar Kafka producer:", e)

def reconnect(symbol_id):
    print("Intentando reconectar...")
    time.sleep(5)
    start_socket(symbol_id)

def start_socket(symbol_id):
    session = generate_session()
    url = "wss://data.tradingview.com/socket.io/websocket"
    headers = json.dumps({"Origin": "https://data.tradingview.com"})

    try:
        ws = create_connection(url, headers=headers)
        print(f"Conectado a {url}")

        send_message(ws, "quote_create_session", [session])
        send_message(ws, "quote_set_fields", [session, "lp", "ch", "chp", "volume"])
        send_message(ws, "quote_add_symbols", [session, symbol_id])

        while True:
            try:
                result = ws.recv()
                if result.startswith("~m~"):
                    data_match = re.search(r"\{.*\}", result)
                    if data_match:
                        message = json.loads(data_match.group(0))
                        if message["m"] == "qsd":
                            process_data(message["p"][1]["v"])
                elif result.startswith("~h~"):
                    send_ping(ws)

            except WebSocketConnectionClosedException:
                print("Conexión cerrada inesperadamente.")
                reconnect(symbol_id)
                break
            except Exception as e:
                print(f"Error procesando mensaje: {e}")
                continue

    except Exception as e:
        print(f"Error al conectar: {e}. Reconectando en 5 segundos...")
        reconnect(symbol_id)

if __name__ == "__main__":
    symbol_id = "BINANCE:ADAUSD"
    start_socket(symbol_id)
