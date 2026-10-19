# BarkDog 🐕 — a noise nuisance log on a Raspberry Pi

🇬🇧 **English** · 🇫🇷 [Français](README.fr.md)

[![pipeline](https://gitlab.com/lbstephane/barkdog/badges/main/pipeline.svg)](https://gitlab.com/lbstephane/barkdog/-/pipelines)

Website: **[barkdog.fr](https://barkdog.fr)** · Development, issues and contributions on **[GitLab](https://gitlab.com/lbstephane/barkdog)** (the GitHub repository is a mirror).

**BarkDog** is a standalone recorder for the Raspberry Pi. It listens continuously, recognises the nuisances you pick with an on-device AI (barking, howling, roosters, music, construction work, fireworks…) and keeps only the episodes. Each episode is **timestamped, categorised and sealed with a SHA-256 fingerprint**. A web page lets you browse everything from your phone.

![BarkDog in 36 seconds](docs/barkdog.mp4)

Vertical version for social media: [docs/barkdog-vertical.mp4](docs/barkdog-vertical.mp4).

The goal: build a factual record (dates, times, durations, repetition, night or day) without spending your nights holding a voice recorder.

> **This is not a measuring instrument.** Levels are relative (uncalibrated microphone). The tool helps document a nuisance, but it replaces neither a regulatory acoustic measurement nor an official report by a bailiff or similar authority.

## Features

- **Local AI detection**: [YAMNet](https://github.com/tensorflow/models/tree/master/research/audioset/yamnet) (Google, 521 AudioSet sound classes), analysis every 0.5 s. No sound ever leaves the box.
- **Choose your nuisances** in the web page, with an optional threshold per nuisance. **Sounds to ignore**: ducks, birds, rain, traffic… **Optional trigger on sound level** alone.
- **Complete episodes**: the seconds before the trigger are kept, and the episode closes after an adjustable quiet time. An isolated sound can be discarded (minimum number of detections), but it is still logged.
- **Timeline** in every file: one lane per category and “0:34 howling” buttons to jump straight to the right moment.
- **Privacy**: passages where the AI hears a human voice are **silenced** in the files (on by default) and flagged on the timeline.
- **Traceability**: SHA-256 fingerprint of every WAV file; identifier of the settings used; history of starts, stops, settings changes, deletions and test modes; log of discarded episodes.
- **Web page** for iPhone and Android:
  - listening status, start / stop button;
  - “recording” banner, list that updates on its own;
  - filters, statistics per day and at night, CSV exports;
  - annotations (false positive, notes) and trash;
  - **test mode** with live AI scores, without recording;
  - interface in **English or French**, selectable in Settings.
- **Hardened**: hashed password, signed session, anti-CSRF, strict CSP, rate limiting, sandboxed systemd services (see [Security](#security)).

## Hardware

| | Recommended | Notes |
|---|---|---|
| Board | **Raspberry Pi Zero 2 W**, 3, 4 or 5 | **Raspberry Pi OS 64-bit** required (Lite is enough). |
| Microphone | **USB microphone** (USB lavalier mic, or USB sound card plus mic) | Avoid conference microphones with “noise reduction”: they erase distant barking. The 3.5 mm jack on the Pi 3 and Pi 4 is **output only**. |
| Power supply | 5 V 2.5 A (Pi 3 / Zero 2 W), 5 V 3 A USB-C (Pi 4) | A 1 A supply is enough to prevent booting. |
| Storage | 16 GB microSD card | About 1.9 MB per recorded minute. |

Good to know:
- **Pi Zero 2 W**: a single USB data port (OTG adapter needed for the mic), 2.4 GHz Wi-Fi only. In a weatherproof enclosure, watch out for heat in the sun: plan for shade, a light colour and baffled ventilation.
- **Electrical hum**: with a switching power supply or a USB ground loop you hear harmonics of the mains frequency (150, 250, 350 Hz… on 50 Hz grids). The 200 Hz high-pass filter removes the lowest ones. If the buzz persists, change the power supply (the official one if possible) or add a USB isolator, a powered hub or a ferrite on the mic cable.
- **Time**: the Pi has no battery-backed clock. It needs network access at boot (NTP), or a DS3231 RTC module. The page warns when the clock is not synchronised.

## Installation

```bash
git clone https://gitlab.com/lbstephane/barkdog.git ~/barkdog
cd ~/barkdog
./install.sh
```

The script installs the dependencies and the model, sets the time zone (`TZ_NAME=Europe/London ./install.sh` to choose yours, Europe/Paris by default), asks for the web page password and creates two services started at boot:
- `barkdog`: listening;
- `barkdog-web`: the web page, on port 8080.

**USB microphone that only does 48 kHz** (common): let ALSA convert to 16 kHz. Create `/etc/asound.conf` with the card name given by `arecord -l`, then choose the “default” microphone in Settings:

```
pcm.!default { type asym capture.pcm "mic" playback.pcm "plughw:0,0" }
pcm.mic { type plug slave.pcm "hw:CARD=Device,DEV=0" }
```

**Update**: `git pull && ./install.sh`. Recordings, password and settings are kept.

## Usage

Open **http://\<pi-name\>.local:8080** from your home Wi-Fi. On iPhone, use “Share → Add to Home Screen”.

1. **Settings** (gear icon): tick the nuisances, adjust the microphone, gain and filter, pick the language. Changes apply within seconds without stopping listening; only a microphone change restarts it, for about 10 s.
2. **Test mode**: shows live scores against the thresholds, the level, what the AI “hears” and voice detections. By default nothing is recorded during the test. The pause expires on its own 5 min after the page is closed, and after at most 30 min of testing.
3. **Episodes**: playback, timeline, annotations, trash. Days fold and unfold; today and yesterday are open by default. Permanent deletion is only possible from the trash, and the line stays in the raw log.

**Remote access**: do **not** open a port on your router. Use a VPN: [Tailscale](https://tailscale.com) (nothing to configure on the router) or WireGuard.
- With Tailscale, `sudo tailscale serve --bg 8080` adds HTTPS. The session cookie then becomes `Secure`.
- Remember to disable key expiry for the box in the Tailscale console.

## Files produced

Data file names are in French (the project started in France); their format is documented here.

```
enregistrements/                 # recordings
  2026-10-16/
    2026-10-16_05h42m10s_aboiement+hurlement.wav   # the episode (16 kHz mono); aboiement = barking, hurlement = howling
    2026-10-16_05h42m10s_aboiement+hurlement.json  # timeline + masked speech passages
  journal_evenements.csv     # 1 line per episode: times, categories, scores, SHA-256, settings
  episodes_ignores.csv       # discarded episodes (too short, speech…): nothing is dropped silently
  historique_ecoute.csv      # starts, stops, settings, deletions, test mode, sign-ins
  annotations.json           # false positives, notes, trash (the log is never modified)
  corbeille/                 # trash
config/                      # (0700) settings, hashed password, session key
```

Command-line tools:
- `.venv/bin/python reanalyse.py [--force]` rebuilds timelines with the current settings;
- `.venv/bin/python rapport.py` prints a daily summary;
- `.venv/bin/python auth.py --set` changes the password.

## Security

Threat model: the page is meant for the **local network and a VPN**, never for direct Internet exposure. It gives access to sensitive recordings, and lets you delete files and stop listening.

- **Authentication**:
  - password hashed with PBKDF2-SHA256 (200,000 iterations, random salt), file in mode 0600;
  - session as an HMAC-SHA256 signed token, valid 30 days, in an `HttpOnly`, `SameSite=Strict` cookie;
  - changing the password ends all sessions;
  - 5 failures in 15 min block the address.
- **Anti-CSRF**: every POST request requires an application header and a matching origin; the sign-in itself is protected.
- **Headers**: CSP without inline scripts, `frame-ancestors 'none'`, `nosniff`, `no-referrer`. The server signature reveals no version.
- **Paths**: files are confined to the recordings folder, resolved then checked; download names are sanitised.
- **systemd**:
  - listening runs unprivileged (`NoNewPrivileges`), without network (`AF_UNIX` only), on a read-only file system except for data and settings;
  - the web page is sandboxed the same way, except for `NoNewPrivileges`, which the start / stop button needs.
- **sudo**: a single rule, limited to `systemctl start|stop barkdog`.
- **Traceability**: sign-ins, settings, deletions and start / stop are written to the history; refusals appear in `journalctl -u barkdog-web`.

Found a vulnerability? Please report it privately before any publication, with a [confidential issue on GitLab](https://gitlab.com/lbstephane/barkdog/-/issues/new) (tick “This issue is confidential”).

## Privacy and legal framework

- In many countries, recording **other people's private conversations** without their consent is a criminal offence (in France, article 226-1 of the Penal Code). Speech masking is on by default. Turning it off is your responsibility.
- Point the microphone at the source of the nuisance, not at homes or public walkways.
- Noise rules vary by country. In France, behavioural noise (animals, shouting, music…) is assessed on its **duration, repetition or intensity**, while activity noise requires a sound-level meter measurement. The log helps make repetition and timing objective. For any proceedings, seek advice from a mediator, a lawyer or the competent local authority.

## Development

```bash
python3 -m unittest discover -s tests          # 34 tests, no hardware or model needed (simulated mic and AI)
python3 tests/demo.py --out /tmp/demo/enregistrements --config /tmp/demo/config/config.json --speed 4
python3 auth.py --config-dir /tmp/demo/config --set
python3 web.py --out /tmp/demo/enregistrements --config-dir /tmp/demo/config --no-service-control
```

The demo runs the real recorder with a fake microphone and a fake model. Its looping scenario includes howling then barking, a voice, ducks and an isolated bark.

Code layout:

| File | Role |
|---|---|
| `catalog.py` | Nuisances, exclusions and speech classes (mapping to YAMNet), labels in French and English. |
| `config.py` | Settings (`config/config.json`): validation, fingerprint, differences. |
| `bark_logger.py` | Recorder: detection, episodes, speech masking, log. |
| `web.py`, `auth.py`, `static/` | Web page, Python standard library only. Translations in `static/i18n.js`. |

Translations: the interface is in French by default and switches to English based on the browser language or the choice in Settings. To add or fix a translation, edit the dictionary in `static/i18n.js` (keys are the French texts).

## Support

BarkDog is free. If it helps you, you can [buy me a coffee on Ko-fi](https://ko-fi.com/revolution3d). Bug reports and contributions: [issues](https://gitlab.com/lbstephane/barkdog/-/issues) and merge requests on GitLab.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## Licence

[MIT](LICENSE), without warranty of any kind. You alone are responsible for how the recordings are used, in particular with regard to other people's privacy.

The YAMNet model and class map (`tests/data/yamnet_class_map.csv`) are published by Google under the Apache 2.0 licence. The model is downloaded at installation and is not redistributed in this repository.
