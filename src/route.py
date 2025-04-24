""" код представления маршрута """
from geopy.distance import great_circle
from geopy.point import Point as GeoPoint


class Route:
    """
    Класс, представляющий маршрут с ограничениями скорости.

    Attributes:
        points (list): Список точек маршрута (GeoPoint).
        speed_limits (list): Список ограничений скорости для каждого отрезка маршрута.
        current_index (int): Индекс текущей точки маршрута.
    """
    

    def __init__(self, points, speed_limits):
        """
        Инициализирует маршрут с заданными точками и ограничениями скорости.

        Args:
            points (list): Список объектов GeoPoint.
            speed_limits (list): Список ограничений скорости для каждого отрезка маршрута.

        Raises:
            ValueError: Если количество точек не на 1 больше, чем количество ограничений скорости.
        """
        if len(points) < len(speed_limits):
            raise ValueError(
                "Количество ограничений скорости не может превышать количество точек!")

        self.points = points
        self.speed_limits = speed_limits
        self.current_index = 0
        self.route_finished = False
        self._last_speed_limit = 0.0

    def next_point(self) -> GeoPoint:
        """
        Выдаёт следующую точку маршрута.

        Returns:
            GeoPoint: Следующая точка маршрута или None, если достигнут конец.
        """
        if self.route_finished:
            return None
        if self.current_index < len(self.points) - 1:
            return self.points[self.current_index + 1]
        return None

    def get_next_point(self) -> GeoPoint:
        """
        Получает ближайшую точку маршрута.

        Returns:
            GeoPoint: ближайшая точка маршрута или None, если достигнут конец.
        """
        if self.route_finished:
            return None
        if self.current_index < len(self.points):
            return self.points[self.current_index]
        return None

    def move_to_next_point(self):
        """
        Перемещает к следующей точке маршрута.

        Returns:
            bool: True, если перемещение успешно, иначе False.
        """
        if self.current_index < len(self.points) - 1:
            self.current_index += 1
            if self.current_index == len(self.points) - 1:
                self.route_finished = True
            return True
        
        self.route_finished = True
        return False

    def calculate_distance_to_next_point(self):
        """
        Вычисляет расстояние до следующей точки маршрута.

        Returns:
            float: Расстояние до следующей точки в метрах.
        """
        if self.current_index < len(self.points) - 1:
            return great_circle(
                (self.points[self.current_index].latitude,
                 self.points[self.current_index].longitude),
                (self.points[self.current_index + 1].latitude,
                 self.points[self.current_index + 1].longitude)
            ).meters
        return 0

    def calculate_remaining_distance_to_next_point(self, position: GeoPoint):
        """
        Вычисляет оставшееся расстояние до следующей точки маршрута.

        Args:
            position (GeoPoint): текущее положение

        Returns:
            float: Расстояние до следующей точки в метрах.
        """
        if self.current_index < len(self.points) - 1:
            return great_circle(
                position,
                (self.points[self.current_index + 1].latitude,
                 self.points[self.current_index + 1].longitude)
            ).meters
        return 0

    def calculate_speed(self) -> float:
        """calculate_speed вычисляет скорость для текущего участка

        Returns:
            float: значение скорости в км/ч
        """
        if self.route_finished:
            return 0.0

        for limit in self.speed_limits:
            if limit.waypoint_index == self.current_index:
                self._last_speed_limit = limit.speed_limit
                break
        return self._last_speed_limit

    def calculate_travel_time_to_next_point(self):
        """
        Вычисляет время в пути до следующей точки маршрута с учетом ограничения скорости.

        Returns:
            float: Время в пути до следующей точки в секундах.
        """
        distance = self.calculate_distance_to_next_point()
        if self.current_index < len(self.speed_limits):
            # Скорость в км/ч
            speed_limit = self.speed_limits[self.current_index]
            # Преобразуем скорость в м/с
            return distance / (speed_limit * 1000 / 3600)
        return float('inf')
