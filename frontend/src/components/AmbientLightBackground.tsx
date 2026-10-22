import React, { useEffect, useRef } from 'react';

// Effet de lumière ambiante fluide et aléatoire se déplaçant en profondeur (z) derrière l'interface
export const AmbientLightBackground: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener('resize', handleResize);

    // Orbes de lumière avec trajectoires aléatoires et variation de profondeur (z-depth)
    interface LightOrb {
      x: number;
      y: number;
      vx: number;
      vy: number;
      z: number;        // Profondeur simulée (0.2 = très loin / faible, 1.0 = très proche / intense)
      vz: number;       // Vitesse d'approche / éloignement
      targetZ: number;
      baseRadius: number;
      color: string;
      colorMid: string;
    }

    const orbs: LightOrb[] = [
      {
        x: width * 0.3,
        y: height * 0.3,
        vx: 0.8,
        vy: 0.5,
        z: 0.6,
        vz: 0.003,
        targetZ: 0.8,
        baseRadius: Math.min(width, height) * 0.35,
        color: 'rgba(0, 242, 254, ',      // Cyan électrique principal
        colorMid: 'rgba(0, 114, 255, ',
      },
      {
        x: width * 0.7,
        y: height * 0.6,
        vx: -0.6,
        vy: 0.7,
        z: 0.4,
        vz: -0.002,
        targetZ: 0.3,
        baseRadius: Math.min(width, height) * 0.4,
        color: 'rgba(14, 165, 233, ',     // Bleu ciel cyan
        colorMid: 'rgba(56, 189, 248, ',
      },
      {
        x: width * 0.5,
        y: height * 0.8,
        vx: 0.4,
        vy: -0.6,
        z: 0.7,
        vz: 0.004,
        targetZ: 0.9,
        baseRadius: Math.min(width, height) * 0.3,
        color: 'rgba(6, 182, 212, ',      // Cyan profond
        colorMid: 'rgba(3, 105, 161, ',
      }
    ];

    let lastTime = performance.now();

    const render = (currentTime: number) => {
      const dt = Math.min((currentTime - lastTime) / 1000, 0.1);
      lastTime = currentTime;

      // Nettoyage fond sombre profond
      ctx.fillStyle = '#060913';
      ctx.fillRect(0, 0, width, height);

      // Mise à jour et dessin de chaque orbe de lumière
      orbs.forEach((orb) => {
        // Déplacement spatial 2D fluide avec rebond doux sur les bords
        orb.x += orb.vx * (1 + (1 - orb.z) * 0.5);
        orb.y += orb.vy * (1 + (1 - orb.z) * 0.5);

        // Perturbation aléatoire de vélocité
        orb.vx += (Math.random() - 0.5) * 0.04;
        orb.vy += (Math.random() - 0.5) * 0.04;

        // Limiter la vitesse maximale
        const speed = Math.hypot(orb.vx, orb.vy);
        if (speed > 1.4) {
          orb.vx = (orb.vx / speed) * 1.4;
          orb.vy = (orb.vy / speed) * 1.4;
        }

        // Rebond souple dans l'écran
        const margin = 100;
        if (orb.x < margin) orb.vx = Math.abs(orb.vx) * 0.9 + 0.1;
        if (orb.x > width - margin) orb.vx = -Math.abs(orb.vx) * 0.9 - 0.1;
        if (orb.y < margin) orb.vy = Math.abs(orb.vy) * 0.9 + 0.1;
        if (orb.y > height - margin) orb.vy = -Math.abs(orb.vy) * 0.9 - 0.1;

        // Simulation de la profondeur Z (se rapproche et s'éloigne aléatoirement)
        if (Math.abs(orb.z - orb.targetZ) < 0.03) {
          // Nouveau point cible aléatoire de profondeur entre 0.25 (loin) et 0.95 (très proche)
          orb.targetZ = 0.25 + Math.random() * 0.7;
          orb.vz = (orb.targetZ - orb.z) * 0.008;
        }
        orb.z += orb.vz;
        orb.z = Math.max(0.2, Math.min(1.0, orb.z));

        // Rayon et intensité dérivés du rapprochement / éloignement (z-depth)
        const currentRadius = orb.baseRadius * (0.6 + orb.z * 0.8);
        const centerOpacity = 0.10 + orb.z * 0.22; // De 0.14 (faible/loin) à 0.32 (intense/proche)
        const midOpacity = centerOpacity * 0.5;

        // Dégradé radial lumineux organique
        const gradient = ctx.createRadialGradient(
          orb.x,
          orb.y,
          0,
          orb.x,
          orb.y,
          currentRadius
        );

        gradient.addColorStop(0, `${orb.color}${centerOpacity.toFixed(3)})`);
        gradient.addColorStop(0.4, `${orb.colorMid}${midOpacity.toFixed(3)})`);
        gradient.addColorStop(0.7, `${orb.color}0.03)`);
        gradient.addColorStop(1, `${orb.color}0)`);

        ctx.beginPath();
        ctx.arc(orb.x, orb.y, currentRadius, 0, Math.PI * 2);
        ctx.fillStyle = gradient;
        ctx.fill();
      });

      animationFrameId = requestAnimationFrame(render);
    };

    animationFrameId = requestAnimationFrame(render);

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100vw',
        height: '100vh',
        zIndex: 0,
        pointerEvents: 'none',
      }}
    />
  );
};
