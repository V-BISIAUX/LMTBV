"""
frontend.py — Page HTML servie au client.

Le flux vidéo (MJPEG) et les données de température (SSE) sont indépendants :
  - <img src="/stream.mjpg">          → frames JPEG via multipart
  - new EventSource("/temperature/stream") → JSON poussé par le serveur

L'overlay de température est géré côté JavaScript, ce qui décharge le CPU
du thread d'encodage (plus de cv2.putText dans la boucle caméra).
"""

PAGE = """\
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>PiCam Thermal</title>
  <style>

    /* ── Variables ──────────────────────────────────────────────────────── */
    :root {
      --bg:        #0a0c0f;
      --panel:     #111418;
      --border:    #1e2530;
      --accent:    #00d4ff;
      --accent2:   #ff4d4d;
      --text:      #c8d6e5;
      --muted:     #4a5568;
      --mono:      'Share Tech Mono', monospace;
      --sans:      'Barlow', sans-serif;
    }

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      background: var(--bg);
      color: var(--text);
      font-family: var(--sans);
      font-weight: 300;
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr auto;
      overflow: hidden;
    }

    /* ── Header ─────────────────────────────────────────────────────────── */
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 28px;
      border-bottom: 1px solid var(--border);
      background: var(--panel);
    }

    .logo {
      display: flex;
      align-items: center;
      gap: 10px;
      font-family: var(--mono);
      font-size: 0.85rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--accent);
    }

    .logo-dot {
      width: 8px; height: 8px;
      border-radius: 50%;
      background: var(--accent);
      animation: pulse 2s ease-in-out infinite;
    }

    @keyframes pulse {
      0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(0,212,255,.4); }
      50%       { opacity: .6; box-shadow: 0 0 0 6px rgba(0,212,255,0); }
    }

    .status-bar {
      display: flex;
      gap: 24px;
      align-items: center;
      font-family: var(--mono);
      font-size: 0.75rem;
      color: var(--muted);
    }

    .status-bar span { letter-spacing: 0.08em; }

    /* ── Main layout ─────────────────────────────────────────────────────── */
    main {
      display: grid;
      grid-template-columns: 1fr 260px;
      gap: 0;
      overflow: hidden;
    }

    /* ── Video ───────────────────────────────────────────────────────────── */
    .video-wrapper {
      position: relative;
      background: #000;
      display: flex;
      align-items: center;
      justify-content: center;
      border-right: 1px solid var(--border);
      overflow: hidden;
    }

    #stream {
      display: block;
      max-width: 100%;
      max-height: calc(100vh - 112px);
      object-fit: contain;
    }

    /* Coin HUD */
    .hud-corner {
      position: absolute;
      font-family: var(--mono);
      font-size: 0.7rem;
      color: rgba(0,212,255,.55);
      letter-spacing: 0.1em;
      pointer-events: none;
    }
    .hud-corner.tl { top: 12px;  left: 14px;  }
    .hud-corner.tr { top: 12px;  right: 14px; text-align: right; }
    .hud-corner.bl { bottom: 12px; left: 14px; }
    .hud-corner.br { bottom: 12px; right: 14px; text-align: right; }

    /* Réticule */
    .reticle {
      position: absolute;
      width: 36px; height: 36px;
      pointer-events: none;
      opacity: .4;
    }
    .reticle::before, .reticle::after {
      content: '';
      position: absolute;
      background: var(--accent);
    }
    .reticle::before { top: 0; left: 50%; width: 1px; height: 100%; transform: translateX(-50%); }
    .reticle::after  { left: 0; top: 50%; height: 1px; width: 100%; transform: translateY(-50%); }

    /* ── Sidebar ─────────────────────────────────────────────────────────── */
    aside {
      background: var(--panel);
      padding: 24px 18px;
      display: flex;
      flex-direction: column;
      gap: 20px;
      overflow-y: auto;
    }

    .section-label {
      font-family: var(--mono);
      font-size: 0.65rem;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 10px;
    }

    /* Température — carte principale */
    .temp-card {
      background: #0d1017;
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 16px;
    }

    .temp-row {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      margin-bottom: 6px;
    }
    .temp-row:last-child { margin-bottom: 0; }

    .temp-label {
      font-family: var(--mono);
      font-size: 0.7rem;
      letter-spacing: 0.1em;
      color: var(--muted);
      text-transform: uppercase;
    }

    .temp-value {
      font-family: var(--mono);
      font-size: 1.65rem;
      font-weight: 400;
      line-height: 1;
      color: var(--accent);
      transition: color .3s;
    }

    .temp-value.hot { color: var(--accent2); }

    .temp-unit {
      font-family: var(--mono);
      font-size: 0.75rem;
      color: var(--muted);
      margin-left: 4px;
    }

    /* Séparateur */
    .divider {
      height: 1px;
      background: var(--border);
      margin: 4px 0;
    }

    /* Barre de gauge */
    .gauge-wrap {
      margin-top: 8px;
    }
    .gauge-track {
      height: 4px;
      background: var(--border);
      border-radius: 2px;
      overflow: hidden;
      margin-top: 4px;
    }
    .gauge-fill {
      height: 100%;
      border-radius: 2px;
      background: linear-gradient(90deg, var(--accent), #00ffcc);
      transition: width .5s ease, background .5s ease;
      width: 0%;
    }
    .gauge-fill.hot {
      background: linear-gradient(90deg, #ff4d4d, #ff9900);
    }

    /* Historique sparkline */
    .sparkline-wrap {
      margin-top: 4px;
    }
    #sparkline {
      width: 100%;
      height: 48px;
      display: block;
    }

    /* Timestamp */
    .timestamp {
      font-family: var(--mono);
      font-size: 0.65rem;
      color: var(--muted);
      text-align: right;
      margin-top: 6px;
    }

    /* Connexion SSE */
    .sse-status {
      display: flex;
      align-items: center;
      gap: 6px;
      font-family: var(--mono);
      font-size: 0.68rem;
      color: var(--muted);
    }
    .sse-dot {
      width: 6px; height: 6px;
      border-radius: 50%;
      background: var(--muted);
      transition: background .3s;
    }
    .sse-dot.connected { background: #48bb78; box-shadow: 0 0 6px #48bb78; }
    .sse-dot.error     { background: var(--accent2); }

    /* ── Footer ─────────────────────────────────────────────────────────── */
    footer {
      padding: 8px 28px;
      border-top: 1px solid var(--border);
      background: var(--panel);
      font-family: var(--mono);
      font-size: 0.65rem;
      color: var(--muted);
      display: flex;
      justify-content: space-between;
      letter-spacing: 0.08em;
    }
  </style>
</head>
<body>

  <!-- ── Header ──────────────────────────────────────────────────────────── -->
  <header>
    <div class="logo">
      <div class="logo-dot"></div>
      PiCam Thermal Stream
    </div>
    <div class="status-bar">
      <span id="fps-counter">-- fps</span>
      <span id="resolution">640×480</span>
      <span id="clock">--:--:--</span>
    </div>
  </header>

  <!-- ── Main ────────────────────────────────────────────────────────────── -->
  <main>

    <!-- Vidéo -->
    <div class="video-wrapper">
      <img id="stream" src="/stream.mjpg" alt="flux vidéo" />
      <div class="hud-corner tl" id="hud-tl">LIVE</div>
      <div class="hud-corner tr" id="hud-tr">MLX90614</div>
      <div class="hud-corner bl" id="hud-bl">CAM0</div>
      <div class="hud-corner br" id="hud-br"></div>
      <div class="reticle"></div>
    </div>

    <!-- Sidebar température -->
    <aside>
      <div>
        <div class="section-label">Température</div>

        <div class="temp-card">
          <!-- Ambiante -->
          <div class="temp-row">
            <span class="temp-label">Ambiante</span>
            <span>
              <span class="temp-value" id="amb-val">--.-</span>
              <span class="temp-unit">°C</span>
            </span>
          </div>

          <div class="divider"></div>

          <!-- Objet -->
          <div class="temp-row">
            <span class="temp-label">Objet</span>
            <span>
              <span class="temp-value" id="obj-val">--.-</span>
              <span class="temp-unit">°C</span>
            </span>
          </div>

          <!-- Gauge objet -->
          <div class="gauge-wrap">
            <div class="gauge-track">
              <div class="gauge-fill" id="gauge-fill"></div>
            </div>
          </div>

          <div class="timestamp" id="ts">--</div>
        </div>
      </div>

      <!-- Sparkline historique -->
      <div class="sparkline-wrap">
        <div class="section-label">Historique objet (60 pts)</div>
        <canvas id="sparkline"></canvas>
      </div>

      <!-- Statut SSE -->
      <div class="sse-status">
        <div class="sse-dot" id="sse-dot"></div>
        <span id="sse-label">En attente…</span>
      </div>
    </aside>
  </main>

  <!-- ── Footer ──────────────────────────────────────────────────────────── -->
  <footer>
    <span>Raspberry Pi · Picamera2 · MLX90614</span>
    <span id="footer-temp">AMB: -- °C &nbsp;|&nbsp; OBJ: -- °C</span>
  </footer>

  <!-- ── Scripts ─────────────────────────────────────────────────────────── -->
  <script>
    /* ── Horloge ────────────────────────────────────────────────────────── */
    function updateClock() {
      document.getElementById('clock').textContent =
        new Date().toLocaleTimeString('fr-FR');
    }
    updateClock();
    setInterval(updateClock, 1000);

    /* ── Compteur FPS (basé sur les événements load de l'img MJPEG) ─────── */
    (() => {
      const img = document.getElementById('stream');
      let frameCount = 0, lastFps = 0;

      img.addEventListener('load', () => frameCount++);
      setInterval(() => {
        lastFps = frameCount;
        frameCount = 0;
        document.getElementById('fps-counter').textContent = `${lastFps} fps`;
      }, 1000);
    })();

    /* ── Sparkline minimaliste (canvas 2D) ──────────────────────────────── */
    const HISTORY_LEN = 60;
    const sparkHistory = [];

    function drawSparkline(canvas, data) {
      const W = canvas.width  = canvas.offsetWidth  * window.devicePixelRatio;
      const H = canvas.height = canvas.offsetHeight * window.devicePixelRatio;
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, W, H);

      if (data.length < 2) return;

      const min = Math.min(...data) - 0.5;
      const max = Math.max(...data) + 0.5;
      const scaleX = W / (data.length - 1);
      const scaleY = H / (max - min);

      const toX = i => i * scaleX;
      const toY = v => H - (v - min) * scaleY;

      // Remplissage dégradé
      const grad = ctx.createLinearGradient(0, 0, 0, H);
      grad.addColorStop(0, 'rgba(0,212,255,.35)');
      grad.addColorStop(1, 'rgba(0,212,255,0)');

      ctx.beginPath();
      ctx.moveTo(toX(0), toY(data[0]));
      for (let i = 1; i < data.length; i++) ctx.lineTo(toX(i), toY(data[i]));
      ctx.lineTo(toX(data.length - 1), H);
      ctx.lineTo(0, H);
      ctx.closePath();
      ctx.fillStyle = grad;
      ctx.fill();

      // Ligne
      ctx.beginPath();
      ctx.moveTo(toX(0), toY(data[0]));
      for (let i = 1; i < data.length; i++) ctx.lineTo(toX(i), toY(data[i]));
      ctx.strokeStyle = 'rgba(0,212,255,.9)';
      ctx.lineWidth = 1.5 * window.devicePixelRatio;
      ctx.stroke();
    }

    /* ── SSE : réception des données de température ─────────────────────── */
    function connectSSE() {
      const dot   = document.getElementById('sse-dot');
      const label = document.getElementById('sse-label');
      const es    = new EventSource('/temperature/stream');

      es.onopen = () => {
        dot.className   = 'sse-dot connected';
        label.textContent = 'Connecté';
      };

      es.onmessage = (event) => {
        const d = JSON.parse(event.data);

        /* Valeurs numériques */
        const amb = d.ambient_c.toFixed(1);
        const obj = d.object_c.toFixed(1);
        const hot = d.object_c > 37;

        /* Mise à jour DOM */
        const ambEl  = document.getElementById('amb-val');
        const objEl  = document.getElementById('obj-val');
        const gauge  = document.getElementById('gauge-fill');
        const footer = document.getElementById('footer-temp');

        ambEl.textContent = amb;
        objEl.textContent = obj;
        objEl.className   = 'temp-value' + (hot ? ' hot' : '');
        gauge.className   = 'gauge-fill'  + (hot ? ' hot' : '');

        // Gauge : 15°C → 0%, 50°C → 100%
        const pct = Math.max(0, Math.min(100, (d.object_c - 15) / 35 * 100));
        gauge.style.width = pct.toFixed(1) + '%';

        // Timestamp
        const ts = new Date(d.timestamp * 1000);
        document.getElementById('ts').textContent =
          ts.toLocaleTimeString('fr-FR', { hour12: false });

        // Footer
        footer.innerHTML = `AMB: ${amb} °C &nbsp;|&nbsp; OBJ: ${obj} °C`;

        // HUD coin bas-droite
        document.getElementById('hud-br').textContent = `${obj}°`;

        // Sparkline
        sparkHistory.push(d.object_c);
        if (sparkHistory.length > HISTORY_LEN) sparkHistory.shift();
        drawSparkline(document.getElementById('sparkline'), sparkHistory);
      };

      es.onerror = () => {
        dot.className     = 'sse-dot error';
        label.textContent = 'Reconnexion…';
        es.close();
        setTimeout(connectSSE, 3000);  // reconnexion automatique
      };
    }

    connectSSE();
  </script>
</body>
</html>
"""
