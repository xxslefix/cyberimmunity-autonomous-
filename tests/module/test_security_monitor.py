""" тесты монитора безопасности """


from src.config import CARGO_BAY_QUEUE_NAME, COMMUNICATION_GATEWAY_QUEUE_NAME, \
    CONTROL_SYSTEM_QUEUE_NAME, SAFETY_BLOCK_QUEUE_NAME
from src.event_types import Event
from src.security_policy_type import SecurityPolicy


def test_security_policies(security_monitor):
    """ проверка политик безопасности """

    # шаг 1. Проверка примера политики безопасности
    event = Event(source=COMMUNICATION_GATEWAY_QUEUE_NAME,
                  destination=CONTROL_SYSTEM_QUEUE_NAME,
                  operation="set_mission",
                  parameters=None)

    authorized = security_monitor._check_event(             # pylint: disable=protected-access
        event=event)  # pylint: disable=protected-access

    assert authorized

    # шаг 2. Проверка допустимого по архитектуре, но не допустимого политиками запроса
    event = Event(source=CONTROL_SYSTEM_QUEUE_NAME,
                  destination=SAFETY_BLOCK_QUEUE_NAME,
                  operation="set_speed",
                  parameters=None)

    authorized = security_monitor._check_event(             # pylint: disable=protected-access
        event=event)  # pylint: disable=protected-access

    assert not authorized

    # шаг 3. Добавление новой политики безопасности и повторная проверка запроса
    policies = security_monitor._security_policies # pylint: disable=protected-access
    policies.append(             
        SecurityPolicy(
            source=CONTROL_SYSTEM_QUEUE_NAME,
            destination=SAFETY_BLOCK_QUEUE_NAME,
            operation="set_speed"
        )
    )
    security_monitor.set_security_policies(policies=policies)

    authorized = security_monitor._check_event(             # pylint: disable=protected-access
        event=event)  # pylint: disable=protected-access

    assert authorized

    # шаг 4. Контрольная проверка неразрешённого запроса
    event = Event(source=COMMUNICATION_GATEWAY_QUEUE_NAME,
                  destination=CARGO_BAY_QUEUE_NAME,
                  operation="release_cargo",
                  parameters=None)

    authorized = security_monitor._check_event(             # pylint: disable=protected-access
        event=event)  # pylint: disable=protected-access

    assert authorized is False
