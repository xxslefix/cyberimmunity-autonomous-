""" парсер WPL файла с маршрутом """
from geopy.point import Point as GeoPoint
from typing import List


class WPLParser:
    """
    Класс для парсинга WPL файлов формата QGC.

    Attributes:
        file_path (str): Путь к WPL файлу.
    """

    def __init__(self, file_path: str):
        """
        Инициализирует WPLParser с заданным путем к файлу.

        Args:
            file_path (str): Путь к WPL файлу.
        """
        self.file_path = file_path

    def parse(self) -> List[GeoPoint]:
        """
        Парсит WPL файл и возвращает список точек маршрута.

        Returns:
            List[GeoPoint]: Список объектов GeoPoint, представляющих точки маршрута.
        """
        points = []
        with open(self.file_path, 'r') as file:
            lines = file.readlines()

            # Пропускаем первую строку (заголовок)
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 10:
                    lat = float(parts[8])
                    lon = float(parts[9])
                    points.append(GeoPoint(lat, lon))

        return points