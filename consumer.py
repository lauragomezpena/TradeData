import subprocess
import json
import time
import boto3
import threading
from botocore.config import Config

# Configuración de Kafka
KAFKA_BIN = "/home/ec2-user/kafka_2.13-3.6.0"
BOOTSTRAP_SERVERS = "b-1-public.testkafka3.l7t9mi.c2.kafka.eu-south-2.amazonaws.com:9198,b-2-public.testkafka3.l7t9mi.c2.kafka.eu-south-2.amazonaws.com:9198"
TOPIC = "imat3b_ADA"
CONFIG_FILE = f"{KAFKA_BIN}/config/client.properties"

# Configuración de Timestream
DATABASE_NAME = "CryptoIcaiDatabase"
TABLE_NAME = "CryptoMonedas"

class TimestreamWriter:

    def __init__(self):
        self.config = Config(retries={"max_attempts": 10})
        self.client = boto3.client(
            "timestream-write", 
            region_name="eu-west-1",  # La base de datos está en esta región
            config=self.config
        )

    def write_record(self, price, timestamp):
        """Escribe un registro en Amazon Timestream."""
        
        dimensions = [{"Name": "ICAI", "Value": "Crypto"}]  # Puedes cambiar "BTC" por otra criptomoneda
        record = {
            "MeasureName": "ADA",  # Cambiar si es otra criptomoneda
            "Dimensions": dimensions,
            "MeasureValue": str(price),
            "MeasureValueType": "DOUBLE",
            "Time": str(int(time.mktime(time.strptime(timestamp, "%Y-%m-%d %H:%M:%S"))) * 1000)
        }

        try:
            response = self.client.write_records(
                DatabaseName=DATABASE_NAME,
                TableName=TABLE_NAME,
                Records=[record]
            )

            print(f"[Timestream] Registro almacenado con éxito: {record} | Status: {response['ResponseMetadata']['HTTPStatusCode']}")

        except self.client.exceptions.RejectedRecordsException as err:
            print(f"[Timestream] Registro rechazado: {err}")

        except Exception as err:
            print(f"[Timestream] Error al escribir en Timestream: {err}")

def log_errors(process):
    """Función en un hilo separado para manejar errores de Kafka sin bloquear la ejecución."""

    for error_line in iter(process.stderr.readline, ''):
        print(f"[Kafka-Error] {error_line.strip()}")

def consume_messages():
    """Ejecuta el consumidor de Kafka y almacena los datos en Amazon Timestream."""

    writer = TimestreamWriter()

    kafka_cmd = [
        f"{KAFKA_BIN}/bin/kafka-console-consumer.sh",
        "--bootstrap-server", BOOTSTRAP_SERVERS,
        "--consumer.config", CONFIG_FILE,
        "--topic", TOPIC,
        "--property", "print.value=true",
        "--property", "print.partition=true",
        "--property", "print.offset=true",
        "--property", "print.timestamp=true",
        "--from-beginning"
    ]

    try:
        process = subprocess.Popen(kafka_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        print(f"[Kafka] Escuchando mensajes en el topic '{TOPIC}'...\n")

        # Iniciar un hilo para capturar errores sin bloquear la ejecución
        error_thread = threading.Thread(target=log_errors, args=(process,), daemon=True)
        error_thread.start()

        for line in iter(process.stdout.readline, ''):
            print(f"[DEBUG] Mensaje recibido de Kafka: {line.strip()}")  # Ver qué llega realmente
            line = line.strip()

            if not line:
                continue

            try:
                # Extraer solo la parte JSON del mensaje
                json_start = line.find("{")

                if json_start == -1:
                    print(f"[Error] No se encontró JSON en: {line}")
                    continue

                json_data = line[json_start:]
                data = json.loads(json_data)  # Convertir a JSON

                # Validar si 'price' es "No disponible" y asignar valor predeterminado
                price = data.get("price", "No disponible")
                if price == "No disponible":
                    print(f"[Warning] Precio no disponible.")
                    continue  # O asignar un valor predeterminado (ejemplo: price = 0)

                try:
                    price = float(price)  # Intentar convertir a flotante
                except ValueError:
                    print(f"[Error] No se pudo convertir el precio '{price}' a float.")
                    continue  # O asignar un valor predeterminado

                timestamp = data.get("timestamp", "")

                print(f"[Kafka] Mensaje recibido: Precio={price}, Timestamp={timestamp}")

                # Enviar a Timestream
                writer.write_record(price, timestamp)

            except json.JSONDecodeError as e:
                print(f"[Error] JSON mal formado: {line} | Error: {e}")

            except Exception as e:
                print(f"[Error] No se pudo procesar el mensaje: {line} | Error: {e}")

    except KeyboardInterrupt:
        print("\n[Kafka] Consumidor detenido.")

    except Exception as e:
        print(f"[Error] Problema con el consumidor: {e}")

if __name__ == "__main__":
    consume_messages()
