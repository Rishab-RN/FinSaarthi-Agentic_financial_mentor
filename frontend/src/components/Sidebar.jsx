import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  TrendingUp,
  Flame,
  Calculator,
  Heart,
  ScrollText,
  Activity,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { healthCheck } from '../services/api';

const navItems = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/portfolio', label: 'Portfolio X-Ray', icon: TrendingUp },
  { path: '/fire', label: 'FIRE Planner', icon: Flame },
  { path: '/tax', label: 'Tax Wizard', icon: Calculator },
  { path: '/couple', label: 'Couple Planner', icon: Heart },
  { path: '/audit', label: 'Audit Log', icon: ScrollText },
];

export default function Sidebar() {
  const location = useLocation();
  const [isOnline, setIsOnline] = useState(false);

  useEffect(() => {
    healthCheck()
      .then(() => setIsOnline(true))
      .catch(() => setIsOnline(false));
  }, [location.pathname]);

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="logo-icon">₹</div>
        <div className="brand-text">
          <h2>FinSaarthi</h2>
          <span>AI Financial Mentor</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        <p className="nav-section-title">Modules</p>
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `nav-item ${isActive ? 'active' : ''}`
            }
            end={item.path === '/'}
          >
            <item.icon className="nav-icon" size={20} />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div style={{ display: 'flex', alignItems: 'center', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          <span className={`status-dot ${isOnline ? 'online' : 'offline'}`}></span>
          {isOnline ? 'Backend Connected' : 'Backend Offline'}
        </div>
        <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
          ET AI Hackathon 2026
        </div>
      </div>
    </aside>
  );
}
