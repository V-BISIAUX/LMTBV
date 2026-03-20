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
      --text:   #c8d6e5;
      --muted:  #4a5568;
    }

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: var(--bg);
      color: var(--text);
      font-family: monospace;
      height: 100vh;
      display: grid;
      grid-template-columns: 1fr 280px;
      overflow: hidden;
    }

    /* ── Vidéo ── */
    .video-col {
      background: #000;
      display: flex;
      align-items: center;
      justify-content: center;
      border-right: 1px solid var(--border);
    }
    .video-col img { max-width: 100%; max-height: 100vh; display: block; }

    /* ── Sidebar ── */
    aside {
      background: var(--panel);
      display: flex;
      flex-direction: column;
      overflow-y: auto;
    }

    .section {
      padding: 14px 16px;
      border-bottom: 1px solid var(--border);
    }

    .label {
      font-size: .6rem;
      letter-spacing: .15em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 8px;
    }

    .row {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 4px;
      font-size: .8rem;
    }
    .row:last-child { margin-bottom: 0; }
    .row .k { color: var(--muted); }
    .row .v { color: var(--text); font-weight: 600; }
    .row .v.hot { color: var(--red); }

    .fix-row {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: .72rem;
      color: var(--muted);
      margin-bottom: 8px;
    }
    .dot {
      width: 6px; height: 6px;
      border-radius: 50%;
      background: var(--muted);
      transition: background .3s;
      flex-shrink: 0;
    }
    .dot.ok  { background: #48bb78; }
    .dot.err { background: var(--red); }

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
      font-size: .75rem;
      color: var(--muted);
      border-top: 1px solid var(--border);
    }
  </style>
</head>
<body>

  <div class="video-col">
    <img src="/stream.mjpg" alt="stream"/>
  </div>

  <aside>

    <div class="section">
      <div class="label">MLX90614</div>
      <div class="row"><span class="k">Ambiante</span><span class="v" id="amb">--.- °C</span></div>
      <div class="row"><span class="k">Objet</span>   <span class="v" id="obj">--.- °C</span></div>
    </div>

    <div class="section">
      <div class="label">ESP8266</div>
      <div class="row"><span class="k">Température</span><span class="v" id="e-temp">-- °C</span></div>
      <div class="row"><span class="k">Humidité</span>   <span class="v" id="e-humi">-- %</span></div>
      <div class="row"><span class="k">Qualité air</span><span class="v" id="e-air">--</span></div>
    </div>

    <div class="section">
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

    <div id="no-fix">En attente du fix GPS…</div>
    <div id="map" style="display:none"></div>

  </aside>

  <script>
    const $ = id => document.getElementById(id);
    let leafMap = null, marker = null;

    /* SSE — température MLX90614 */
    function connectSSE() {
      const es = new EventSource('/temperature/stream');
      es.onmessage = e => {
        const d = JSON.parse(e.data);
        $('amb').textContent = d.ambient_c.toFixed(1) + ' °C';
        const objEl = $('obj');
        objEl.textContent = d.object_c.toFixed(1) + ' °C';
        objEl.className = 'v' + (d.object_c > 37 ? ' hot' : '');
      };
      es.onerror = () => { es.close(); setTimeout(connectSSE, 3000); };
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
