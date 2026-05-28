<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>GéoQuiz — Capitales du Monde</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
      background: #080818;
      min-height: 100vh;
      color: #fff;
      overflow-x: hidden;
    }

    body::before {
      content: '';
      position: fixed;
      inset: 0;
      background:
        radial-gradient(ellipse 80% 50% at 20% 10%, rgba(90,40,160,0.35) 0%, transparent 60%),
        radial-gradient(ellipse 60% 60% at 80% 80%, rgba(20,60,120,0.35) 0%, transparent 60%);
      z-index: 0;
      pointer-events: none;
    }

    .stars { position: fixed; inset: 0; z-index: 0; pointer-events: none; }
    .star {
      position: absolute;
      background: #fff;
      border-radius: 50%;
      animation: twinkle var(--dur, 3s) ease-in-out infinite alternate;
    }
    @keyframes twinkle { 0% { opacity: 0.08; } 100% { opacity: 0.9; } }

    .screen { display: none; position: relative; z-index: 1; min-height: 100vh; padding: 20px; }
    .screen.active { display: block; }

    /* ── HOME ── */
    #screen-home { max-width: 860px; margin: 0 auto; }

    .home-hero {
      text-align: center;
      padding: 50px 0 36px;
    }

    .home-title {
      font-size: clamp(2.6rem, 7vw, 4.5rem);
      font-weight: 900;
      letter-spacing: -2px;
      background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 30%, #ef4444 65%, #a78bfa 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      line-height: 1.1;
      margin-bottom: 10px;
    }

    .home-sub {
      color: rgba(255,255,255,0.55);
      font-size: 1.05rem;
      margin-bottom: 22px;
    }

    .home-badges {
      display: inline-flex;
      gap: 20px;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 50px;
      padding: 10px 26px;
      font-size: 0.9rem;
      color: rgba(255,255,255,0.65);
    }

    .section-label {
      text-align: center;
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 4px;
      color: rgba(255,255,255,0.3);
      margin: 8px 0 22px;
    }

    .levels-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 14px;
      margin-bottom: 50px;
    }

    .level-card {
      position: relative;
      background: rgba(255,255,255,0.05);
      border: 1.5px solid rgba(255,255,255,0.1);
      border-radius: 22px;
      padding: 30px 18px 22px;
      text-align: center;
