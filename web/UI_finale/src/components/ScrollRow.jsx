import { useRef } from 'react';
import { useDragScroll } from '../hooks/useDragScroll';
import './ScrollRow.css';

export default function ScrollRow({ children, ariaLabel, className = '' }) {
  const ref = useRef(null);
  useDragScroll(ref);

  return (
    <div className={`scroll-row ${className}`} ref={ref} role="list" aria-label={ariaLabel}>
      {children}
    </div>
  );
}
