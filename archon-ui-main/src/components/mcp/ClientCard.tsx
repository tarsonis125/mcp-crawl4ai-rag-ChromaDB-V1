import React, { useEffect, useState, useRef, createElement } from 'react';
import { Server, Activity, Clock, ChevronRight, Hammer } from 'lucide-react';
import { Client } from './MCPClients';
interface ClientCardProps {
  client: Client;
  onSelect: () => void;
}
export const ClientCard = ({
  client,
  onSelect
}: ClientCardProps) => {
  const [isFlipped, setIsFlipped] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const particlesRef = useRef<HTMLDivElement>(null);
  // Special styling for Archon client
  const isArchonClient = client.isArchon === true;
  // Status-based styling
  const statusConfig = {
    online: {
      color: isArchonClient ? 'archon' : 'cyan',
      glow: isArchonClient ? 'shadow-[0_0_25px_rgba(59,130,246,0.7),0_0_15px_rgba(168,85,247,0.5)] dark:shadow-[0_0_35px_rgba(59,130,246,0.8),0_0_20px_rgba(168,85,247,0.7)]' : 'shadow-[0_0_15px_rgba(34,211,238,0.5)] dark:shadow-[0_0_20px_rgba(34,211,238,0.7)]',
      border: isArchonClient ? 'border-blue-400/60 dark:border-blue-500/60' : 'border-cyan-400/50 dark:border-cyan-500/40',
      badge: isArchonClient ? 'bg-blue-500/30 text-blue-400 border-blue-500/40' : 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
      pulse: isArchonClient ? 'bg-blue-400' : 'bg-cyan-400'
    },
    offline: {
      color: 'gray',
      glow: 'shadow-[0_0_15px_rgba(156,163,175,0.3)] dark:shadow-[0_0_15px_rgba(156,163,175,0.4)]',
      border: 'border-gray-400/30 dark:border-gray-600/30',
      badge: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
      pulse: 'bg-gray-400'
    },
    error: {
      color: 'pink',
      glow: 'shadow-[0_0_15px_rgba(236,72,153,0.5)] dark:shadow-[0_0_20px_rgba(236,72,153,0.7)]',
      border: 'border-pink-400/50 dark:border-pink-500/40',
      badge: 'bg-pink-500/20 text-pink-400 border-pink-500/30',
      pulse: 'bg-pink-400'
    }
  };
  // Handle mouse movement for neon trail effect
  useEffect(() => {
    if (!isArchonClient || !particlesRef.current) return;

    let trailPoints: {x: number, y: number, timestamp: number}[] = [];
    let trailSvg: SVGElement | null = null;
    let lastMoveTime = 0;

    const createTrailSvg = () => {
      if (trailSvg) return trailSvg;
      
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('class', 'absolute inset-0 pointer-events-none');
      svg.setAttribute('width', '100%');
      svg.setAttribute('height', '100%');
      svg.style.overflow = 'visible';
      
      particlesRef.current?.appendChild(svg);
      trailSvg = svg;
      return svg;
    };

    const updateTrail = () => {
      if (!trailSvg || trailPoints.length < 2) return;
      
      // Clear existing path
      trailSvg.innerHTML = '';
      
      // Create smooth path through all points
      let pathData = `M ${trailPoints[0].x} ${trailPoints[0].y}`;
      
      for (let i = 1; i < trailPoints.length; i++) {
        const currentPoint = trailPoints[i];
        const prevPoint = trailPoints[i - 1];
        
        // Create smooth curve between points
        const controlX = (prevPoint.x + currentPoint.x) / 2;
        const controlY = (prevPoint.y + currentPoint.y) / 2;
        
        pathData += ` Q ${controlX} ${controlY} ${currentPoint.x} ${currentPoint.y}`;
      }
      
      // Create the glowing trail path
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', pathData);
      path.setAttribute('stroke', 'rgba(59, 130, 246, 0.8)');
      path.setAttribute('stroke-width', '3');
      path.setAttribute('fill', 'none');
      path.setAttribute('stroke-linecap', 'round');
      path.setAttribute('stroke-linejoin', 'round');
      
      // Add glow effects with multiple paths
      const glowPath1 = path.cloneNode() as SVGPathElement;
      glowPath1.setAttribute('stroke', 'rgba(168, 85, 247, 0.6)');
      glowPath1.setAttribute('stroke-width', '6');
      glowPath1.setAttribute('filter', 'blur(2px)');
      
      const glowPath2 = path.cloneNode() as SVGPathElement;
      glowPath2.setAttribute('stroke', 'rgba(59, 130, 246, 0.4)');
      glowPath2.setAttribute('stroke-width', '10');
      glowPath2.setAttribute('filter', 'blur(4px)');
      
      // Add paths in order (largest glow first)
      trailSvg.appendChild(glowPath2);
      trailSvg.appendChild(glowPath1);
      trailSvg.appendChild(path);
      
      // Animate the trail fade
      const fadeAnimation = trailSvg.animate([
        { opacity: 1 },
        { opacity: 0 }
      ], {
        duration: 2000,
        easing: 'ease-out',
        fill: 'forwards'
      });
    };

    const handleMouseMove = (e: MouseEvent) => {
      if (!particlesRef.current) return;
      
      // Throttle movement tracking
      const now = Date.now();
      if (now - lastMoveTime < 30) return;
      lastMoveTime = now;
      
      const rect = particlesRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      // Add new point to trail
      trailPoints.push({ x, y, timestamp: now });
      
      // Remove old points (keep trail length manageable)
      trailPoints = trailPoints.filter(point => now - point.timestamp < 1500);
      
      // Create/update trail SVG
      createTrailSvg();
      updateTrail();
    };

    const cardElement = particlesRef.current;
    if (isHovered) {
      cardElement.addEventListener('mousemove', handleMouseMove);
    }

    return () => {
      cardElement.removeEventListener('mousemove', handleMouseMove);
      // Clean up trail SVG
      if (trailSvg && particlesRef.current?.contains(trailSvg)) {
        particlesRef.current.removeChild(trailSvg);
      }
      trailPoints = [];
      trailSvg = null;
    };
  }, [isArchonClient, isHovered]);
  const currentStatus = statusConfig[client.status];
  // Handle card flip
  const toggleFlip = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsFlipped(!isFlipped);
  };
  // Generate more tools for some clients to demonstrate scrolling
  const extendedTools = client.status === 'online' ? [...client.tools, {
    id: `extra-1-${client.id}`,
    name: 'network_monitor',
    description: 'Monitor network traffic and detect anomalies',
    parameters: []
  }, {
    id: `extra-2-${client.id}`,
    name: 'security_scan',
    description: 'Run comprehensive security vulnerability scans',
    parameters: []
  }, {
    id: `extra-3-${client.id}`,
    name: 'log_analyzer',
    description: 'Parse and analyze system logs for issues',
    parameters: []
  }, {
    id: `extra-4-${client.id}`,
    name: 'backup_manager',
    description: 'Manage system backups and restoration points',
    parameters: []
  }] : client.tools;
  // Special background for Archon client
  const archonBackground = isArchonClient ? 'bg-gradient-to-b from-white/80 via-blue-50/30 to-white/60 dark:from-white/10 dark:via-blue-900/10 dark:to-black/30' : 'bg-gradient-to-b from-white/80 to-white/60 dark:from-white/10 dark:to-black/30';


  return <div className={`flip-card h-[220px] cursor-pointer ${isArchonClient ? 'order-first' : ''}`} style={{
    perspective: '1500px'
  }} onClick={onSelect} onMouseEnter={() => setIsHovered(true)} onMouseLeave={() => setIsHovered(false)}>
      <div className={`relative w-full h-full transition-all duration-500 transform-style-preserve-3d ${isFlipped ? 'rotate-y-180' : ''} ${isHovered && !isFlipped ? 'hover-lift' : ''}`}>
        {/* Front Side */}
        <div className={`absolute w-full h-full backface-hidden backdrop-blur-md ${archonBackground} rounded-xl p-5 ${currentStatus.border} ${currentStatus.glow} transition-all duration-300 ${isArchonClient ? 'archon-card-border' : ''}`} ref={isArchonClient ? particlesRef : undefined}>
          {/* Particle container for Archon client */}
          {isArchonClient && <div className="absolute inset-0 rounded-xl overflow-hidden pointer-events-none">
              <div className="particles-container"></div>
            </div>}
          {/* Subtle aurora glow effect for Archon client */}
          {isArchonClient && <div className="absolute inset-0 rounded-xl overflow-hidden opacity-20">
              <div className="absolute -inset-[100px] bg-[radial-gradient(circle,rgba(59,130,246,0.8)_0%,rgba(168,85,247,0.6)_40%,transparent_70%)] blur-3xl animate-[pulse_8s_ease-in-out_infinite]"></div>
            </div>}
          {/* Client info */}
          <div className="flex items-start">
            {isArchonClient ? <div className="p-3 rounded-lg bg-gradient-to-br from-blue-500/20 to-purple-500/20 mr-3 relative pulse-soft">
                <img src="/logo-neon.svg" alt="Archon" className="w-6 h-6 drop-shadow-[0_0_8px_rgba(59,130,246,0.8)] animate-glow-pulse" />
                <div className="absolute inset-0 rounded-lg bg-blue-500/10 animate-pulse opacity-60"></div>
              </div> : <div className={`p-3 rounded-lg bg-${currentStatus.color}-500/10 text-${currentStatus.color}-400 mr-3 pulse-soft`}>
                <Server className="w-6 h-6" />
              </div>}
            <div>
              <h3 className={`font-bold text-gray-800 dark:text-white text-lg ${isArchonClient ? 'bg-gradient-to-r from-blue-400 to-purple-500 text-transparent bg-clip-text animate-text-shimmer' : ''}`}>
                {client.name}
              </h3>
              <p className="text-gray-500 dark:text-gray-400 text-sm">
                {client.ip}
              </p>
            </div>
          </div>
          <div className="mt-5 space-y-2">
            <div className="flex items-center text-sm">
              <Clock className="w-4 h-4 text-gray-500 dark:text-gray-400 mr-2" />
              <span className="text-gray-700 dark:text-gray-300">
                Last seen:{' '}
              </span>
              <span className="text-gray-600 dark:text-gray-400 ml-auto">
                {client.lastSeen}
              </span>
            </div>
            <div className="flex items-center text-sm">
              <Activity className="w-4 h-4 text-gray-500 dark:text-gray-400 mr-2" />
              <span className="text-gray-700 dark:text-gray-300">
                Version:{' '}
              </span>
              <span className={`text-gray-600 dark:text-gray-400 ml-auto ${isArchonClient ? 'font-medium text-blue-600 dark:text-blue-400' : ''}`}>
                {client.version}
              </span>
            </div>
            {client.cpuUsage !== undefined && <div className="mt-4">
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-gray-600 dark:text-gray-400">CPU</span>
                  <span className={`${client.cpuUsage > 80 ? 'text-pink-500' : client.cpuUsage > 60 ? 'text-orange-500' : isArchonClient ? 'text-blue-500' : 'text-green-500'}`}>
                    {client.cpuUsage}%
                  </span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 overflow-hidden">
                  <div className={`h-1.5 rounded-full ${client.cpuUsage > 80 ? 'bg-pink-500' : client.cpuUsage > 60 ? 'bg-orange-500' : isArchonClient ? 'bg-gradient-r-animated' : 'bg-green-500'}`} style={{
                width: `${client.cpuUsage}%`
              }}></div>
                </div>
              </div>}
          </div>
          {/* Status badge - moved to bottom left */}
          <div className="absolute bottom-4 left-4">
            <div className={`px-2.5 py-1 rounded-full text-xs font-medium flex items-center gap-1.5 border ${currentStatus.badge}`}>
              <div className="relative flex h-2 w-2">
                <span className={`animate-ping-slow absolute inline-flex h-full w-full rounded-full ${currentStatus.pulse} opacity-75`}></span>
                <span className={`relative inline-flex rounded-full h-2 w-2 ${currentStatus.pulse}`}></span>
              </div>
              {client.status.charAt(0).toUpperCase() + client.status.slice(1)}
            </div>
          </div>
          {/* Tools button - with Hammer icon */}
          <button 
            onClick={toggleFlip} 
            className={`absolute bottom-4 right-4 p-1.5 rounded-full ${isArchonClient ? 'bg-blue-200/50 dark:bg-blue-900/50 hover:bg-blue-300/50 dark:hover:bg-blue-800/50' : 'bg-gray-200/50 dark:bg-gray-800/50 hover:bg-gray-300/50 dark:hover:bg-gray-700/50'} transition-colors transform hover:scale-110 transition-transform duration-200 z-10`} 
            title="View available tools"
          >
            <Hammer className={`w-4 h-4 ${isArchonClient ? 'text-blue-600 dark:text-blue-400' : 'text-gray-600 dark:text-gray-400'}`} />
          </button>
        </div>
        {/* Back Side */}
        <div className={`absolute w-full h-full backface-hidden backdrop-blur-md ${archonBackground} rounded-xl p-5 rotate-y-180 ${currentStatus.border} ${currentStatus.glow} transition-all duration-300 ${isArchonClient ? 'archon-card-border' : ''}`}>
          {/* Subtle aurora glow effect for Archon client */}
          {isArchonClient && <div className="absolute inset-0 rounded-xl overflow-hidden opacity-20">
              <div className="absolute -inset-[100px] bg-[radial-gradient(circle,rgba(59,130,246,0.8)_0%,rgba(168,85,247,0.6)_40%,transparent_70%)] blur-3xl animate-[pulse_8s_ease-in-out_infinite]"></div>
            </div>}
          <h3 className={`font-bold text-gray-800 dark:text-white mb-3 flex items-center ${isArchonClient ? 'bg-gradient-to-r from-blue-400 to-purple-500 text-transparent bg-clip-text animate-text-shimmer' : ''}`}>
            <Hammer className={`w-4 h-4 mr-2 ${isArchonClient ? 'text-blue-600 dark:text-blue-400' : 'text-gray-600 dark:text-gray-400'}`} />
            Available Tools
          </h3>
          <div className="space-y-2 overflow-y-auto max-h-[140px] pr-1 hide-scrollbar">
            {extendedTools.map(tool => <div key={tool.id} className={`p-2 rounded-md ${isArchonClient ? 'bg-blue-50/50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700/50 hover:border-blue-300 dark:hover:border-blue-600/50' : 'bg-gray-100/50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700/50 hover:border-gray-300 dark:hover:border-gray-600/50'} transition-colors transform hover:translate-x-1 transition-transform duration-200`}>
                <div className="flex items-center justify-between">
                  <span className={`font-mono text-xs ${isArchonClient ? 'text-blue-600 dark:text-blue-400' : 'text-blue-600 dark:text-blue-400'}`}>
                    {tool.name}
                  </span>
                  <ChevronRight className="w-3 h-3 text-gray-400" />
                </div>
                <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                  {tool.description}
                </p>
              </div>)}
          </div>
          {/* Status badge - also at bottom left on back side */}
          <div className="absolute bottom-4 left-4">
            <div className={`px-2.5 py-1 rounded-full text-xs font-medium flex items-center gap-1.5 border ${currentStatus.badge}`}>
              <div className="relative flex h-2 w-2">
                <span className={`animate-ping-slow absolute inline-flex h-full w-full rounded-full ${currentStatus.pulse} opacity-75`}></span>
                <span className={`relative inline-flex rounded-full h-2 w-2 ${currentStatus.pulse}`}></span>
              </div>
              {client.status.charAt(0).toUpperCase() + client.status.slice(1)}
            </div>
          </div>
          {/* Flip button - back to front */}
          <button 
            onClick={toggleFlip} 
            className={`absolute bottom-4 right-4 p-1.5 rounded-full ${isArchonClient ? 'bg-blue-200/50 dark:bg-blue-900/50 hover:bg-blue-300/50 dark:hover:bg-blue-800/50' : 'bg-gray-200/50 dark:bg-gray-800/50 hover:bg-gray-300/50 dark:hover:bg-gray-700/50'} transition-colors transform hover:scale-110 transition-transform duration-200 z-10`} 
            title="Show client details"
          >
            <Server className={`w-4 h-4 ${isArchonClient ? 'text-blue-600 dark:text-blue-400' : 'text-gray-600 dark:text-gray-400'}`} />
          </button>
        </div>
      </div>
    </div>;
};