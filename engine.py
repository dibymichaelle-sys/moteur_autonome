# --- MODULE 1 : ZFE (GEO) ---

def is_in_bounding_box(lat, lon, polygon):
    lats = [p['lat'] for p in polygon]
    lons = [p['lon'] for p in polygon]
    return min(lats) <= lat <= max(lats) and min(lons) <= lon <= max(lons)

def is_point_in_polygon(lat, lon, polygon):
    # Optimisation Bounding Box
    if not is_in_bounding_box(lat, lon, polygon):
        return False

    # Algorithme Ray Casting
    inside = False
    n = len(polygon)
    p1 = polygon
    for i in range(1, n + 1):
        p2 = polygon[i % n]
        if lon > min(p1['lon'], p2['lon']):
            if lon <= max(p1['lon'], p2['lon']):
                if lat <= max(p1['lat'], p2['lat']):
                    if p1['lon'] != p2['lon']:
                        xints = (lon - p1['lon']) * (p2['lat'] - p1['lat']) / (p2['lon'] - p1['lon']) + p1['lat']
                    if p1['lat'] == p2['lat'] or lat <= xints:
                        inside = not inside
        p1 = p2
    return inside

def run_zfe_check(polygon_file, gps_file):
    with open(polygon_file, 'r') as f:
        polygon = json.load(f)
    with open(gps_file, 'r') as f:
        traces = json.load(f)

    for point in traces:
        if is_point_in_polygon(point['lat'], point['lon'], polygon):
            print(f"[ALERT ZFE] Camion {point['id']} à {point['timestamp']} - Position: {point['lat']},{point['lon']}")
# --- MODULE 2 : SAFETY (PHYSICS) ---
def analyze_safety(acc_file):
    harsh_braking_events = []
    max_deceleration = 0

    with open(acc_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            acc_y = float(row['acc_y'])
            # Seuil de détection selon l'énoncé : < -2.5 m/s²
            if acc_y < -2.5:
                event = {
                    "timestamp": row['timestamp'],
                    "force_g": acc_y
                }
                harsh_braking_events.append(event)
                if acc_y < max_deceleration:
                    max_deceleration = acc_y

    daily_score = {
        "vehicle_id": "GML-TRUCK-50",
        "date": "2026-06-08",
        "summary": {
            "harsh_braking_count": len(harsh_braking_events),
            "peak_deceleration": max_deceleration,
            "safety_rating": "DANGER" if len(harsh_braking_events) > 0 else "SAFE"
        },
        "events": harsh_braking_events
    }

    with open('daily_score.json', 'w') as f:
        json.dump(daily_score, f, indent=4)
    print(f"[SAFETY] Analyse terminée. {len(harsh_braking_events)} freinages violents détectés.")

# --- EXECUTION DU POC ---
if __name__ == "__main__":
    # Simulation du moteur
    run_zfe_check('lyon_polygon.json', 'truck_gps.json')
    analyze_safety('accelerometer_data.csv')
