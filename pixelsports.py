import json
import urllib.request
import ssl
from urllib.error import URLError, HTTPError
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

# Disable SSL certificate verification globally
ssl._create_default_https_context = ssl._create_unverified_context

BASE = "https://pixelsport.tv"
API_EVENTS = f"{BASE}/backend/liveTV/events"

OUTPUT_FILE = "Pixelsports.m3u8"
TIVIMATE_FILE = "Pixelsports_Tivimate.m3u8"
CATEGORIES_FILE = "Pixelsports_categories.txt"

# User-Agent for VLC / Tivimate
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0"
ENCODED_UA = quote(USER_AGENT)
REFERER = f"{BASE}/"
ICY = "1"

# League info for logos and grouping
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

def utc_to_eastern(utc_str):
    """Convert ISO UTC time string to Eastern Time (ET) and return formatted string."""
    try:
        utc_dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00")).astimezone(timezone.utc)
        month = utc_dt.month
        offset = -4 if 3 <= month <= 11 else -5
        et = utc_dt + timedelta(hours=offset)
        return et.strftime("%I:%M %p ET - %m/%d/%Y").replace(" 0", " ")
    except Exception:
        return ""

def get_game_status(utc_str):
    """Return game status: Finished, Started, or countdown."""
    try:
        utc_dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00")).astimezone(timezone.utc)
        now = datetime.now(timezone.utc)
        time_diff = (utc_dt - now).total_seconds()
        if time_diff < -10800:
            return "Finished"
        elif time_diff < 0:
            return "Started"
        else:
            hours = int(time_diff // 3600)
            minutes = int((time_diff % 3600) // 60)
            return f"In {hours}h {minutes}m" if hours > 0 else f"In {minutes}m"
    except Exception:
        return ""

def fetch_json(url):
    """Fetch JSON data from URL."""
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": REFERER,
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "Connection": "close",
        "Icy-MetaData": ICY,
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

def collect_links_with_labels(event):
    """Collect valid stream URLs with labels (Home/Away/Alt)."""
    links = []
    comp1_home = event.get("competitors1_homeAway", "").lower() == "home"
    for i in range(1, 4):
        key = f"server{i}URL"
        try:
            link = event["channel"][key]
            if link and link.lower() != "null":
                label = "Home" if (i == 1 and comp1_home) else "Away" if (i == 2 and comp1_home) else "Alt"
                links.append((link, label))
        except KeyError:
            continue
    return links

def get_league_info(league_name):
    """Return tvg-id, logo, and display name."""
    for key, (tvid, logo, display_name) in LEAGUE_INFO.items():
        if key.lower() in league_name.lower():
            return tvid, logo, display_name
    return ("Pixelsports.Dummy.us", "", "Live Sports")

def build_m3u(events):
    """Generate standard M3U8 playlist."""
    lines = ["#EXTM3U"]
    categories_set = set()
    for ev in events:
        title = ev.get("match_name", "Unknown Event").strip()
        logo = ev.get("competitors1_logo", "")
        date_str = ev.get("date")
        time_et = utc_to_eastern(date_str)
        status = get_game_status(date_str)
        if time_et:
            title = f"{title} - {time_et}"
        if status:
            title = f"{title} - {status}"
        league = ev.get("channel", {}).get("TVCategory", {}).get("name", "LIVE")
        tvid, group_logo, group_display = get_league_info(league)
        categories_set.add(group_display)
        if not logo:
            logo = group_logo
        for link, label in collect_links_with_labels(ev):
            lines.append(f'#EXTINF:-1 tvg-id="{tvid}" tvg-logo="{logo}" group-title="Pixelsports - {group_display} - {label}",{title}')
            lines.append(link)
    return "\n".join(lines), sorted(categories_set)

def build_tivimate(events):
    """Generate Tivimate-compatible playlist with pipe headers."""
    lines = ["#EXTM3U"]
    for ev in events:
        title = ev.get("match_name", "Unknown Event").strip()
        logo = ev.get("competitors1_logo", "")
        date_str = ev.get("date")
        time_et = utc_to_eastern(date_str)
        status = get_game_status(date_str)
        if time_et:
            title = f"{title} - {time_et}"
        if status:
            title = f"{title} - {status}"
        league = ev.get("channel", {}).get("TVCategory", {}).get("name", "LIVE")
        tvid, group_logo, group_display = get_league_info(league)
        if not logo:
            logo = group_logo
        for link, label in collect_links_with_labels(ev):
            header = f"referer={REFERER}/|origin={REFERER}|user-agent={ENCODED_UA}"
            lines.append(f'#EXTINF:-1 tvg-id="{tvid}" tvg-logo="{logo}" group-title="Pixelsports - {group_display} - {label}",{title}')
            lines.append(f"{link}?{header}")
    return "\n".join(lines)

def main():
    print("[*] Fetching PixelSport live events…")
    try:
        data = fetch_json(API_EVENTS)
        events = data.get("events", [])
        if not events:
            print("[-] No live events found.")
            return

        # Standard playlist + categories
        playlist, categories = build_m3u(events)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(playlist)
        with open(CATEGORIES_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(categories))

        # Tivimate playlist
        tivimate_playlist = build_tivimate(events)
        with open(TIVIMATE_FILE, "w", encoding="utf-8") as f:
            f.write(tivimate_playlist)

        print(f"[+] Saved playlist: {OUTPUT_FILE} ({len(events)} events)")
        print(f"[+] Saved Tivimate playlist: {TIVIMATE_FILE}")
        print(f"[+] Saved categories: {CATEGORIES_FILE}")
    except (URLError, HTTPError) as e:
        print(f"[!] Error fetching data: {e}")
    except Exception as e:
        print(f"[!] Unexpected error: {e}")

if __name__ == "__main__":
    main()
