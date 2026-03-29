import { useNavigate } from 'react-router-dom';
import {
  TrendingUp,
  Flame,
  Calculator,
  Heart,
  ArrowRight,
  ShieldCheck,
  BarChart3,
  Zap,
  Globe,
  Bot
} from 'lucide-react';

const modules = [
  {
    title: 'Portfolio X-Ray',
    desc: 'Upload CAMS CAS PDF for deep MF analysis — XIRR, overlap detection, and rebalancing advice.',
    icon: TrendingUp,
    path: '/portfolio',
    accent: 'emerald',
    badge: 'AI Powered',
  },
  {
    title: 'FIRE Path Planner',
    desc: 'Calculate your retirement number, monthly SIP roadmap, and year-wise corpus projection.',
    icon: Flame,
    path: '/fire',
    accent: 'gold',
    badge: 'Goal Based',
  },
  {
    title: 'Tax Wizard',
    desc: 'Old vs New regime comparison from Form 16, discover missed deductions, and optimize taxes.',
    icon: Calculator,
    path: '/tax',
    accent: 'blue',
    badge: 'FY 2025-26',
  },
  {
    title: "Couple's Money Planner",
    desc: 'Joint financial optimization — combine salaries, split deductions, and maximize savings.',
    icon: Heart,
    path: '/couple',
    accent: 'purple',
    badge: 'Joint Plan',
  },
];

export default function Dashboard() {
  const navigate = useNavigate();

  return (
    <div className="reveal">
      {/* Dynamic Header */}
      <div className="hero-banner glass glow-emerald" style={{ padding: '3rem', border: 'none', position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: '-50px', right: '-50px', opacity: 0.1 }}>
             <Globe size={300} className="floating" />
        </div>
        
        <div className="hero-content reveal" style={{ maxWidth: '600px' }}>
          <div className="badge badge-emerald" style={{ marginBottom: '1rem' }}>
            <Zap size={10} style={{ marginRight: 4 }} /> 2 Agent Actions Today
          </div>
          <h1 style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>
            Your Intelligence <span className="text-gradient">Dashboard</span>
          </h1>
          <p style={{ fontSize: '1.05rem', opacity: 0.9 }}>
            Welcome back! FinSaarthi has finished scanning the latest market trends and your latest portfolio status. 
            Everything is on track.
          </p>
          <div style={{ marginTop: '2rem', display: 'flex', gap: '1rem' }}>
            <button className="btn btn-primary btn-lg" onClick={() => navigate('/portfolio')}>
              New Scan <ArrowRight size={18} />
            </button>
            <button className="btn btn-secondary btn-lg" onClick={() => navigate('/audit')}>
              View Logs
            </button>
          </div>
        </div>
      </div>

      {/* Grid of Key Stats */}
      <div className="grid grid-4" style={{ margin: '2rem 0' }}>
        <div className="stat-card glass reveal" style={{ animationDelay: '0.1s' }}>
          <div className="stat-icon emerald"><TrendingUp size={20} /></div>
          <div className="stat-info">
             <div className="stat-label">System State</div>
             <div className="stat-value" style={{ fontSize: '1.1rem', color: 'var(--accent-emerald)' }}>Live & Optimized</div>
          </div>
        </div>
        <div className="stat-card glass reveal" style={{ animationDelay: '0.2s' }}>
          <div className="stat-icon gold"><ShieldCheck size={20} /></div>
          <div className="stat-info">
             <div className="stat-label">Security</div>
             <div className="stat-value" style={{ fontSize: '1.1rem' }}>AES-256 Valid</div>
          </div>
        </div>
        <div className="stat-card glass reveal" style={{ animationDelay: '0.3s' }}>
          <div className="stat-icon blue"><BarChart3 size={20} /></div>
          <div className="stat-info">
             <div className="stat-label">Accuracy</div>
             <div className="stat-value" style={{ fontSize: '1.1rem' }}>99.8% Agent Score</div>
          </div>
        </div>
        <div className="stat-card glass reveal" style={{ animationDelay: '0.4s' }}>
          <div className="stat-icon purple"><Bot size={20} /></div>
          <div className="stat-info">
             <div className="stat-label">Agents Active</div>
             <div className="stat-value" style={{ fontSize: '1.1rem' }}>4 Specialized</div>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', marginTop: '3rem' }}>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 800 }}>Explore Modules</h2>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Scroll to discover all modules</span>
      </div>

      <div className="grid grid-2">
        {modules.map((mod, i) => (
          <div
            key={mod.path}
            className={`module-card glass reveal`}
            style={{ animationDelay: `${0.1 * (i + 5)}s`, border: '1px solid var(--glass-border)' }}
            onClick={() => navigate(mod.path)}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.5rem' }}>
                <div className={`stat-icon ${mod.accent}`} style={{ width: 50, height: 50 }}>
                   <mod.icon size={28} />
                </div>
                <span className={`badge badge-${mod.accent}`}>{mod.badge}</span>
            </div>
            <h3 style={{ fontSize: '1.25rem', marginBottom: '0.75rem' }}>{mod.title}</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1.5rem', minHeight: '3rem' }}>{mod.desc}</p>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-emerald)', fontSize: '0.85rem', fontWeight: 700 }}>
               Access Module <ArrowRight size={16} />
            </div>
          </div>
        ))}
      </div>
      
      <div style={{ marginTop: '4rem', padding: '3rem', textAlign: 'center' }} className="glass reveal">
          <Bot size={48} style={{ color: 'var(--accent-emerald)', marginBottom: '1rem' }} className="floating" />
          <h2 style={{ marginBottom: '1rem' }}>Need personalized advice?</h2>
          <p style={{ color: 'var(--text-secondary)', maxWidth: '500px', margin: '0 auto 2rem' }}>
            Our agents are ready to assist you in any of the modules above. Just select a module to begin the intelligence gathering process.
          </p>
          <button className="btn btn-secondary btn-lg" onClick={() => navigate('/portfolio')}>Start Portfolio Scan</button>
      </div>
    </div>
  );
}
