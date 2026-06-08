import React, { useRef, useEffect } from 'react';
import { motion, useInView, useAnimation, Variants } from 'framer-motion';

interface ScrollRevealProps {
  children: React.ReactNode;
  direction?: 'up' | 'down' | 'left' | 'right' | 'none';
  delay?: number;
  duration?: number;
  className?: string;
  distance?: number;
  once?: boolean;
  staggerChildren?: number;
}

export const ScrollReveal: React.FC<ScrollRevealProps> = ({
  children,
  direction = 'up',
  delay = 0,
  duration = 0.5,
  className = '',
  distance = 50,
  once = true,
  staggerChildren = 0,
}) => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once, amount: 0.2 });
  const controls = useAnimation();

  useEffect(() => {
    if (isInView) {
      controls.start('visible');
    }
  }, [isInView, controls]);

  const getHiddenOffset = () => {
    switch (direction) {
      case 'up': return { y: distance };
      case 'down': return { y: -distance };
      case 'left': return { x: distance };
      case 'right': return { x: -distance };
      default: return {};
    }
  };

  const variants: Variants = {
    hidden: {
      opacity: 0,
      ...getHiddenOffset(),
    },
    visible: {
      opacity: 1,
      x: 0,
      y: 0,
      transition: {
        duration,
        delay,
        ease: [0.25, 0.1, 0.25, 1],
        staggerChildren: staggerChildren > 0 ? staggerChildren : undefined,
      },
    },
  };

  return (
    <motion.div
      ref={ref}
      initial="hidden"
      animate={controls}
      variants={variants}
      className={className}
    >
      {children}
    </motion.div>
  );
};

export const StaggerContainer: React.FC<{ children: React.ReactNode, delay?: number, stagger?: number, className?: string }> = ({ 
  children, 
  delay = 0, 
  stagger = 0.1,
  className = "" 
}) => {
  return (
    <ScrollReveal 
      direction="none" 
      staggerChildren={stagger} 
      delay={delay}
      className={className}
    >
      {children}
    </ScrollReveal>
  );
};

export const StaggerItem: React.FC<{ children: React.ReactNode, direction?: 'up' | 'down' | 'left' | 'right' }> = ({ 
  children,
  direction = 'up'
}) => {
  const distance = 20;
  const getHiddenOffset = () => {
    switch (direction) {
      case 'up': return { y: distance };
      case 'down': return { y: -distance };
      case 'left': return { x: distance };
      case 'right': return { x: -distance };
      default: return { y: distance };
    }
  };

  return (
    <motion.div
      variants={{
        hidden: { opacity: 0, ...getHiddenOffset() },
        visible: { opacity: 1, x: 0, y: 0 }
      }}
    >
      {children}
    </motion.div>
  );
};
