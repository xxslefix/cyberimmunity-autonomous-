""" модуль управления грузовым отсеком """
from multiprocessing import Queue, Process
from queue import Empty

from time import sleep

from src.config import CARGO_BAY_QUEUE_NAME, CRITICALITY_STR, DEFAULT_LOG_LEVEL, \
    LOG_DEBUG, LOG_INFO
from src.queues_dir import QueuesDirectory
from src.event_types import Event, ControlEvent


class CargoBay(Process):
    """ класс управления грузовым отсеком """
    log_prefix = "[CARGO]"
    event_source_name = CARGO_BAY_QUEUE_NAME
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

        self._is_cargo_released = False
        self.log_level = log_level

        self._log_message(LOG_INFO, "создан компонент грузового отсека, отсек заблокирован")

    def _log_message(self, criticality: int, message: str):
        """_log_message печатает сообщение заданного уровня критичности

        Args:
            criticality (int): уровень критичности
            message (str): текст сообщения
        """
        if criticality <= self.log_level:
            print(f"[{CRITICALITY_STR[criticality]}]{self.log_prefix} {message}")

    def _check_control_q(self):
        """_check_control_q проверка наличия новых управляющих команд
        """
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

            if event.operation == 'release_cargo':
                self._log_message(LOG_INFO, "выгрузка")
                self._release_cargo()
            elif event.operation == 'lock_cargo':
                self._log_message(LOG_INFO, "заблокировать грузовой отсек")
                self._lock_cargo()

    def _release_cargo(self):
        self._is_cargo_released = True
        self._log_message(LOG_INFO, "груз оставлен")

    def _lock_cargo(self):
        self._is_cargo_released = False
        self._log_message(LOG_INFO, "грузовой отсек заблокирован")

    def stop(self):
        """stop запрос остановки работы блока
        """
        self._control_q.put(ControlEvent(operation='stop'))

    def run(self):
        self._log_message(LOG_INFO, "старт блока грузового отсека")

        while self._quit is False:
            sleep(self._recalc_interval_sec)
            self._check_events_q()
            self._check_control_q()
