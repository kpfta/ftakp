import json
import urllib.request
import ssl
from urllib.error import URLError, HTTPError
from datetime import datetime, timezone, timedelta
import os

# Disable SSL verification globally
ssl._create_default_https_context = ssl._create_unverified_context

# === Configuration ===
BASE = "https://pixelsport.tv"
API_EVENTS = f"{BASE}/backend/liveTV/events"
OUTPUT_FILE_MAIN = "Pixelsports.m3u8"
OUTPUT_FILE_TIVIMATE = "Pixelsports_Tivimate.m3u8"

# Headers
VLC_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0"
ENCODED_UA = "Mozilla%2F5.0%20(Windows%20NT%2010.0%3B%20Win64%3B%20x64%3B%20rv%3A144.0)%20Gecko%2F20100101%20Firefox%2F144.0"
VLC_REFERER = f"{BASE}/"
VLC_ICY = "1"

# League definitions
LEAGUE_INFO = {
    "NFL": ("NFL.Dummy.us", "http://drewlive24.duckdns.org:9000/Logos/Maxx.png", "NFL"),
    "MLB": ("MLB.Baseball.Dummy.us", "http://drewlive24.duckdns.org:9000/Logos/Baseball3.png", "MLB"),
    "NHL": ("NHL.Hockey.Dummy.us", "http://drewlive24.duckdns.org:9000/Logos/Hockey2.png", "NHL"),
    "NBA": ("NBA.Basketball.Dummy.us", "http://drewlive24.duckdns.org:9000/Logos/Basketball-2.png", "NBA"),
    "NASCAR": ("Racing.Dummy.us", "http://drewlive24.duckdns.org:9000/Logos/Motorsports2.png", "NASCAR Cup Series"),
    "UFC": ("UFC.Fight.Pass.Dummy.us", "http://drewlive24.duckdns.org:9000/Logos/CombatSports2.png", "UFC"),
    "SOCCER": ("Soccer.Dummy.us", "http://drewlive24.duckdns.org:9000/Logos/Soccer.png", "Soccer"),
    "BOXING": ("PPV.EVENTS.Dummy.us", "http://drewlive24.duckdns.org:9000/Logos/Combat-Sports.png", "Boxing"),
}

# === Utility Functions ===
def utc_to_eastern(utc_str):
    try:
        utc_dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00")).astimezone(timezone.utc)
        offset = -4 if 3 <= utc_dt.month <= 11 else -5
        et = utc_dt + timedelta(hours=offset)
        return et.strftime("%I:%M %p ET - %m/%d/%Y").replace(" 0", " ")
    except Exception:
        return ""

def get_game_status(utc_str):
    try:
        utc_dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00")).astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        diff = (utc_dt - now).total_seconds()
        if diff < -10800:
            return "Finished"
        elif diff < 0:
            return "Started"
        else:
            hours = int(diff // 3600)
            minutes = int((diff % 3600) // 60)
            return f"In {hours}h {minutes}m" if hours > 0 else f"In {minutes}m"
    except Exception:
        return ""

def fetch_json(url):
    headers = {
        "User-Agent": VLC_USER_AGENT,
        "Referer": VLC_REFERER,
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "Connection": "close",
        "Icy-MetaData": VLC_ICY,
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

def collect_links_with_labels(event):
    links = []
    comp1_home = event.get("competitors1_homeAway", "").lower() == "home"
    for i in range(1, 4):
        key = f"server{i}URL"
        link = event.get("channel", {}).get(key)
        if link and str(link).lower() != "null":
            label = "Home" if (i == 1 and comp1_home) or (i == 2 and not comp1_home) else "Away" if (i == 2 and comp1_home) or (i == 1 and not comp1_home) else "Alt"
            links.append((link, label))
    return links

def get_league_info(league_name):
    for key, (tvid, logo, display) in LEAGUE_INFO.items():
        if key.lower() in league_name.lower():
            return tvid, logo, display
    return ("Pixelsports.Dummy.us", "", "Live Sports")

# === Playlist Builders ===
def build_m3u(events):
    lines = ["#EXTM3U"]
    for ev in events:
        title = ev.get("match_name", "Unknown Event").strip()
        date_str = ev.get("date", "")
        time_et = utc_to_eastern(date_str)
        status = get_game_status(date_str)
        if time_et: title += f" - {time_et}"
        if status: title += f" - {status}"

        league = ev.get("channel", {}).get("TVCategory", {}).get("name", "LIVE")
        tvid, logo, group = get_league_info(league)
        logo = ev.get("competitors1_logo") or logo

        for link, label in collect_links_with_labels(ev):
            lines.append(f'#EXTINF:-1 tvg-id="{tvid}" tvg-logo="{logo}" group-title="Pixelsports - {group} - {label}",{title}')
            lines.append(f"#EXTVLCOPT:http-user-agent={VLC_USER_AGENT}")
            lines.append(f"#EXTVLCOPT:http-referrer={VLC_REFERER}")
            lines.append(f"#EXTVLCOPT:http-icy-metadata={VLC_ICY}")
            lines.append(link)
    return "\n".join(lines)

def build_tivimate(events):
    """Generate playlist with pipe headers for TiviMate."""
    lines = ["#EXTM3U"]
    for ev in events:
        title = ev.get("match_name", "Unknown Event").strip()
        date_str = ev.get("date", "")
        time_et = utc_to_eastern(date_str)
        status = get_game_status(date_str)
        if time_et: title += f" - {time_et}"
        if status: title += f" - {status}"

        league = ev.get("channel", {}).get("TVCategory", {}).get("name", "LIVE")
        tvid, logo, group = get_league_info(league)
        logo = ev.get("competitors1_logo") or logo

        for link, label in collect_links_with_labels(ev):
            lines.append(f'#EXTINF:-1 tvg-id="{tvid}" tvg-logo="{logo}" group-title="Pixelsports - {group} - {label}",{title}')
            lines.append(f"{link}|referer={VLC_REFERER}|origin={BASE}|user-agent={ENCODED_UA}")
    return "\n".join(lines)

# === Main Execution ===
def main():
    print("[*] Fetching live PixelSport events…")
    try:
        data = fetch_json(API_EVENTS)
        events = data.get("events", [])
        if not events:
            print("[-] No events found.")
            return

        # Master M3U (VLC format)
        playlist = build_m3u(events)
        with open(OUTPUT_FILE_MAIN, "w", encoding="utf-8") as f:
            f.write(playlist)
        print(f"[+] Saved main playlist: {OUTPUT_FILE_MAIN}")

        # TiviMate playlist
        playlist_tivi = build_tivimate(events)
        with open(OUTPUT_FILE_TIVIMATE, "w", encoding="utf-8") as f:
            f.write(playlist_tivi)
        print(f"[+] Saved TiviMate playlist: {OUTPUT_FILE_TIVIMATE}")

        # Per-league category playlists
        print("[*] Generating category playlists…")
        leagues = {}
        for ev in events:
            league = ev.get("channel", {}).get("TVCategory", {}).get("name", "Other")
            leagues.setdefault(league, []).append(ev)

        for league_name, league_events in leagues.items():
            _, _, group = get_league_info(league_name)
            safe_name = "".join(c if c.isalnum() else "_" for c in group)
            filename = f"{safe_name}.m3u8"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(build_tivimate(league_events))
            print(f"  [+] Saved: {filename}")

        print("\n✅ All playlists generated successfully.")

    except (URLError, HTTPError) as e:
        print(f"[!] Network error: {e}")
    except Exception as e:
        print(f"[!] Unexpected error: {e}")

if __name__ == "__main__":
    main()
