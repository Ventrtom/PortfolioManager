import React, { useState } from 'react';

interface TooltipProps {
  content: string;
  children?: React.ReactNode;
}

const Tooltip: React.FC<TooltipProps> = ({ content, children }) => {
  const [visible, setVisible] = useState(false);

  return (
    <span className="tooltip">
      <button
        type="button"
        className="tooltip__trigger"
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
        onFocus={() => setVisible(true)}
        onBlur={() => setVisible(false)}
        aria-label={content}
        tabIndex={0}
      >
        {children || '?'}
      </button>
      {visible && (
        <div className="tooltip__content" role="tooltip">
          {content}
        </div>
      )}
    </span>
  );
};

export default Tooltip;
