import math

class LocationService:
    EARTH_RADIUS_KM = 6371.0

    @classmethod
    def haversine_distance(cls, lat1, lon1, lat2, lon2):
        """
        Calculate the great circle distance between two points 
        on the earth (specified in decimal degrees).
        Returns distance in kilometers (float).
        """
        if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
            return None

        try:
            lat1_rad = math.radians(float(lat1))
            lon1_rad = math.radians(float(lon1))
            lat2_rad = math.radians(float(lat2))
            lon2_rad = math.radians(float(lon2))

            dlat = lat2_rad - lat1_rad
            dlon = lon2_rad - lon1_rad

            a = math.sin(dlat / 2.0) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2.0) ** 2
            c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
            distance = cls.EARTH_RADIUS_KM * c

            return round(distance, 1)
        except (ValueError, TypeError):
            return None

    @classmethod
    def format_distance(cls, distance_km):
        if distance_km is None:
            return "Distance unavailable"
        if distance_km < 1.0:
            meters = int(distance_km * 1000)
            return f"{meters} m"
        return f"{distance_km:.1f} km"
