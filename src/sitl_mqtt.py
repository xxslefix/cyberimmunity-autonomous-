""" модуль отправки телеметрии в систему мониторинга
"""
from multiprocessing import Queue, Process
from queue import Empty
from time import sleep, time

from geopy import Point as GeoPoint
import paho.mqtt.client as mqtt

from src.config import CRITICALITY_STR, LOG_DEBUG, LOG_ERROR, LOG_INFO, \
    SITL_TELEMETRY_QUEUE_NAME, DEFAULT_LOG_LEVEL
from src.queues_dir import QueuesDirectory
from src.event_types import Event, ControlEvent


class TelemetrySender(Process):
    """ класс отправки телеметрии в систему мониторинга """
    MQTT_BROKER = "localhost"
    MQTT_PORT = 1883
    MQTT_TOPIC = "api/telemetry"
    TIMEOUT = 5

    log_prefix = "[SITL.MQTT]"
    event_source_name = SITL_TELEMETRY_QUEUE_NAME
    events_q_name = event_source_name

    def __init__(self, queues_dir: QueuesDirectory, client_id='', log_level = DEFAULT_LOG_LEVEL):
        super().__init__()

        self._queues_dir = queues_dir
        self._client_id = client_id

        # создаём очередь для сообщений на обработку
        self._events_q = Queue()
        self._events_q_name = TelemetrySender.events_q_name
        self._queues_dir.register(
            queue=self._events_q, name=self._events_q_name)

        self._quit = False
        # очередь управляющих команд (например, для остановки симуляции)
        self._control_q = Queue()

        self._mqttc = None
        self._published = False

        # инициализируем интервал обновления
        self._recalc_interval_sec = 0.5
        self.log_level = log_level

    def _log_message(self, criticality: int, message: str):
        """_log_message печатает сообщение заданного уровня критичности

        Args:
            criticality (int): уровень критичности
            message (str): текст сообщения
        """
        if criticality <= self.log_level:
            print(f"[{CRITICALITY_STR[criticality]}]{self.log_prefix} {message}")

    # The callback for when the client receives a CONNACK response from the server.
    def _on_connect(self, _, userdata, flags, reason_code):
        self._log_message(
            LOG_DEBUG, f"Connected with result code {reason_code}, other info: {userdata}, {flags}")
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        # client.subscribe("$SYS/#")

    def _on_log(self, _, __, ___, buf):
        if self.log_level > 2:
            print(f"{self.log_prefix} LOG >> {buf}")

    # The callback for when a PUBLISH message is received from the server.
    def _on_message(self, _, __, msg):
        print(msg.topic+" "+str(msg.payload))

    def _on_publish(self, _, __, ___):
        self._published = True

    def stop(self):
        """ запрос остановки работы """
        self._control_q.put(ControlEvent(operation='stop'))

    # проверка наличия новых управляющих команд
    def _check_control_q(self):
        try:
            request: ControlEvent = self._control_q.get_nowait()
            # print(f"{self.log_prefix} проверяем запрос {request}")
            if not isinstance(request, ControlEvent):
                return
            if request.operation == 'stop':
                # поступил запрос на остановку монитора, поднимаем "красный флаг"
                self._quit = True
        except Empty:
            # никаких команд не поступило, ну и ладно
            pass

    def _post_telemetry(self, event: Event):
        try:
            position: GeoPoint = event.parameters
            bearing = int(event.extra_parameters["bearing"])
            speed = int(event.extra_parameters["speed"])

            payload = f'id={self._client_id}&lat={int(position.latitude*(1E+7))}&' +\
                f'lon={int(position.longitude*(1E+7))}&alt={int(position.altitude*100)}&' +\
                f'azimuth={bearing*(1E+7)}&dop={1.2}&sats={12}&speed={speed}'

            self._mqttc.publish(
                TelemetrySender.MQTT_TOPIC, payload, qos=1)
            start_time = time()

            while not self._published and time() - start_time < TelemetrySender.TIMEOUT:
                sleep(0.1)

            if self._published:
                self._log_message(
                    LOG_DEBUG, f"отправлена телеметрия: {payload}")
            else:
                self._log_message(LOG_ERROR, "таймаут отправки телеметрии")

        except Exception as e:
            self._log_message(LOG_ERROR, f"ошибка отправки телеметрии: {e}")

    def _check_events_q(self):
        while True:
            try:
                event: Event = self._events_q.get_nowait()
                # print(f"{self.log_prefix} обрабатываем событие: {event}")
                if not isinstance(event, Event):
                    return
                if event.operation == 'post_telemetry':
                    self._post_telemetry(event)
            except Empty:
                # все входящие события обработаны
                break

    def run(self):
        self._log_message(LOG_INFO, "старт клиента телеметрии")

        mqttc = mqtt.Client(client_id=self._client_id)
        mqttc.connect(TelemetrySender.MQTT_BROKER,
                      TelemetrySender.MQTT_PORT, 60)

        mqttc.on_connect = self._on_connect

        mqttc.on_message = self._on_message

        self._published = False

        mqttc.on_publish = self._on_publish

        mqttc.on_log = self._on_log

        self._mqttc = mqttc

        self._mqttc.loop_start()
        self._log_message(
            LOG_INFO, "клиент отправки телеметрии создан и запущен")

        while self._quit is False:
            self._check_events_q()
            self._check_control_q()
            sleep(self._recalc_interval_sec)

        self._mqttc.loop_stop()
        self._mqttc.disconnect()
