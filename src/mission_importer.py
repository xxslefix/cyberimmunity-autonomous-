""" модуль для импортирования миссии из wpl файла """

from typing import List
from geopy import Point as GeoPoint
from src.mission_type import GeoSpecificSpeedLimit, Mission
from src.wpl_parser import WPLParser


class MissionImporter:
    """ класс для импортирования миссии """

    def __init__(self, mission_file: str):
        """__init__ конструктор

        Args:
            mission_file (str): имя файла с миссией
        """
        self._wpl_parser = WPLParser(file_path=mission_file)
        self._waypoints = self._wpl_parser.parse()
        self._mission = Mission(
            home=self._waypoints[0], waypoints=self._waypoints, speed_limits=[], armed=False)

    def set_speed_limits(self, speed_limits: List[GeoSpecificSpeedLimit]) -> Mission:
        """set_speed_limits установка скоростных ограничений

        Args:
            speed_limits (List): список скоростных ограничений

        Returns:
            Mission: миссия
        """
        self._mission.speed_limits = speed_limits
        return self._mission

    def get_mission(self) -> GeoPoint:
        """get_mission возвращает импортированную миссию

        Returns:
            GeoPoint: точки миссии
        """

        return self._mission
