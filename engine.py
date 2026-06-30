import json
import csv
from datetime import date

# =============================================================================
# MODULE 1 : ZFE (Géographique)
# Objectif : détecter si un camion entre dans une Zone à Faibles Émissions.
# =============================================================================

def is_in_bounding_box(lat, lon, polygon):
    """
    Vérification rapide : le point est-il dans le rectangle englobant le polygone ?
    Si non, inutile de faire le calcul complet — on rejette immédiatement.
    """
    lats = [p['lat'] for p in polygon]
    lons = [p['lon'] for p in polygon]
    return min(lats) <= lat <= max(lats) and min(lons) <= lon <= max(lons)


def is_on_segment(lat, lon, p1, p2):
    """
    Vérifie si le point (lat, lon) se trouve exactement sur le segment [p1, p2].
    Utilisé pour inclure les points sur la bordure du polygone.
    """
    # Le point doit être dans le rectangle englobant du segment
    if not (min(p1['lat'], p2['lat']) <= lat <= max(p1['lat'], p2['lat']) and
            min(p1['lon'], p2['lon']) <= lon <= max(p1['lon'], p2['lon'])):
        return False
    # Vérification de la colinéarité via le produit vectoriel (= 0 si aligné)
    cross = (p2['lat'] - p1['lat']) * (lon - p1['lon']) - (p2['lon'] - p1['lon']) * (lat - p1['lat'])
    return abs(cross) < 1e-10


def is_point_in_polygon(lat, lon, polygon):
    """
    Algorithme Ray Casting : on lance un rayon horizontal depuis le point
    et on compte combien de fois il coupe les arêtes du polygone.
    - Nombre impair de croisements → point INSIDE
    - Nombre pair               → point OUTSIDE
    Les points sur la bordure sont également considérés INSIDE.
    """
    # Étape 1 : filtre rapide par bounding box
    if not is_in_bounding_box(lat, lon, polygon):
        return False

    n = len(polygon)

    # Étape 2 : vérification bordure — un point sur une arête est IN
    for i in range(n):
        if is_on_segment(lat, lon, polygon[i], polygon[(i + 1) % n]):
            return True

    # Étape 3 : Ray Casting pour les points strictement intérieurs
    inside = False
    p1 = polygon[0]  # on commence par le premier sommet du polygone

    for i in range(1, n + 1):
        p2 = polygon[i % n]  # sommet suivant (revient à 0 en fin de boucle)

        # Le rayon horizontal doit croiser l'arête [p1, p2] sur l'axe longitude
        if lon > min(p1['lon'], p2['lon']):
            if lon <= max(p1['lon'], p2['lon']):
                if lat <= max(p1['lat'], p2['lat']):
                    if p1['lon'] != p2['lon']:
                        # Calcul du point d'intersection entre le rayon et l'arête
                        xints = (lon - p1['lon']) * (p2['lat'] - p1['lat']) / (p2['lon'] - p1['lon']) + p1['lat']
                        # Si le point est sous le croisement, on inverse l'état inside
                        if p1['lat'] == p2['lat'] or lat <= xints:
                            inside = not inside
        p1 = p2  # avancer au sommet suivant

    return inside


def run_zfe_check(polygon_file, gps_file):
    """
    Charge les fichiers et vérifie chaque point GPS contre le polygone ZFE.
    Affiche une alerte pour chaque camion détecté dans la zone.
    """
    # Vérification existence des fichiers avant d'ouvrir
    for filepath in [polygon_file, gps_file]:
        try:
            open(filepath)
        except FileNotFoundError:
            print(f"[ERREUR] Fichier introuvable : {filepath}")
            return

    with open(polygon_file, 'r') as f:
        polygon = json.load(f)
    with open(gps_file, 'r') as f:
        traces = json.load(f)

    alerts = 0
    for point in traces:
        if is_point_in_polygon(point['lat'], point['lon'], polygon):
            print(f"[ALERT ZFE] Camion {point['id']} à {point['timestamp']} - Position: {point['lat']},{point['lon']}")
            alerts += 1

    if alerts == 0:
        print("[ZFE] Aucun camion détecté dans la zone.")


# =============================================================================
# MODULE 2 : Safety (Physique)
# Objectif : identifier les freinages violents dans les données accéléromètre.
# Format CSV attendu : timestamp,acc_x,acc_y,acc_z (timestamps Unix)
# =============================================================================

def analyze_safety(acc_file, vehicle_id="UNKNOWN", analysis_date=None):
    """
    Lit le fichier CSV accéléromètre (colonnes : timestamp, acc_x, acc_y, acc_z)
    et applique un filtrage par seuil : tout échantillon dont la valeur absolue
    dépasse 2.5G est un freinage violent.
    Génère un fichier daily_score.json avec le bilan de la journée.

    Paramètres :
      acc_file      : chemin vers le fichier CSV
      vehicle_id    : identifiant du véhicule (optionnel)
      analysis_date : date d'analyse au format YYYY-MM-DD (défaut : aujourd'hui)
    """
    # Vérification existence du fichier avant d'ouvrir
    try:
        open(acc_file)
    except FileNotFoundError:
        print(f"[ERREUR] Fichier introuvable : {acc_file}")
        return

    harsh_braking_events = []
    max_deceleration = 0
    analysis_date = analysis_date or str(date.today())

    with open(acc_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            acc_y = float(row['acc_y'])

            # Seuil : magnitude > 2.5G (valeur absolue pour capturer
            # freinage brusque négatif ET choc avant positif)
            if abs(acc_y) > 2.5:
                event = {
                    "timestamp": row['timestamp'],
                    "force_g": acc_y
                }
                harsh_braking_events.append(event)
                # On garde la décélération la plus forte (valeur la plus négative)
                if acc_y < max_deceleration:
                    max_deceleration = acc_y

    # Construction du rapport journalier
    daily_score = {
        "vehicle_id": vehicle_id,
        "date": analysis_date,
        "summary": {
            "harsh_braking_count": len(harsh_braking_events),
            "peak_deceleration": max_deceleration,
            # DANGER si au moins un freinage violent, SAFE sinon
            "safety_rating": "DANGER" if len(harsh_braking_events) > 0 else "SAFE"
        },
        "events": harsh_braking_events
    }

    with open('daily_score.json', 'w') as f:
        json.dump(daily_score, f, indent=4)

    print(f"[SAFETY] Analyse terminée. {len(harsh_braking_events)} freinages violents détectés.")


# =============================================================================
# POINT D'ENTRÉE
# =============================================================================

if __name__ == "__main__":
    run_zfe_check('lyon_polygon.json', 'truck_gps.json')
    analyze_safety('accelerometer_data.csv', vehicle_id="GML-TRUCK-50")
