import React from 'react';

interface BadgeProps {
  type: 'required' | 'optional' | 'auto';
  className?: string;
}

const Badge: React.FC<BadgeProps> = ({ type, className = '' }) => {
  const badgeText = {
    required: 'Required',
    optional: 'Optional',
    auto: 'Auto-calculated'
  };

  const ariaLabel = {
    required: 'This field is required',
    optional: 'This field is optional',
    auto: 'This field is auto-calculated but can be overridden'
  };

  return (
    <span
      className={`form-field__badge form-field__badge--${type} ${className}`}
      aria-label={ariaLabel[type]}
      title={ariaLabel[type]}
    >
      {badgeText[type]}
    </span>
  );
};

export default Badge;
