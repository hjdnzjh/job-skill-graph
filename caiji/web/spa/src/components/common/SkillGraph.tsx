import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { GraphNode, GraphLink } from '../../lib/mockData';

interface SkillGraphProps {
  data: {
    nodes: GraphNode[];
    links: GraphLink[];
  };
  onNodeClick?: (node: GraphNode) => void;
  width?: number | string;
  height?: number | string;
  editable?: boolean;
}

export function SkillGraph({ data, onNodeClick, width = '100%', height = 600, editable = false }: SkillGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [nodes, setNodes] = useState<(GraphNode & { x: number; y: number })[]>([]);
  const [links, setLinks] = useState<GraphLink[]>(data?.links || []);
  const [viewBox, setViewBox] = useState({ x: 0, y: 0, w: 1000, h: 1000 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [ripples, setRipples] = useState<{ id: number; x: number; y: number }[]>([]);

  // Initial layout: circular or random
  useEffect(() => {
    const initializedNodes = data.nodes.map((node, i) => {
      const angle = (i / data.nodes.length) * Math.PI * 2;
      const radius = node.type === 'job' ? 300 : 450;
      return {
        ...node,
        x: 500 + Math.cos(angle) * radius + (Math.random() - 0.5) * 100,
        y: 500 + Math.sin(angle) * radius + (Math.random() - 0.5) * 100,
      };
    });
    setNodes(initializedNodes);
    setLinks(data.links);
  }, [data]);

  const handleMouseDown = (e: React.MouseEvent) => {
    if ((e.target as SVGElement).tagName === 'svg') {
      setIsDragging(true);
      setDragStart({ x: e.clientX, y: e.clientY });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    const dx = e.clientX - dragStart.x;
    const dy = e.clientY - dragStart.y;
    setViewBox(prev => ({
      ...prev,
      x: prev.x - dx * (prev.w / 1000),
      y: prev.y - dy * (prev.h / 1000)
    }));
    setDragStart({ x: e.clientX, y: e.clientY });
  };

  const handleMouseUp = () => setIsDragging(false);

  const handleWheel = (e: React.WheelEvent) => {
    const scale = e.deltaY > 0 ? 1.1 : 0.9;
    setViewBox(prev => ({
      ...prev,
      w: prev.w * scale,
      h: prev.h * scale,
      x: prev.x + (prev.w * (1 - scale)) / 2,
      y: prev.y + (prev.h * (1 - scale)) / 2,
    }));
  };

  const handleNodeClick = (node: GraphNode & { x: number; y: number }, e: React.MouseEvent) => {
    e.stopPropagation();
    
    // Add ripple effect
    const newRipple = { id: Date.now(), x: node.x, y: node.y };
    setRipples(prev => [...prev, newRipple]);
    setTimeout(() => {
      setRipples(prev => prev.filter(r => r.id !== newRipple.id));
    }, 1000);

    if (onNodeClick) onNodeClick(node);
  };

  return (
    <div 
      ref={containerRef}
      className="relative overflow-hidden bg-slate-950/50 rounded-xl border border-slate-800 cursor-grab active:cursor-grabbing"
      style={{ width, height }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onWheel={handleWheel}
    >
      <svg 
        viewBox={`${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}`}
        className="w-full h-full"
      >
        <defs>
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="10" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
          <linearGradient id="linkGradient" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#6366f1" />
            <stop offset="100%" stopColor="#06b6d4" />
          </linearGradient>
        </defs>

        {/* Links */}
        {links.map((link, i) => {
          const source = nodes.find(n => n.id === link.source);
          const target = nodes.find(n => n.id === link.target);
          if (!source || !target) return null;
          
          return (
            <g key={`link-group-${i}`}>
              <motion.line
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 0.3 }}
                transition={{ duration: 1.5, delay: i * 0.05 }}
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                stroke="url(#linkGradient)"
                strokeWidth={2}
              />
              {/* Flowing light effect */}
              <motion.circle
                r={2}
                fill="#fff"
                filter="url(#glow)"
                animate={{
                  cx: [source.x, target.x],
                  cy: [source.y, target.y],
                  opacity: [0, 1, 0]
                }}
                transition={{
                  duration: 2 + Math.random() * 2,
                  repeat: Infinity,
                  ease: "linear",
                  delay: Math.random() * 5
                }}
              />
            </g>
          );
        })}

        {/* Ripples */}
        <AnimatePresence>
          {ripples.map(ripple => (
            <motion.circle
              key={ripple.id}
              cx={ripple.x}
              cy={ripple.y}
              initial={{ r: 0, opacity: 0.8 }}
              animate={{ r: 100, opacity: 0 }}
              exit={{ opacity: 0 }}
              stroke="#818cf8"
              strokeWidth={2}
              fill="none"
              transition={{ duration: 0.8, ease: "easeOut" }}
            />
          ))}
        </AnimatePresence>

        {/* Nodes */}
        {nodes.map((node, i) => (
          <motion.g
            key={node.id}
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ 
              type: "spring", 
              stiffness: 260, 
              damping: 20, 
              delay: i * 0.02 
            }}
            whileHover={{ scale: 1.2 }}
            className="cursor-pointer"
            onClick={(e) => handleNodeClick(node, e)}
          >
            {/* Node Glow */}
            <motion.circle
              r={node.type === 'job' ? 25 : 18}
              cx={node.x}
              cy={node.y}
              fill={node.type === 'job' ? '#6366f1' : '#06b6d4'}
              animate={{
                opacity: [0.3, 0.6, 0.3],
                scale: [1, 1.1, 1]
              }}
              transition={{
                duration: 2,
                repeat: Infinity,
                ease: "easeInOut",
                delay: Math.random() * 2
              }}
              filter="url(#glow)"
            />
            
            <circle
              r={node.type === 'job' ? 20 : 15}
              cx={node.x}
              cy={node.y}
              fill={node.type === 'job' ? '#4f46e5' : '#0891b2'}
              stroke="#fff"
              strokeWidth={2}
            />
            
            <text
              x={node.x}
              y={node.y + (node.type === 'job' ? 40 : 35)}
              textAnchor="middle"
              fill="#fff"
              fontSize={node.type === 'job' ? 14 : 12}
              fontWeight="bold"
              className="pointer-events-none select-none drop-shadow-md"
            >
              {node.label}
            </text>
          </motion.g>
        ))}
      </svg>
      
      {/* Background Star Points */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        {[...Array(50)].map((_, i) => (
          <motion.div
            key={i}
            className="absolute w-1 h-1 bg-white rounded-full"
            initial={{ 
              x: Math.random() * 100 + "%", 
              y: Math.random() * 100 + "%",
              opacity: Math.random() * 0.5
            }}
            animate={{ 
              opacity: [0.2, 0.8, 0.2],
              scale: [1, 1.5, 1]
            }}
            transition={{ 
              duration: Math.random() * 3 + 2, 
              repeat: Infinity,
              ease: "easeInOut"
            }}
          />
        ))}
      </div>
    </div>
  );
}
