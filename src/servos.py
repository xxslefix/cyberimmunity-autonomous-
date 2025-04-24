""" модуль управления приводами """
from multiprocessing import Queue, Process
from queue import Empty

from time import sleep

from src.config import CRITICALITY_STR, SERVOS_QUEUE_NAME, SITL_QUEUE_NAME, DEFAULT_LOG_LEVEL, \
    LOG_ERROR, LOG_DEBUG, LOG_INFO
from src.queues_dir import QueuesDirectory
from src.event_types import Event, ControlEvent


class Servos(Process):
    """ класс управления приводами """
    log_prefix = "[SERVOS]"
    event_source_name = SERVOS_QUEUE_NAME
    events_q_name = event_source_name    

    def __init__(self, queues_dir: QueuesDirectory, log_level = DEFAULT_LOG_LEVEL):
        # вызываем конструктор базового класса
        super().__init__()

        self._queues_dir = queues_dir

        # создаём очередь для сообщений на обработку
        self._events_q = Queue()
        self._events_q_name = self.event_source_name

        # регистрируем очередь в каталоге
        self._queues_dir.register(
            queue=self._events_q, name=self._events_q_name)

        # инициализируем интервал обновления
        self._recalc_interval_sec = 0.5

        self._quit = False
        # очередь управляющих команд (например, для остановки работы модуля)
        self._control_q = Queue()

        self.log_level = log_level
        self._speed: int = 0
        self._direction: float = 0.0

        self._log_message(LOG_INFO, "создан компонент сервоприводов")

    def _log_message(self, criticality: int, message: str):
        """_log_message печатает сообщение заданного уровня критичности

        Args:
            criticality (int): уровень критичности
            message (str): текст сообщения
        """
        if criticality <= self.log_level:
            print(f"[{CRITICALITY_STR[criticality]}]{self.log_prefix} {message}")

    # проверка наличия новых управляющих команд

    def _check_control_q(self):
        try:
            request: ControlEvent = self._control_q.get_nowait()
            self._log_message(LOG_DEBUG, f"проверяем запрос {request}")
            if isinstance(request, ControlEvent) and request.operation == 'stop':
                # поступил запрос на остановку монитора, поднимаем "красный флаг"
                self._quit = True
        except Empty:
            # никаких команд не поступило, ну и ладно
            pass

    def _check_events_q(self):
        """_check_events_q в цикле проверим все входящие сообщения, 
        выход из цикла по условию отсутствия новых сообщений
        """

        while True:
            try:
                event: Event = self._events_q.get_nowait()
            except Empty:
                # в очереди не команд на обработку,
                # выходим из цикла проверки
                break
            if not isinstance(event, Event):
                # событие неправильного типа, пропускаем
                continue

            self._log_message(LOG_DEBUG, f"получен запрос {event}")

            if event.operation == 'set_speed':
                self._log_message(
                    LOG_DEBUG, f"устанавливаем новую скорость {event.parameters}")
                self._set_speed(event.parameters)
            elif event.operation == 'set_direction':
                self._log_message(
                    LOG_DEBUG, f"устанавливаем новое направление {event.parameters}")
                self._set_direction(event.parameters)

    def _set_speed(self, speed):
        self._speed = speed
        self._send_new_speed_to_sitl()

    def _set_direction(self, direction):
        self._direction = direction
        self._send_new_direction_to_sitl()

    def _send_new_speed_to_sitl(self):
        sitl_q_name = SITL_QUEUE_NAME
        event = Event(source=Servos.event_source_name,
                      destination=sitl_q_name,
                      operation="set_speed", parameters=self._speed
                      )
        sitl_q: Queue = self._queues_dir.get_queue(sitl_q_name)
        try:
            sitl_q.put(event)
            self._log_message(
                LOG_DEBUG, f"новая скорость {self._speed} отправлена в симулятор")
        except Exception as e:
            self._log_message(
                LOG_ERROR, f"ошибка отправки скорости в симулятор: {e}")

    def _send_new_direction_to_sitl(self):
        sitl_q_name = SITL_QUEUE_NAME
        event = Event(source=Servos.event_source_name,
                      destination=sitl_q_name,
                      operation="set_direction", parameters=self._direction
                      )
        sitl_q: Queue = self._queues_dir.get_queue(sitl_q_name)
        try:
            sitl_q.put(event)
            self._log_message(
                LOG_DEBUG, f"направление {self._direction} отправлено в симулятор")
        except Exception as e:
            self._log_message(
                LOG_ERROR, f"ошибка отправки направления в симулятор: {e}")

    def stop(self):
        self._control_q.put(ControlEvent(operation='stop'))

    def run(self):
        self._log_message(LOG_INFO, "старт блока приводов")

        while self._quit is False:
            sleep(self._recalc_interval_sec)
            try:
                self._check_events_q()
                self._check_control_q()
            except Exception as e:
                self._log_message(LOG_ERROR, f"ошибка обработки команд: {e}")
