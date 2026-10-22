import React, { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';

interface MermaidChartProps {
  chart: string;
}

// Initialisation globale du thème Mermaid adapté au HUD sombre
mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  securityLevel: 'loose',
  themeVariables: {
    darkMode: true,
    background: '#090f1d',
    primaryColor: '#00f2fe',
    primaryTextColor: '#000000',
    primaryBorderColor: '#00f2fe',
    lineColor: '#38bdf8',
    secondaryColor: '#1e293b',
    tertiaryColor: '#0f172a',
    fontFamily: 'Inter, sans-serif',
    fontSize: '13px',
  },
});

export const MermaidChart: React.FC<MermaidChartProps> = ({ chart }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svgContent, setSvgContent] = useState<string>('');
  const [hasError, setHasError] = useState<boolean>(false);

  useEffect(() => {
    let isMounted = true;
    const renderChart = async () => {
      if (!chart.trim()) return;
      try {
        const id = `mermaid-${Math.random().toString(36).substring(2, 9)}`;
        const { svg } = await mermaid.render(id, chart);
        if (isMounted) {
          setSvgContent(svg);
          setHasError(false);
        }
      } catch (err) {
        if (isMounted) {
          setHasError(true);
        }
      }
    };

    renderChart();
    return () => {
      isMounted = false;
    };
  }, [chart]);

  if (hasError) {
    return (
      <pre style={{ background: '#090f1d', padding: '12px', borderRadius: '6px', fontSize: '0.8rem', color: '#94a3b8' }}>
        {chart}
      </pre>
    );
  }

  return (
    <div
      ref={containerRef}
      style={{
        margin: '16px 0',
        padding: '16px',
        background: 'rgba(8, 15, 30, 0.95)',
        border: '1px solid rgba(0, 242, 254, 0.3)',
        borderRadius: '10px',
        overflowX: 'auto',
        display: 'flex',
        justifyContent: 'center',
        boxShadow: '0 4px 20px rgba(0, 0, 0, 0.5)',
      }}
      dangerouslySetInnerHTML={{ __html: svgContent }}
    />
  );
};
