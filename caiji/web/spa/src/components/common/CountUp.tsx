import React, { useEffect, useState, useRef } from 'react';
import { useInView, animate } from 'framer-motion';

interface CountUpProps {
  to: number;
  from?: number;
  duration?: number;
  delay?: number;
  className?: string;
  decimals?: number;
  suffix?: string;
  prefix?: string;
}

export const CountUp: React.FC<CountUpProps> = ({
  to,
  from = 0,
  duration = 2,
  delay = 0,
  className = '',
  decimals = 0,
  suffix = '',
  prefix = '',
}) => {
  const [count, setCount] = useState(from);
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, amount: 0.5 });

  useEffect(() => {
    if (isInView) {
      const timeout = setTimeout(() => {
        const controls = animate(from, to, {
          duration,
          onUpdate: (value) => {
            setCount(value);
          },
          ease: "easeOut",
        });
        return () => controls.stop();
      }, delay * 1000);
      
      return () => clearTimeout(timeout);
    }
  }, [isInView, from, to, duration, delay]);

  return (
    <span ref={ref} className={className}>
      {prefix}
      {count.toLocaleString(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}
      {suffix}
    </span>
  );
};
