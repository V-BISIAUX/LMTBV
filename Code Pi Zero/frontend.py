"""
frontend.py — Page HTML servie au client.

Layout : vidéo à gauche, sidebar à droite.
Sidebar : température MLX90614 (SSE) + données ESP8266 (polling) + carte OSM.
"""

PAGE = """\
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>PiCam Robot</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    :root {
      --bg:     #0a0c0f;
      --panel:  #111418;
      --border: #1e2530;
      --accent: #00d4ff;
      --red:    #ff4d4d;
      --green:  #48bb78;
      --text:   #c8d6e5;
      --muted:  #4a5568;
      --panel2: #161b22;
    }

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: var(--bg);
      color: var(--text);
      font-family: 'Courier New', monospace;
      height: 100vh;
      display: grid;
      grid-template-columns: 1fr 300px;
      overflow: hidden;
    }

    /* ── Vidéo ── */
    .video-col {
      background: #000;
      display: flex;
      align-items: center;
      justify-content: center;
      border-right: 1px solid var(--border);
      position: relative;
    }
    .video-col img {
      width: 640px;
      height: 480px;
      display: block;
      image-rendering: auto;
    }

    /* ── Sidebar ── */
    aside {
      background: var(--panel);
      display: flex;
      flex-direction: column;
      overflow-y: auto;
    }

    /* ── Barre de statut ── */
    .status-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 14px;
      background: var(--panel2);
      border-bottom: 1px solid var(--border);
      font-size: .65rem;
      color: var(--muted);
      letter-spacing: .05em;
      flex-shrink: 0;
    }
    .status-bar .sse-status {
      display: flex;
      align-items: center;
      gap: 5px;
    }
    .status-bar .sse-dot {
      width: 5px; height: 5px;
      border-radius: 50%;
      background: var(--muted);
      transition: background .4s;
    }
    .status-bar .sse-dot.live { background: var(--green); box-shadow: 0 0 4px var(--green); }
    .status-bar .sse-dot.err  { background: var(--red); }
    #last-update { color: var(--muted); }

    /* ── Section ── */
    .section {
      padding: 16px 16px 14px;
      border-bottom: 1px solid var(--border);
    }

    /* Titre de section */
    .section-title {
      display: flex;
      align-items: center;
      gap: 7px;
      margin-bottom: 12px;
    }
    .section-title .icon {
      font-size: .75rem;
      color: var(--accent);
      line-height: 1;
    }
    .section-title .name {
      font-size: .65rem;
      letter-spacing: .18em;
      text-transform: uppercase;
      color: var(--accent);
      font-weight: 700;
    }
    .section-title .sub {
      font-size: .58rem;
      letter-spacing: .08em;
      color: var(--muted);
      margin-left: auto;
    }

    /* Ligne clé / valeur */
    .row {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      padding: 5px 0;
      border-bottom: 1px solid #1a2030;
      font-size: .78rem;
    }
    .row:last-child { border-bottom: none; padding-bottom: 0; }
    .row .k { color: var(--muted); }
    .row .v {
      color: var(--text);
      font-weight: 700;
      font-size: .85rem;
      letter-spacing: .03em;
    }
    .row .v.hot { color: var(--red); }

    /* Fix GPS */
    .fix-row {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: .7rem;
      color: var(--muted);
      margin-bottom: 12px;
    }
    .dot {
      width: 7px; height: 7px;
      border-radius: 50%;
      background: var(--muted);
      transition: background .3s;
      flex-shrink: 0;
    }
    .dot.ok  { background: var(--green); box-shadow: 0 0 5px var(--green); }
    .dot.err { background: var(--red);   box-shadow: 0 0 5px var(--red); }

    /* ── Jauge température objet ── */
    .gauge-wrap {
      margin-top: 10px;
    }
    .gauge-track {
      width: 100%;
      height: 7px;
      border-radius: 4px;
      background: #1a2030;
      overflow: hidden;
    }
    .gauge-fill {
      height: 100%;
      width: 0%;
      border-radius: 4px;
      transition: width .6s cubic-bezier(.4,0,.2,1), background .6s;
      background: #48bb78;
    }

    /* ── Carte ── */
    #map {
      width: 100%;
      height: 200px;
      border-top: 1px solid var(--border);
    }
    #no-fix {
      height: 200px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: .72rem;
      color: var(--muted);
      border-top: 1px solid var(--border);
      flex-direction: column;
      gap: 6px;
    }
    #no-fix .no-fix-icon { font-size: 1.4rem; opacity: .3; }
  </style>
</head>
<body>

  <div class="video-col">
    <img src="/stream.mjpg" alt="stream"/>
  </div>

  <aside>

    <!-- Barre de statut -->
    <div class="status-bar">
      <div class="sse-status">
        <div class="sse-dot" id="sse-dot"></div>
        <span id="sse-label">SSE déconnecté</span>
      </div>
      <span id="last-update">--:--:--</span>
    </div>

    <!-- MLX90614 -->
    <div class="section">
      <div class="section-title">
        <span class="name">MLX90614</span>
      </div>
      <div class="row"><span class="k">Ambiante</span><span class="v" id="amb">--.- °C</span></div>
      <div class="row"><span class="k">Objet</span>   <span class="v" id="obj">--.- °C</span></div>
      <div class="gauge-wrap">
        <div class="gauge-track">
          <div class="gauge-fill" id="gauge-fill"></div>
        </div>
      </div>
    </div>

    <!-- ESP8266 -->
    <div class="section">
      <div class="section-title">
        <span class="name">ESP8266</span>
      </div>
      <div class="row"><span class="k">Température</span><span class="v" id="e-temp">-- °C</span></div>
      <div class="row"><span class="k">Humidité</span>   <span class="v" id="e-humi">-- %</span></div>
      <div class="row"><span class="k">Qualité air</span><span class="v" id="e-air">--</span></div>
    </div>

    <!-- GPS -->
    <div class="section">
      <div class="section-title">
        <span class="name">GPS</span>
      </div>
      <div class="fix-row">
        <div class="dot" id="fix-dot"></div>
        <span id="fix-text">Pas de fix GPS</span>
      </div>
      <div class="row"><span class="k">Latitude</span>   <span class="v" id="g-lat">--</span></div>
      <div class="row"><span class="k">Longitude</span>  <span class="v" id="g-lng">--</span></div>
      <div class="row"><span class="k">Altitude</span>   <span class="v" id="g-alt">--</span></div>
      <div class="row"><span class="k">Vitesse</span>    <span class="v" id="g-spd">--</span></div>
      <div class="row"><span class="k">Satellites</span> <span class="v" id="g-sat">--</span></div>
    </div>

    <div id="no-fix">
      <span class="no-fix-icon">◎</span>
      En attente du fix GPS…
    </div>
    <div id="map" style="display:none"></div>

  </aside>

  <script>
    const $ = id => document.getElementById(id);
    let leafMap = null, marker = null;

    /* Horloge dernière mise à jour */
    function setLastUpdate() {
      const now = new Date();
      $('last-update').textContent = now.toLocaleTimeString('fr-FR');
    }

    /* Jauge température objet */
    function updateGauge(temp) {
      const MAX = 50;
      const pct = Math.min(Math.max(temp / MAX * 100, 0), 100);
      const fill = $('gauge-fill');
      fill.style.width = pct + '%';

      // Couleur progressive
      let color;
      if (temp <= 15)      color = '#63b3ed'; // bleu
      else if (temp <= 30) color = '#48bb78'; // vert
      else if (temp <= 42) color = '#f6ad55'; // orange
      else                 color = '#ff4d4d'; // rouge

      fill.style.background = color;
    }

    /* SSE — température MLX90614 */
    function connectSSE() {
      const es = new EventSource('/temperature/stream');

      es.onopen = () => {
        $('sse-dot').className = 'sse-dot live';
        $('sse-label').textContent = 'SSE connecté';
      };

      es.onmessage = e => {
        const d = JSON.parse(e.data);
        $('amb').textContent = d.ambient_c.toFixed(1) + ' °C';
        const objEl = $('obj');
        objEl.textContent = d.object_c.toFixed(1) + ' °C';
        objEl.className = 'v' + (d.object_c > 50 ? ' hot' : '');
        updateGauge(d.object_c);
        setLastUpdate();
      };

      es.onerror = () => {
        $('sse-dot').className = 'sse-dot err';
        $('sse-label').textContent = 'SSE déconnecté';
        es.close();
        setTimeout(connectSSE, 3000);
      };
    }

    /* Polling — données ESP8266 toutes les 5s */
    async function fetchEsp() {
      try {
        const r = await fetch('/esp/data');
        if (!r.ok) return;
        const d = await r.json();

        $('e-temp').textContent = d.temperature != null ? d.temperature + ' °C' : '--';
        $('e-humi').textContent = d.humidity    != null ? d.humidity    + ' %'  : '--';
        $('e-air').textContent  = d.air_label   ?? '--';

        const g = d.gps ?? {};
        const hasFix = g.fix && g.latitude != null && g.longitude != null;

        $('fix-dot').className    = 'dot ' + (hasFix ? 'ok' : 'err');
        $('fix-text').textContent = hasFix ? 'Fix GPS actif' : 'Pas de fix GPS';
        $('g-lat').textContent = g.latitude  != null ? g.latitude.toFixed(6)  + '°'     : '--';
        $('g-lng').textContent = g.longitude != null ? g.longitude.toFixed(6) + '°'     : '--';
        $('g-alt').textContent = g.altitude  != null ? g.altitude.toFixed(1)  + ' m'    : '--';
        $('g-spd').textContent = g.speed_kmh != null ? g.speed_kmh.toFixed(1) + ' km/h' : '--';
        $('g-sat').textContent = g.satellites ?? '--';

        if (hasFix) updateMap(g.latitude, g.longitude);
        setLastUpdate();
      } catch(_) {}
    }

    function updateMap(lat, lng) {
      if (!leafMap) {
        $('no-fix').style.display = 'none';
        $('map').style.display    = 'block';
        leafMap = L.map('map').setView([lat, lng], 16);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          attribution: '© OpenStreetMap', maxZoom: 19
        }).addTo(leafMap);
        marker = L.marker([lat, lng]).addTo(leafMap);
      } else {
        marker.setLatLng([lat, lng]);
        leafMap.panTo([lat, lng]);
      }
    }

    connectSSE();
    fetchEsp();
    setInterval(fetchEsp, 5000);
  </script>
</body>
</html>
"""
