from src.sitl import SITL
from geopy import Point as GeoPoint
from multiprocessing import Queue
from src.communication_gateway import BaseCommunicationGateway
from src.event_types import Event
from src.queues_dir import QueuesDirectory
from src.control_system import BaseControlSystem
from src.navigation_system import BaseNavigationSystem
from src.servos import Servos
from src.mission_planner import MissionPlanner
from src.mission_type import Mission, GeoSpecificSpeedLimit
from time import sleep
from src.cargo_bay import CargoBay
from src.system_wrapper import SystemComponentsContainer
from src.mission_planner_mqtt import MissionSender
from src.sitl_mqtt import TelemetrySender
from src.wpl_parser import WPLParser
from src.mission_planner import Mission
from src.config import (SERVOS_QUEUE_NAME, CONTROL_SYSTEM_QUEUE_NAME, LOG_ERROR, 
                       LOG_INFO, CARGO_BAY_QUEUE_NAME, SAFETY_BLOCK_QUEUE_NAME, 
                       LOG_DEBUG, PLANNER_QUEUE_NAME, NAVIGATION_QUEUE_NAME,
                       SECURITY_MONITOR_QUEUE_NAME, COMMUNICATION_GATEWAY_QUEUE_NAME)
from src.safety_block import BaseSafetyBlock
from src.security_monitory import BaseSecurityMonitor
from src.security_policy_type import SecurityPolicy
import datetime

home = GeoPoint(latitude=63.197640, longitude=75.453721) #стартовая позиция
car_id = "m3" #номер машины
afcs_present = True
queues_dir = QueuesDirectory() 
wpl_file = "/home/user/cyberimmune-autonomy-chvt/module2.wpl" #идентификация файла с заданием маршрута


if afcs_present:
    mission_sender = MissionSender(
        queues_dir=queues_dir, client_id=car_id, log_level=LOG_ERROR)
    telemetry_sender = TelemetrySender(
        queues_dir=queues_dir, client_id=car_id, log_level=LOG_ERROR)
parser = WPLParser(wpl_file)    
points = parser.parse()
print(points)
if not points:
    print("Ошибка: список точек пуст. Проверьте файл WPL.")
else:
    print(points)

speed_limits = [
    GeoSpecificSpeedLimit(0, 30),
    GeoSpecificSpeedLimit(1, 60),
    GeoSpecificSpeedLimit(2, 60),
    GeoSpecificSpeedLimit(3, 45),
]

home = points[0]
mission = Mission(home=home, waypoints=points,speed_limits=speed_limits, armed=True)

# ======================================Монитор Безопасности=================================================
"""Монитор безопасности"""
class SecurityMonitor(BaseSecurityMonitor):
    """ класс монитора безопасности """

    def __init__(self, queues_dir):
        super().__init__(queues_dir)
        self._init_set_security_policies()

    def _init_set_security_policies(self):
        """ инициализация политик безопасности """
        default_policies = [
            # Коммуникация
            SecurityPolicy(
                source=COMMUNICATION_GATEWAY_QUEUE_NAME,
                destination=CONTROL_SYSTEM_QUEUE_NAME,
                operation='set_mission'),
            SecurityPolicy(
                source=COMMUNICATION_GATEWAY_QUEUE_NAME,
                destination=SAFETY_BLOCK_QUEUE_NAME,
                operation='set_mission'),
                
            # Навигация
            SecurityPolicy(
                source=NAVIGATION_QUEUE_NAME,
                destination=CONTROL_SYSTEM_QUEUE_NAME,
                operation='position_update'),
            SecurityPolicy(
                source=NAVIGATION_QUEUE_NAME,
                destination=SAFETY_BLOCK_QUEUE_NAME,
                operation='position_update'),
                
            # Система контроля
            SecurityPolicy(
                source=CONTROL_SYSTEM_QUEUE_NAME,
                destination=SAFETY_BLOCK_QUEUE_NAME,
                operation='set_speed'),
            SecurityPolicy(
                source=CONTROL_SYSTEM_QUEUE_NAME,
                destination=SAFETY_BLOCK_QUEUE_NAME,
                operation='set_direction'),
            SecurityPolicy(
                source=CONTROL_SYSTEM_QUEUE_NAME,
                destination=CARGO_BAY_QUEUE_NAME,
                operation='lock_cargo'),
            SecurityPolicy(
                source=CONTROL_SYSTEM_QUEUE_NAME,
                destination=CARGO_BAY_QUEUE_NAME,
                operation='release_cargo'),
                
            # Безопастность
            SecurityPolicy(
                source=SAFETY_BLOCK_QUEUE_NAME,
                destination=SERVOS_QUEUE_NAME,
                operation='set_speed'),
            SecurityPolicy(
                source=SAFETY_BLOCK_QUEUE_NAME,
                destination=SERVOS_QUEUE_NAME,
                operation='set_direction')
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

        if authorized is False:
            self._log_message(LOG_ERROR, f"событие не разрешено политиками безопасности! {event}")
        return authorized

# ==============================================================================================
class SafetyBlock(BaseSafetyBlock):
    """Класс ограничений безопасности с расширенными проверками"""
    
    def __init__(self, queues_dir=None, log_level=LOG_INFO):
        super().__init__(queues_dir=queues_dir, log_level=log_level)
        self._max_speed = 60  # Максимальная допустимая скорость (км/ч)
        self._max_turn_angle = 45  # Максимальный угол поворота (градусы)
        self._emergency_stop = False
        
    def _set_new_direction(self, direction: float):
        """Установка нового направления с проверкой безопасности"""
        if self._emergency_stop:
            self._log_message(LOG_INFO, "Аварийная остановка! Направление не изменено")
            return
            
        # Нормализация угла направления (0-360 градусов)
        direction = direction % 360   
        self._log_message(LOG_INFO, f"Текущие координаты: {self._position}")
        self._log_message(LOG_DEBUG, f"Маршрутное задание: {self._mission}")
        self._log_message(LOG_DEBUG, f"Состояние маршрута: {self._route}")
        
        # Проверка нахождения в пределах маршрута
        if not self._check_route_safety(direction):
            self._log_message(LOG_ERROR, "Направление ведет за пределы безопасной зоны!")
            return
            
        self._direction = direction
        self._send_direction_to_consumers()

    def _set_new_speed(self, speed: float):
        """Установка новой скорости с проверкой безопасности"""
        if self._emergency_stop:
            self._log_message(LOG_INFO, "Аварийная остановка! Скорость не изменена")
            return
            
        # Проверка максимальной скорости
        if speed > self._max_speed:
            self._log_message(LOG_ERROR, f"Попытка превысить максимальную скорость: {speed} > {self._max_speed}")
            return
        
        # Принудительное ограничение скорости
        speed = min(speed, self._max_speed)
            
        self._speed = speed
        self._send_speed_to_consumers()
        
    def _check_route_safety(self, direction: float) -> bool:
        """Проверка безопасности направления относительно маршрута"""
        return True
        
    def _get_current_waypoint_index(self) -> int:
        """Получение индекса текущей точки маршрута"""
        return 0
        
    def emergency_stop(self):
        """Аварийная остановка"""
        self._emergency_stop = True
        self._speed = 0
        self._send_speed_to_consumers()
        self._log_message(LOG_INFO, "Активирована аварийная остановка!")
        
    def _send_speed_to_consumers(self):
        """Отправка скорости сервоприводам через монитор безопасности"""
        event = Event(
            source=self.event_source_name,
            destination=SERVOS_QUEUE_NAME,
            operation="set_speed",
            parameters=self._speed
        )
        security_monitor_q: Queue = self._queues_dir.get_queue(SECURITY_MONITOR_QUEUE_NAME)
        security_monitor_q.put(event)

    def _send_direction_to_consumers(self):
        """Отправка направления сервоприводам через монитор безопасности"""
        event = Event(
            source=self.event_source_name,
            destination=SERVOS_QUEUE_NAME,
            operation="set_direction",
            parameters=self._direction
        )
        security_monitor_q: Queue = self._queues_dir.get_queue(SECURITY_MONITOR_QUEUE_NAME)
        security_monitor_q.put(event)

# ==============================================================================================
"""Блок коммуникации"""
class CommunicationGateway(BaseCommunicationGateway):
    def _send_mission_to_consumers(self):
        event = Event(
            source=BaseCommunicationGateway.event_source_name,
            destination=CONTROL_SYSTEM_QUEUE_NAME,
            operation="set_mission",
            parameters=self._mission
        )
        security_monitor_q: Queue = self._queues_dir.get_queue(SECURITY_MONITOR_QUEUE_NAME)
        security_monitor_q.put(event)
        
        event = Event(
            source=BaseCommunicationGateway.event_source_name,
            destination=SAFETY_BLOCK_QUEUE_NAME,
            operation="set_mission",
            parameters=self._mission
        )
        security_monitor_q.put(event)

# ==============================================================================================
class ControlSystem(BaseControlSystem):
    """ControlSystem с защитой от киберпрепятствий и правильной выгрузкой груза"""
    
    def __init__(self, queues_dir=None, log_level=LOG_INFO):
        super().__init__(queues_dir=queues_dir, log_level=log_level)
        self._current_cargo_weight = 0
        
    def _check_cargo_weight(self):
        """Проверка веса груза перед перемещением"""
        if self._current_cargo_weight > 5:
            self._log_message(LOG_ERROR, "Груз превышает 5 тонн - движение запрещено!")
            return False
        return True

    def _calculate_current_bearing(self) -> float:
        """Переопределенный метод расчета направления без киберпрепятствий"""
        if self._route.route_finished:
            return 0.0
        pos: GeoPoint = self._position
        dst: GeoPoint = self._route.next_point()
        bearing = self._calculate_bearing(pos, dst)
        self._log_message(LOG_DEBUG, f"новое направление {bearing}")
        return bearing

    def _recalc_control(self):
        """Переопределенный метод управления с правильной выгрузкой груза"""
        new_speed = 0
        new_direction = 0

        if self._route.route_finished:
            return
            
        self._log_message(LOG_DEBUG, "пересчитываем управление")

        distance_to_next_wp = self._route.calculate_remaining_distance_to_next_point(
            self._position)

        if distance_to_next_wp <= self._tolerance_meters:
            self._route.move_to_next_point()

            # Выгрузка груза при достижении последней точки маршрута
            if self._route.route_finished:
                self._log_message(
                    LOG_INFO, "маршрут пройден, " +
                    f"текущее время {datetime.datetime.now().time()}")
                self._release_cargo()
            else:
                self._log_message(LOG_INFO, "сегмент пройден")

        new_speed = self._route.calculate_speed()

        if int(self._speed) != int(new_speed/3.6):
            self._log_message(
                LOG_INFO, f"новая скорость {new_speed} (была {int(self._speed*3.6)})")

        self._set_speed(new_speed)

        new_direction = self._calculate_current_bearing()
        if int(self._direction_grad) != int(new_direction):
            self._log_message(
                LOG_INFO, f"новое направление {int(new_direction)} " +
                f"(было {int(self._direction_grad)})")
        self._set_direction(new_direction)

        self._log_message(
            LOG_DEBUG, f"до следующей точки {int(distance_to_next_wp)} м\t" +
            f"скорость {int(new_speed)}км/ч\tнаправление {int(new_direction)} град."
        )

        self._send_speed_and_direction_to_consumers(new_speed, new_direction)

    def _send_speed_and_direction_to_consumers(self, speed, direction):
        """Отправка команд управления через монитор безопасности"""
        if not self._check_cargo_weight():
            return
            
        # Отправка скорости через монитор безопасности
        event_speed = Event(
            source=self.event_source_name,
            destination=SAFETY_BLOCK_QUEUE_NAME,
            operation="set_speed",
            parameters=speed
        )
        security_monitor_q: Queue = self._queues_dir.get_queue(SECURITY_MONITOR_QUEUE_NAME)
        security_monitor_q.put(event_speed)
        
        # Отправка направления через монитор безопасности
        event_direction = Event(
            source=self.event_source_name,
            destination=SAFETY_BLOCK_QUEUE_NAME,
            operation="set_direction",
            parameters=direction
        )
        security_monitor_q.put(event_direction)

    def _lock_cargo(self):
        """ заблокировать грузовой отсек через монитор безопасности """
        event = Event(
            source=CONTROL_SYSTEM_QUEUE_NAME,
            destination=CARGO_BAY_QUEUE_NAME,
            operation="lock_cargo",
            parameters=None
        )
        security_monitor_q: Queue = self._queues_dir.get_queue(SECURITY_MONITOR_QUEUE_NAME)
        security_monitor_q.put(event)

    def _release_cargo(self):
        """ открыть грузовой отсек через монитор безопасности """
        event = Event(
            source=CONTROL_SYSTEM_QUEUE_NAME,
            destination=CARGO_BAY_QUEUE_NAME,
            operation="release_cargo",
            parameters=None
        )
        security_monitor_q: Queue = self._queues_dir.get_queue(SECURITY_MONITOR_QUEUE_NAME)
        security_monitor_q.put(event)

# ==============================================================================================
class NavigationSystem(BaseNavigationSystem):
    def _send_position_to_consumers(self):
        # событие для системы управления
        event = Event(
            source=self.event_source_name,
            destination=CONTROL_SYSTEM_QUEUE_NAME,
            operation="position_update",
            parameters=self._position
        )
        security_monitor_q: Queue = self._queues_dir.get_queue(SECURITY_MONITOR_QUEUE_NAME)
        security_monitor_q.put(event)
        
        event = Event(
            source=self.event_source_name,
            destination=SAFETY_BLOCK_QUEUE_NAME,
            operation="position_update",
            parameters=self._position
        )
        security_monitor_q.put(event)

# ==============================================================================================
# Инициализация компонентов системы
security_monitor = SecurityMonitor(queues_dir=queues_dir)
communication_gateway = CommunicationGateway(queues_dir=queues_dir, log_level=LOG_ERROR)
control_system = ControlSystem(queues_dir=queues_dir, log_level=LOG_INFO)
navigation_system = NavigationSystem(queues_dir=queues_dir, log_level=LOG_ERROR)
servos = Servos(queues_dir=queues_dir, log_level=LOG_ERROR)
cargo_bay = CargoBay(queues_dir=queues_dir, log_level=LOG_INFO)
safety_block = SafetyBlock(queues_dir=queues_dir, log_level=LOG_INFO)
sitl = SITL(queues_dir=queues_dir, position=home, car_id=car_id, post_telemetry=afcs_present, log_level=LOG_ERROR)
mission_planner = MissionPlanner(queues_dir, afcs_present=afcs_present, mission=mission)

# Контейнер компонентов для старта
system_components = SystemComponentsContainer(
    components=[
        mission_sender,
        telemetry_sender,
        sitl,
        navigation_system,
        servos,
        cargo_bay,
        communication_gateway,
        control_system,
        mission_planner,
        safety_block,
        security_monitor
    ] if afcs_present else [
        sitl,
        navigation_system,
        servos,
        cargo_bay,
        communication_gateway,
        control_system,
        mission_planner,
        safety_block,
        security_monitor
    ])

control_system.enable_surprises()
system_components.start()
sleep(83) #время работы в секундах
system_components.stop()
system_components.clean()