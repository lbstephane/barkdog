#!/usr/bin/env bash
# Installation / mise à jour sur Raspberry Pi OS 64 bits (Bookworm, Trixie), à lancer depuis le dossier du projet.
# Peut être relancé sans risque : enregistrements, mot de passe et réglages sont conservés.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
SVC_USER="${SUDO_USER:-$USER}"
[ "$SVC_USER" = "root" ] && { echo "Lancer en utilisateur normal (pas root) : ./install.sh"; exit 1; }

echo "== Paquets système"
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip libportaudio2 alsa-utils

echo "== Environnement Python"
# Un .venv copié ou déplacé garde ses anciens chemins : on le recrée s'il ne fonctionne plus
if [ -d .venv ] && ! .venv/bin/python -c "import sys" 2>/dev/null; then rm -rf .venv; fi
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install numpy sounddevice scipy
# Moteur d'inférence : ai-edge-litert (successeur de tflite-runtime, dispo pour Python 3.13) ;
# tflite-runtime seulement en secours, pour les anciens systèmes.
if ! .venv/bin/python -c "import ai_edge_litert.interpreter" 2>/dev/null \
   && ! .venv/bin/python -c "import tflite_runtime.interpreter" 2>/dev/null; then
  .venv/bin/python -m pip install ai-edge-litert 2>/dev/null || .venv/bin/python -m pip install tflite-runtime
fi

echo "== Modèle YAMNet"
[ -f yamnet.tflite ] || wget -O yamnet.tflite \
  "https://storage.googleapis.com/download.tensorflow.org/models/tflite/task_library/audio_classification/android/lite-model_yamnet_classification_tflite_1.tflite"
[ -f yamnet_class_map.csv ] || wget -O yamnet_class_map.csv \
  "https://raw.githubusercontent.com/tensorflow/models/master/research/audioset/yamnet/yamnet_class_map.csv"

echo "== Heure (le Pi n'a pas d'horloge sauvegardée : NTP indispensable pour l'horodatage)"
sudo timedatectl set-timezone "${TZ_NAME:-Europe/Paris}"
sudo timedatectl set-ntp true

echo "== Réglages"
mkdir -p enregistrements config
chmod 700 config
.venv/bin/python config.py --out config/config.json

echo "== Mot de passe de la page web"
if ! .venv/bin/python auth.py --status >/dev/null 2>&1; then
  if [ -t 0 ]; then
    .venv/bin/python auth.py --set
  else
    echo "!! Aucun mot de passe : lancer « .venv/bin/python auth.py --set » avant d'ouvrir la page."
  fi
fi

echo "== Services (cloisonnés par systemd)"
sudo tee /etc/systemd/system/barkdog.service >/dev/null <<EOF
[Unit]
Description=BarkDog - enregistreur de nuisances sonores
After=network-online.target time-sync.target sound.target
Wants=network-online.target

[Service]
User=$SVC_USER
SupplementaryGroups=audio
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/python $DIR/bark_logger.py --out $DIR/enregistrements --config $DIR/config/config.json
Restart=always
RestartSec=5
TimeoutStopSec=30
# Cloisonnement : écriture limitée aux enregistrements et aux réglages, aucun réseau, aucun privilège
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$DIR/enregistrements $DIR/config
PrivateTmp=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
LockPersonality=yes
RestrictAddressFamilies=AF_UNIX

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/barkdog-web.service >/dev/null <<EOF
[Unit]
Description=BarkDog - page web
After=network-online.target
Wants=network-online.target

[Service]
User=$SVC_USER
WorkingDirectory=$DIR
ExecStart=/usr/bin/python3 $DIR/web.py --out $DIR/enregistrements --config-dir $DIR/config --port ${WEB_PORT:-8080}
Restart=always
RestartSec=5
# Cloisonnement (sans NoNewPrivileges : le bouton marche/arrêt passe par sudo, voir /etc/sudoers.d/barkdog)
ProtectSystem=full
ProtectHome=read-only
ReadWritePaths=$DIR/enregistrements $DIR/config
PrivateTmp=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
LockPersonality=yes
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6

[Install]
WantedBy=multi-user.target
EOF

# Autorise la page web à démarrer / arrêter l'écoute, et rien d'autre
SC=$(command -v systemctl)
TMP=$(mktemp)
cat > "$TMP" <<EOF
# Pilotage de l'écoute depuis la page web (installé par BarkDog, install.sh)
$SVC_USER ALL=(root) NOPASSWD: $SC start barkdog, $SC stop barkdog
EOF
if sudo visudo -cf "$TMP" >/dev/null; then
  sudo install -m 440 -o root -g root "$TMP" /etc/sudoers.d/barkdog
else
  echo "Règle sudo invalide : bouton marche/arrêt désactivé"
fi
rm -f "$TMP"

sudo systemctl daemon-reload
sudo systemctl enable barkdog.service barkdog-web.service
sudo systemctl restart barkdog.service barkdog-web.service
sleep 3
systemctl is-active --quiet barkdog || echo "!! L'écoute n'a pas démarré : journalctl -u barkdog -n 30"
echo
echo "OK. Page web : http://$(hostname).local:${WEB_PORT:-8080}  (ou http://$(hostname -I | awk '{print $1}'):${WEB_PORT:-8080})"
echo "Réglages : depuis la page (section Réglages) ou $DIR/config/config.json"
echo "Suivi en direct : journalctl -u barkdog -f"
