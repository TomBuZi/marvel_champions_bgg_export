"""Client für die (inoffizielle) JSON-API von marvelchampionstracker.com.

Die Endpunkte stammen aus dem JavaScript der Website; die API ist nicht dokumentiert und
kann sich ändern. Alle Schreibzugriffe brauchen den CSRF-Token einer eingeloggten Seite.
"""

import os
import re
import time

import requests

BASE_URL = "https://marvelchampionstracker.com"
CSRF_RE = re.compile(r'const csrf_token = "([^"]+)"')
RETRY_STATUS = {429, 500, 502, 503, 504}


class TrackerError(Exception):
    pass


class AuthError(TrackerError):
    pass


class TrackerClient:
    """Anmeldung per E-Mail/Passwort (bevorzugt) oder per Cookie-Datei aus dem Browser."""

    def __init__(self, email=None, password=None, cookie_file=None, base_url=BASE_URL, delay=1.0):
        self.email, self.password = email, password
        self.base_url = base_url.rstrip("/")
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; mc-tracker-sync)",
            # Flask-WTF prüft bei HTTPS, dass der Referer von derselben Origin kommt
            "Referer": self.base_url + "/",
        })
        self._csrf = None
        self._last_request = 0.0
        if cookie_file:
            self._load_cookie_file(cookie_file)

    @classmethod
    def from_env(cls):
        email = os.environ.get("TRACKER_EMAIL")
        password = os.environ.get("TRACKER_PASSWORD")
        cookie_file = os.environ.get("TRACKER_COOKIE_FILE")
        if not (email and password) and not cookie_file:
            raise AuthError("TRACKER_EMAIL und TRACKER_PASSWORD (oder TRACKER_COOKIE_FILE) setzen")
        return cls(email, password, cookie_file, delay=float(os.environ.get("TRACKER_DELAY", "1.0")))

    def _load_cookie_file(self, path):
        """Datei mit einer Zeile 'Cookie: session=…; remember_token=…' (aus den Browser-DevTools)."""
        with open(path, encoding="utf-8-sig") as f:
            header = f.read().strip()
        header = re.sub(r"^cookie:\s*", "", header, flags=re.IGNORECASE)
        domain = re.sub(r"^https?://", "", self.base_url)
        for part in header.split(";"):
            if "=" in part:
                name, value = part.strip().split("=", 1)
                self.session.cookies.set(name, value, domain=domain)

    # --- HTTP -----------------------------------------------------------------------------

    def _request(self, method, path, **kwargs):
        """Gedrosselte Anfrage ohne Redirects; wiederholt bei 429/5xx und Verbindungsfehlern
        mit wachsender Pause — außer POST bei Verbindungsfehlern (siehe unten)."""
        for attempt in range(5):
            wait = self.delay - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            try:
                response = self.session.request(method, self.base_url + path,
                                                allow_redirects=False, timeout=60, **kwargs)
            except requests.RequestException as e:
                self._last_request = time.monotonic()
                # POST nicht wiederholen: der Server hat das Log evtl. trotz Timeout angelegt.
                # Der nächste Sync erkennt es am Marker bzw. löscht ein Duplikat.
                if method == "POST" or attempt == 4:
                    raise TrackerError(f"{method} {path}: {e}") from e
                time.sleep(5 * 2 ** attempt)
                continue
            self._last_request = time.monotonic()
            if response.status_code not in RETRY_STATUS or attempt == 4:
                return response
            time.sleep(5 * 2 ** attempt)

    def _csrf_from(self, response, what):
        match = CSRF_RE.search(response.text) if response.status_code == 200 else None
        if not match:
            raise AuthError(f"{what}: kein CSRF-Token (HTTP {response.status_code}) — Anmeldung abgelaufen?")
        return match.group(1)

    def login(self):
        if self.email and self.password:
            token = self._csrf_from(self._request("GET", "/login/"), "Login-Seite")
            response = self._request("POST", "/login/submit/", headers={"X-CSRFToken": token},
                                     json={"email": self.email, "password": self.password,
                                           "remember_me": True})
            if response.status_code != 200:
                raise AuthError(f"Login fehlgeschlagen (HTTP {response.status_code}): {response.text[:300]}")
        # CSRF-Token der eingeloggten Sitzung; bei einer Weiterleitung zum Login ist sie ungültig
        self._csrf = self._csrf_from(self._request("GET", "/game-logs/add-new/"), "Tracker-Sitzung")

    def _api(self, method, path, **kwargs):
        if self._csrf is None:
            self.login()
        response = self._request(method, path, headers={"X-CSRFToken": self._csrf}, **kwargs)
        if response.status_code in (301, 302, 401, 403):
            # Sitzung abgelaufen: einmal neu anmelden und wiederholen
            self.login()
            response = self._request(method, path, headers={"X-CSRFToken": self._csrf}, **kwargs)
        if response.status_code >= 300:
            raise TrackerError(f"{method} {path} → HTTP {response.status_code}: {response.text[:500]}")
        return response.json() if response.content else None

    # --- Endpunkte ------------------------------------------------------------------------

    def list_logs(self):
        """Alle gespielten Logs des Kontos (ohne geplante 'future'-Partien)."""
        logs, page = [], 1
        while True:
            data = self._api("GET", f"/api/game-logs/get-game-logs/?page={page}")
            logs.extend(data["logs"])
            if not data.get("has_more"):
                return logs
            page += 1

    def get_content(self, content_type):
        """Komplette Liste 'heroes', 'villains' oder 'modulars' (inkl. eigener Inhalte)."""
        return self._api("GET", "/api/game-content/get-content/",
                         params={"content_type": content_type, "allow_other_names": "true"})

    def get_settings(self):
        return self._api("GET", "/api/settings/get/")

    def create_log(self, payload):
        return self._api("POST", "/api/game-logs/add-new/submit/", json=payload)["game_log"]

    def update_log(self, payload):
        return self._api("PUT", "/api/game-logs/edit/submit/", json=payload)

    def delete_log(self, public_id):
        return self._api("DELETE", "/api/game-logs/delete/", params={"public_id": public_id})
