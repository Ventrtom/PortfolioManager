import { useState, useRef, useEffect } from 'react';
import './CalcTooltip.css';

interface CalcTooltipProps {
  formula: string;
  calculation: string;
  children: React.ReactNode;
}

interface TooltipPosition {
  top: number;
  left: number;
}

const CalcTooltip = ({ formula, calculation, children }: CalcTooltipProps) => {
  const [showTooltip, setShowTooltip] = useState(false);
  const [position, setPosition] = useState<TooltipPosition>({ top: 0, left: 0 });
  const wrapperRef = useRef<HTMLSpanElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (showTooltip && wrapperRef.current) {
      const rect = wrapperRef.current.getBoundingClientRect();
      const tooltipHeight = tooltipRef.current?.offsetHeight || 80;
      const tooltipWidth = tooltipRef.current?.offsetWidth || 300;

      // Position above the element, centered horizontally
      let top = rect.top - tooltipHeight - 10;
      let left = rect.left + rect.width / 2 - tooltipWidth / 2;

      // Keep tooltip within viewport bounds
      if (left < 10) left = 10;
      if (left + tooltipWidth > window.innerWidth - 10) {
        left = window.innerWidth - tooltipWidth - 10;
      }
      if (top < 10) {
        // Show below if not enough space above
        top = rect.bottom + 10;
      }

      setPosition({ top, left });
    }
  }, [showTooltip]);

  return (
    <span
      ref={wrapperRef}
      className="calc-tooltip-wrapper"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      {children}
      <span className="calc-tooltip-icon">?</span>
      {showTooltip && (
        <div
          ref={tooltipRef}
          className="calc-tooltip-content"
          style={{ top: position.top, left: position.left }}
        >
          <div className="calc-formula">{formula}</div>
          <div className="calc-calculation">{calculation}</div>
        </div>
      )}
    </span>
  );
};

export default CalcTooltip;
