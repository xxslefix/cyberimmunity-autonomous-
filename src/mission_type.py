""" модуль для описания маршрутного задания
"""
from dataclasses import dataclass
from typing import List
from geopy import Point


@dataclass
class GeoSpecificSpeedLimit:
    """ ограничение скорости в определённой точке маршрута
    действует до следующего скоростного ограничения
    """
    # start_position: Point  # координаты точка начала действия скоростного ограничения
    waypoint_index: int  # индекс путевой точки, начиная с которой действует это ограничение
    speed_limit: int  # ограничение скорости, км/ч


@dataclass
class Mission:
    """ класс описания маршрутного задания
    """
    home: Point  # координата начала маршрута
    waypoints: List[Point]  # координаты путевых точек
    # ограничения скорости на маршруте
    speed_limits: List[GeoSpecificSpeedLimit]
    armed: bool  # поездка разрешена (истина) или запрещена (ложь)
