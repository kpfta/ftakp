import json
import urllib.request
import ssl
from urllib.error import URLError, HTTPError
from datetime import datetime, timezone, timedelta
import urllib.parse

# Disable SSL certificate verification globally
ssl._create_default_https_context = ssl._create_unverified_context

BASE = "https://pixelsport.tv"
API_EVENTS = f"{BASE}/backend/liveTV/events"

OUTPUT_STANDARD = "Pixelsports.m3u8"
OUTPUT_TIVIMATE = "Pixelsports_Tivimate.m3u8"
OUTPUT_CATEGORIES = "Pixelsports_categories.txt"

VLC_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0"
VLC_REFERER = f"{BASE}/"
VLC_ICY = "1"

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
    try:
        utc_dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00")).astimezone(timezone.utc)
        month = utc_dt.month
        offset = -4 if 3 <= month <= 11 else -5
        et = utc_dt + timedelta(hours=offset)
        return et.strftime("%I:%M %p ET - %m/%d/%Y").replace(" 0", " ")
    except Exception:
        return ""

def get_game_status(utc_str):
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
            if hours > 0:
                return f"In {hours}h {minutes}m"
            else:
                return f"In {minutes}m"
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
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

def collect_links_with_labels(event):
    links = []
    comp1_home = event.get("competitors1_homeAway", "").lower() == "home"
    for i in range(1, 4):
        key = f"server{i}URL"
        try:
            link = event["channel"][key]
            if link and link.lower() != "null":
                if i == 1:
                    label = "Home" if comp1_home else "Away"
                elif i == 2:
                    label = "Away" if comp1_home else "Home"
                else:
                    label = "Alt"
                links.append((link, label))
        except KeyError:
            continue
    return links

def get_league_info(league_name):
    for key, (tvid, logo, display_name) in LEAGUE_INFO.items():
        if key.lower() in league_name.lower():
            return tvid, logo, display_name
    return ("Pixelsports.Dummy.us", "", "Live Sports")

def build_standard_m3u(events):
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
            lines.append(f'#EXTINF:-1 tvg-id="{tvid}" tvg-logo="{logo}" group-title="Pixelsports - {group_display} - {label}",{title}')
            lines.append(f"#EXTVLCOPT:http-user-agent={VLC_USER_AGENT}")
            lines.append(f"#EXTVLCOPT:http-referrer={VLC_REFERER}")
            lines.append(f"#EXTVLCOPT:http-icy-metadata={VLC_ICY}")
            lines.append(link)
    return "\n".join(lines)

def build_tivimate_m3u(events):
    ua_encoded = urllib.parse.quote(VLC_USER_AGENT)
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
        if not logo:
            logo = group_logo
        categories_set.add(group_display)
        for link, label in collect_links_with_labels(ev):
            # Tivimate-style headers
            tiv_headers = f"referer={VLC_REFERER}|origin={VLC_REFERER}|user-agent={ua_encoded}"
            lines.append(f'#EXTINF:-1 tvg-id="{tvid}" tvg-logo="{logo}" group-title="Pixelsports - {group_display} - {label}",{title}')
            lines.append(f"{link}|{tiv_headers}")
    return "\n".join(lines), categories_set

def main():
    print("[*] Fetching PixelSport live events…")
    try:
        data = fetch_json(API_EVENTS)
        events = data.get("events", [])
        if not events:
            print("[-] No live events found.")
            return

        # Standard M3U
        playlist_standard = build_standard_m3u(events)
        with open(OUTPUT_STANDARD, "w", encoding="utf-8") as f:
            f.write(playlist_standard)
        print(f"[+] Saved playlist: {OUTPUT_STANDARD} ({len(events)} events)")

        # Tivimate M3U
        playlist_tivimate, categories = build_tivimate_m3u(events)
        with open(OUTPUT_TIVIMATE, "w", encoding="utf-8") as f:
            f.write(playlist_tivimate)
        print(f"[+] Saved Tivimate playlist: {OUTPUT_TIVIMATE} ({len(events)} events)")

        # Categories list
        with open(OUTPUT_CATEGORIES, "w", encoding="utf-8") as f:
            for cat in sorted(categories):
                f.write(f"{cat}\n")
        print(f"[+] Saved categories list: {OUTPUT_CATEGORIES} ({len(categories)} categories)")

    except (URLError, HTTPError) as e:
        print(f"[!] Error fetching data: {e}")
    except Exception as e:
        print(f"[!] Unexpected error: {e}")

if __name__ == "__main__":
    main()
