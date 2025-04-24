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
from src.config import SERVOS_QUEUE_NAME, CONTROL_SYSTEM_QUEUE_NAME, LOG_ERROR, LOG_INFO, CARGO_BAY_QUEUE_NAME


home = GeoPoint(latitude=63.197640, longitude=75.453721) #стартовая позиция
car_id = "m2" #номер машины
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
# ==============================================================================================
"""блок коммуникации """
class CommunicationGateway(BaseCommunicationGateway):
    def _send_mission_to_consumers(self):
        control_q_name = CONTROL_SYSTEM_QUEUE_NAME
        event = Event(source=BaseCommunicationGateway.event_source_name,
            destination=control_q_name,
            operation="set_mission", parameters=self._mission
            )
        control_q: Queue = self._queues_dir.get_queue(control_q_name)
        control_q.put(event)

communication_gateway = CommunicationGateway(queues_dir=queues_dir)
# ==============================================================================================
class ControlSystem(BaseControlSystem):
    """ControlSystem блок расчёта управления """
    def __init__(self, queues_dir=None, log_level=LOG_INFO):
        super().__init__(queues_dir=queues_dir, log_level=log_level)
        self._current_cargo_weight = 0  # Текущий вес груза
        
    def _check_cargo_weight(self):
        """Проверка веса груза перед перемещением"""
        if self._current_cargo_weight > 5:  # Если груз > 5 тонн
            print("Предупреждение: Груз превышает 5 тонн")
            return False
        return True

    def _send_speed_and_direction_to_consumers(self, speed, direction):
        """Отправка команд управления только если вес груза допустим"""
        if not self._check_cargo_weight():
            return  # Прерываем выполнение если груз слишком тяжелый
            
        servos_q_name = SERVOS_QUEUE_NAME
        servos_q: Queue = self._queues_dir.get_queue(servos_q_name)
        event_speed = Event(source=self.event_source_name,
                          destination=servos_q_name,
                          operation="set_speed",
                          parameters=speed
                          )
        event_direction = Event(source=self.event_source_name,
                              destination=servos_q_name,
                              operation="set_direction",
                              parameters=direction
                              )
        servos_q.put(event_speed)
        servos_q.put(event_direction)


    def _lock_cargo(self):
        """ заблокировать грузовой отсек """
        cargo_q = self._queues_dir.get_queue(CARGO_BAY_QUEUE_NAME)
        event = Event(source=CONTROL_SYSTEM_QUEUE_NAME,
                      destination=CARGO_BAY_QUEUE_NAME,
                      operation="lock_cargo",
                      parameters=None
                      )
        cargo_q.put(event)

    def _release_cargo(self):
        """ открыть грузовой отсек """
        cargo_q = self._queues_dir.get_queue(CARGO_BAY_QUEUE_NAME)
        event = Event(source=CONTROL_SYSTEM_QUEUE_NAME,
                      destination=CARGO_BAY_QUEUE_NAME,
                      operation="release_cargo",
                      parameters=None
                      )
        cargo_q.put(event) 
control_system = ControlSystem(queues_dir=queues_dir) 
# ==============================================================================================
"""блок навигации """
class NavigationSystem(BaseNavigationSystem):
    def _send_position_to_consumers(self):
        control_q_name = CONTROL_SYSTEM_QUEUE_NAME
        event = Event(source=self.event_source_name,
                    destination=control_q_name,
                    operation="position_update", parameters=self._position
                    )
        control_q: Queue = self._queues_dir.get_queue(control_q_name)
        control_q.put(event)

navigation_system = NavigationSystem(queues_dir=queues_dir)
# ==============================================================================================
"""блок подключения сервоприводов """
servos = Servos(queues_dir=queues_dir)
# ==============================================================================================
sitl = SITL(queues_dir=queues_dir, position=home,car_id=car_id, post_telemetry=afcs_present, log_level=LOG_ERROR)
mission_planner = MissionPlanner(queues_dir, afcs_present=afcs_present, mission=mission)
communication_gateway = CommunicationGateway(queues_dir=queues_dir, log_level=LOG_ERROR)
control_system = ControlSystem(queues_dir=queues_dir, log_level=LOG_INFO)
navigation_system = NavigationSystem(queues_dir=queues_dir, log_level=LOG_ERROR)
servos = Servos(queues_dir=queues_dir, log_level=LOG_ERROR)
cargo_bay = CargoBay(queues_dir=queues_dir, log_level=LOG_INFO)
"""контейнер компонентов для старта"""
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
        mission_planner
    ] if afcs_present else [
        sitl,
        navigation_system,
        servos,
        cargo_bay,
        communication_gateway,
        control_system,
        mission_planner
    ])

system_components.start()
sleep(100) #время работы в секундах
system_components.stop()
system_components.clean()
