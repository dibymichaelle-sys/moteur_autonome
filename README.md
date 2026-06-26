# Moteur Autonome — POC Flotte Camions

Moteur d'analyse autonome pour la surveillance d'une flotte de camions.  
Deux modules indépendants : détection ZFE (géographique) et analyse sécurité (physique).

---

## Procédure de test en local

### Prérequis

- Python 3.8 ou supérieur
- Aucune dépendance externe (librairie standard uniquement)

### Installation

```bash
git clone https://github.com/dibymichaelle-sys/moteur_autonome.git
cd moteur_autonome
```

### Exécution

```bash
python3 engine.py
```

### Résultats attendus

**Console :**
```
[ALERT ZFE] Camion 4 à 08:00:30 - Position: 45.76,4.8357
[ALERT ZFE] Camion 5 à 08:00:40 - Position: 45.75,4.85
[SAFETY] Analyse terminée. 3 freinages violents détectés.
```

**Fichier généré :** `daily_score.json` dans le répertoire courant.

### Fichiers d'entrée

| Fichier | Description |
|--------|-------------|
| `lyon_polygon.json` | Coordonnées du polygone ZFE de Lyon |
| `truck_gps.json` | Traces GPS horodatées du camion |
| `accelerometer_data.csv` | Données accéléromètre (colonnes : timestamp, vehicle_id, date, acc_x, acc_y, acc_z) |

---

## Architecture et pistes de réflexion

### Module 1 : ZFE (Géographique)

**Problème** : Déterminer si un camion se trouve dans une Zone à Faibles Émissions.

**Algorithme choisi : Ray Casting (Point in Polygon)**

L'idée est de lancer un rayon horizontal depuis le point testé vers l'infini et de compter combien de fois il coupe les arêtes du polygone. Si le nombre de croisements est impair → le point est à l'intérieur.

```
Point P → rayon →→→→→→→→ ∞
              ×     ×
         (2 croisements = pair = OUTSIDE)

Point P → rayon →→→→→→→→ ∞
              ×
         (1 croisement = impair = INSIDE)
```

**Optimisation Bounding Box** : avant d'exécuter le Ray Casting (coûteux), on vérifie d'abord si le point est dans le rectangle englobant le polygone. Si non, on rejette immédiatement — évite les calculs inutiles pour les points clairement hors zone.

```
is_in_bounding_box() → filtre rapide O(n)
is_point_in_polygon() → Ray Casting O(n) seulement si nécessaire
```

**Input** : `lyon_polygon.json`, `truck_gps.json`  
**Output** : log `[ALERT ZFE]` sur chaque point GPS détecté dans la zone

---

### Module 2 : Safety (Physique)

**Problème** : Identifier les freinages violents dans un flux de données accéléromètre bruité.

**Algorithme choisi : Filtrage par seuil (Threshold Filtering)**

Les données accéléromètre contiennent du bruit de fond (vibrations moteur, route, etc.) autour de 0 G. Un freinage violent génère un pic de décélération mesurable.

**Seuil retenu : |acc_y| > 2.5 G**

- On utilise la **valeur absolue** pour capturer à la fois les freinages brusques (acc_y négatif) et les chocs avant (acc_y positif).
- Tout échantillon dépassant ce seuil est enregistré comme événement.

**Output** : fichier `daily_score.json` structuré :

```json
{
  "vehicle_id": "GML-TRUCK-50",
  "date": "2026-06-08",
  "summary": {
    "harsh_braking_count": 3,
    "peak_deceleration": -4.2,
    "safety_rating": "DANGER"
  },
  "events": [
    { "timestamp": "08:00:02", "force_g": -3.1 },
    ...
  ]
}
```

**`safety_rating`** vaut `"SAFE"` si aucun événement n'est détecté, `"DANGER"` sinon.
