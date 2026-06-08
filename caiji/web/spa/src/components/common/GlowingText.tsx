import React from 'react';
import { motion } from 'framer-motion';

interface GlowingTextProps {
  children: React.ReactNode;
  className?: string;
  colorFrom?: string;
  colorTo?: string;
}

export const GlowingText: React.FC<GlowingTextProps> = ({ 
  children, 
  className = "",
  colorFrom = "#818cf8",
  colorTo = "#22d3ee"
}) => {
  return (
    <motion.span
      className={`relative inline-block bg-clip-text text-transparent bg-gradient-to-r from-[${colorFrom}] via-[${colorTo}] to-[${colorFrom}] bg-[length:200%_auto] ${className}`}
      animate={{
        backgroundPosition: ["0% center", "200% center"],
      }}
      transition={{
        duration: 4,
        repeat: Infinity,
        ease: "linear",
      }}
      style={{
        backgroundImage: `linear-gradient(to right, ${colorFrom}, ${colorTo}, ${colorFrom})`,
      }}
    >
      {children}
    </motion.span>
  );
};
