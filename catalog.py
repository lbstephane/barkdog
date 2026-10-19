"""
Catalogue des nuisances détectables, construit sur les classes AudioSet de YAMNet.

- PROFILES   : ce que l'on veut enregistrer (choix dans la page Réglages)
- EXCLUSIONS : sons qui annulent une détection quand ils dominent (canards confondus avec des aboiements…)
- SPEECH     : voix humaines, pour la protection de la vie privée (masquage)

Les identifiants des trois premiers profils (aboiement, hurlement, grognement) sont
ceux des premières versions : les anciens enregistrements restent compatibles.
« couleur » est un index dans la palette de la page (0 à 9).
"""

PROFILES = [
    # --- Animaux
    {"id": "aboiement", "label": "Aboiements", "label_en": "Barking", "groupe": "Animaux", "couleur": 0, "defaut": True,
     "classes": ["Bark", "Bow-wow", "Yip", "Dog", "Canidae, dogs, wolves"]},
    {"id": "hurlement", "label": "Hurlements", "label_en": "Howling", "groupe": "Animaux", "couleur": 1, "defaut": True,
     "classes": ["Howl"]},
    {"id": "grognement", "label": "Grognements, gémissements", "label_en": "Growling, whimpering", "groupe": "Animaux", "couleur": 2, "defaut": True,
     "classes": ["Growling", "Whimper (dog)"]},
    {"id": "coq", "label": "Chant du coq", "label_en": "Rooster crowing", "groupe": "Animaux", "couleur": 3,
     "classes": ["Crowing, cock-a-doodle-doo", "Chicken, rooster"]},
    {"id": "chat", "label": "Miaulements, chats en chaleur", "label_en": "Meowing, cats in heat", "groupe": "Animaux", "couleur": 4,
     "classes": ["Meow", "Caterwaul", "Cat"]},
    # --- Activités humaines
    {"id": "musique", "label": "Musique", "label_en": "Music", "groupe": "Activités humaines", "couleur": 5,
     "classes": ["Music", "Pop music", "Hip hop music", "Rock music", "Electronic music", "House music",
                 "Electronic dance music", "Dance music", "Drum and bass", "Techno"]},
    {"id": "basses", "label": "Basses, percussions", "label_en": "Bass, drums", "groupe": "Activités humaines", "couleur": 6,
     "classes": ["Bass drum", "Drum kit", "Drum machine", "Drum", "Bass guitar"]},
    {"id": "travaux", "label": "Bricolage, travaux", "label_en": "DIY, construction work", "groupe": "Activités humaines", "couleur": 7,
     "classes": ["Power tool", "Drill", "Jackhammer", "Hammer", "Sawing"]},
    {"id": "petards", "label": "Pétards, feux d'artifice", "label_en": "Firecrackers, fireworks", "groupe": "Activités humaines", "couleur": 8,
     "classes": ["Fireworks", "Firecracker", "Explosion"]},
    # --- Moteurs et alarmes
    {"id": "jardinage", "label": "Tondeuse, tronçonneuse", "label_en": "Lawn mower, chainsaw", "groupe": "Moteurs et alarmes", "couleur": 9,
     "classes": ["Lawn mower", "Chainsaw"]},
    {"id": "deux_roues", "label": "Motos, scooters", "label_en": "Motorbikes, scooters", "groupe": "Moteurs et alarmes", "couleur": 3,
     "classes": ["Motorcycle"]},
    {"id": "alarme", "label": "Alarmes, sirènes", "label_en": "Alarms, sirens", "groupe": "Moteurs et alarmes", "couleur": 4,
     "classes": ["Car alarm", "Alarm", "Siren", "Smoke detector, smoke alarm"]},
    {"id": "klaxon", "label": "Klaxons", "label_en": "Horns", "groupe": "Moteurs et alarmes", "couleur": 5,
     "classes": ["Vehicle horn, car horn, honking", "Air horn, truck horn"]},
]

# Pseudo-profil : déclenchement sur le niveau sonore seul (réglage audio.seuil_niveau_dbfs)
LEVEL_PROFILE = {"id": "niveau", "label": "Niveau sonore élevé", "label_en": "High sound level", "groupe": "Niveau", "couleur": 7, "classes": []}

EXCLUSIONS = [
    {"id": "canards", "label": "Canards, oies", "label_en": "Ducks, geese", "defaut": True,
     "classes": ["Duck", "Quack", "Goose", "Honk"]},
    {"id": "oiseaux", "label": "Oiseaux chanteurs", "label_en": "Songbirds",
     "classes": ["Bird vocalization, bird call, bird song", "Chirp, tweet", "Bird"]},
    {"id": "meteo", "label": "Vent, pluie, orage", "label_en": "Wind, rain, thunder",
     "classes": ["Wind", "Wind noise (microphone)", "Rain", "Rain on surface", "Raindrop", "Thunder", "Thunderstorm"]},
    {"id": "circulation", "label": "Circulation (voitures, camions)", "label_en": "Traffic (cars, trucks)",
     "classes": ["Vehicle", "Motor vehicle (road)", "Car", "Truck"]},
]

# Voix humaines : masquées dans les fichiers (vie privée, art. 226-1 du Code pénal)
SPEECH = ["Speech", "Child speech, kid speaking", "Conversation", "Narration, monologue", "Babbling",
          "Whispering", "Hubbub, speech noise, speech babble", "Shout", "Yell"]

PROFILE_IDS = [p["id"] for p in PROFILES]
EXCLUSION_IDS = [e["id"] for e in EXCLUSIONS]


def profile(pid):
    if pid == LEVEL_PROFILE["id"]:
        return LEVEL_PROFILE
    return next((p for p in PROFILES if p["id"] == pid), None)


def public():
    """Ce que la page web a besoin de connaître (sans les classes internes inutiles)."""
    return {
        "profils": [{k: p.get(k) for k in ("id", "label", "label_en", "groupe", "couleur", "defaut")} for p in PROFILES]
                   + [{k: LEVEL_PROFILE[k] for k in ("id", "label", "label_en", "groupe", "couleur")}],
        "exclusions": [{k: e.get(k) for k in ("id", "label", "label_en", "defaut")} for e in EXCLUSIONS],
    }
