import { useState } from 'react';
import './CalcTooltip.css';

interface CalcTooltipProps {
  formula: string;
  calculation: string;
  children: React.ReactNode;
}

const CalcTooltip = ({ formula, calculation, children }: CalcTooltipProps) => {
  const [showTooltip, setShowTooltip] = useState(false);

  return (
    <span
      className="calc-tooltip-wrapper"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      {children}
      <span className="calc-tooltip-icon">?</span>
      {showTooltip && (
        <div className="calc-tooltip-content">
          <div className="calc-formula">{formula}</div>
          <div className="calc-calculation">{calculation}</div>
        </div>
      )}
    </span>
  );
};

export default CalcTooltip;
