
import './OrbitLogo.css';

export default function OrbitLogo({ size = 44, showName = true }) {
  return (
    <div className="orbit-brand">
      <div
        className="orbit-logo"
        style={{ '--logo-size': `${size}px` }}
        aria-label="Invoice Keeper"
        role="img"
      >
        <svg
          className="orbit-logo__svg"
          viewBox="0 0 100 100"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <defs>
            <linearGradient id="orbit-cyan" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#55D3E3" />
              <stop offset="100%" stopColor="#16B9CF" />
            </linearGradient>
          </defs>

          {/* Outer orbital ring */}
          <ellipse
            className="orbit-ring orbit-ring--outer"
            cx="50"
            cy="50"
            rx="43"
            ry="19"
            transform="rotate(-35 50 50)"
          />

          {/* Inner orbital ring */}
          <ellipse
            className="orbit-ring orbit-ring--inner"
            cx="50"
            cy="50"
            rx="35"
            ry="15"
            transform="rotate(48 50 50)"
          />

          {/* Orbiting particles */}
          <circle
            className="orbit-dot orbit-dot--one"
            cx="50"
            cy="7"
            r="4"
          />
          <circle
            className="orbit-dot orbit-dot--two"
            cx="91"
            cy="50"
            r="3"
          />

          {/* Central coin */}
          <circle
            className="orbit-coin"
            cx="50"
            cy="50"
            r="20"
          />

          {/* Invoice monogram */}
          <path
            className="orbit-monogram"
            d="M42 39 H58 M50 39 V61 M42 61 H58"
          />
        </svg>
      </div>

      {showName && (
        <div className="orbit-brand__text">
          <span className="orbit-brand__title">Invoice<span> </span>Keeper</span>
        </div>
      )}
    </div>
  );
}
