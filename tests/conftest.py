""" вспомогательный код для модульных тестов """
import pytest
from src.event_types import Event

from src.config import COMMUNICATION_GATEWAY_QUEUE_NAME, \
    LOG_DEBUG, LOG_INFO
from src.config import CONTROL_SYSTEM_QUEUE_NAME
from src.queues_dir import QueuesDirectory
from src.security_monitory import BaseSecurityMonitor
from src.security_policy_type import SecurityPolicy


@pytest.fixture(scope="module")
def queues_dir() -> QueuesDirectory:
    """ каталог очередей """
    return QueuesDirectory()


class SecurityMonitor(BaseSecurityMonitor):
    """ класс монитора безопасности """

    def __init__(self, queues_dir):
        super().__init__(queues_dir)
        self._init_set_security_policies()

    def _init_set_security_policies(self):
        """ инициализация политик безопасности """
        default_policies = [
            SecurityPolicy(
                source=COMMUNICATION_GATEWAY_QUEUE_NAME,
                destination=CONTROL_SYSTEM_QUEUE_NAME,
                operation='set_mission')
        ]
        self.set_security_policies(policies=default_policies)

    def set_security_policies(self, policies):
        """ установка новых политик безопасности """
        self._security_policies = policies
        self._log_message(
            LOG_INFO, f"изменение политик безопасности: {policies}")

    def _check_event(self, event: Event):
        """ проверка входящих событий """
        self._log_message(
            LOG_DEBUG, f"проверка события {event}, по умолчанию выполнение запрещено")

        authorized = False
        request = SecurityPolicy(
            source=event.source,
            destination=event.destination,
            operation=event.operation)

        if request in self._security_policies:
            self._log_message(
                LOG_DEBUG, "событие разрешено политиками, выполняем")
            authorized = True

        return authorized

@pytest.fixture
def security_monitor(queues_dir) -> SecurityMonitor:
    """ монитор безопасности """
    sm = SecurityMonitor(queues_dir=queues_dir)
    sm.log_level = LOG_DEBUG
    assert sm is not None
    return sm
