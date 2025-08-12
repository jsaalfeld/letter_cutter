# Letter Cutter Generator

Dieses Tool erzeugt **STL-Dateien für Buchstaben-Ausstecher** (z. B. für Ton, Kekse oder andere Werkstoffe) mit automatischen Brücken für innere Flächen (z. B. beim Buchstaben „A“ oder „O“).  
Die Brücken verbinden innere Inseln mit der Außenkontur, sodass der Ausstecher aus einem Stück besteht.

## Features

- Erzeugt direkt eine druckbare STL aus einem einzelnen Buchstaben.
- Liest TTF/OTF-Schriften (alle auf dem System installierten Fonts nutzbar).
- Automatische Erkennung von Innenlöchern und Hinzufügen von Brücken.
- Einstellbare Wandstärke, Höhe, Lippe, Bodenplatte, Schrumpf-Skalierung.
- Wahl, ob die scharfe Schneidlippe **unten** (Ton) oder **oben** (Kekse) sitzt.
- Optionaler Verstärkungsring am oberen Ende für besseren Griff.

## Installation

```bash
pip install -r requirements.txt
```

## Nutzung

```bash
python letter_cutter.py -t A -o cutter_A.stl
```

**Wichtige Parameter:**

| Parameter        | Bedeutung |
|------------------|-----------|
| `-t` / `--text`  | Einzelner Buchstabe oder Zeichen |
| `-f` / `--font`  | Pfad zur TTF/OTF-Schriftdatei |
| `--size`         | Schriftgröße in mm |
| `--wall`         | Wandstärke in mm |
| `--height`       | Wandhöhe ohne Boden in mm |
| `--edge`         | Höhe der scharfen Lippe |
| `--base`         | Bodenstärke in mm |
| `--clearance`    | Spiel innen (für leichteres Lösen des Tons) |
| `--bridge`       | Breite der Brücken |
| `--lip-pos`      | `bottom` oder `top` |
| `--top-cap`      | Höhe eines oberen Verstärkungsrings in mm |
| `--scale`        | Skalierung für Schrumpfausgleich (z. B. 1.08) |
| `-o` / `--output`| Ausgabedatei (STL) |

## Beispiele

- **Ton-Ausstecher** (schneidend unten, verstärkt oben):
  ```bash
  python letter_cutter.py -t A --lip-pos bottom --top-cap 1.0 -o cutter_A.stl
  ```

- **Keks-Ausstecher** (schneidend oben, ohne Verstärkung):
  ```bash
  python letter_cutter.py -t A --lip-pos top -o cutter_A_top.stl
  ```

- **Mit Schrumpfausgleich (8 %)**:
  ```bash
  python letter_cutter.py -t A --scale 1.08 -o cutter_A_scaled.stl
  ```

## Tipps für den 3D-Druck

- Material: PLA oder PETG. PETG ist robuster und wasserfester.
- Layerhöhe: 0,2 mm
- Perimeter: 4–5 für stabile Wände
- Infill: 15–20 %
- Brim empfohlen für große Buchstaben

