import { ArrowRight, Shield, Zap, TrendingUp, PieChart, Heart, MousePointer2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function Landing() {
  const navigate = useNavigate();

  return (
    <div className="landing-wrapper">
      {/* Animated Blobs */}
      <div className="landing-blob" style={{ top: '-10%', right: '-5%' }}></div>
      <div className="landing-blob" style={{ bottom: '10%', left: '-10%', background: 'radial-gradient(circle, var(--accent-purple-dim) 0%, transparent 70%)' }}></div>

      {/* Navbar */}
      <nav className="navbar-landing glass">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ background: 'var(--gradient-emerald)', padding: '8px', borderRadius: '8px', color: 'white' }}>
            <TrendingUp size={24} />
          </div>
          <span style={{ fontSize: '1.25rem', fontWeight: 800, letterSpacing: '-0.5px' }}>FinSaarthi</span>
        </div>
        <div style={{ display: 'flex', gap: '30px' }}>
          <a href="#features" style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', fontWeight: 500 }}>Features</a>
          <button 
            onClick={() => navigate('/dashboard')}
            className="btn btn-primary" 
            style={{ padding: '0.5rem 1.25rem' }}
          >
            Launch App
          </button>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="hero-section">
        <div className="reveal">
          <div className="hero-tag">AI-Powered Financial Intelligence</div>
          <h1 className="hero-title">
            Your Money, <br />
            <span className="text-gradient">Agentically Optimized.</span>
          </h1>
          <p className="hero-subtitle">
            FinSaarthi is the first multi-agent financial mentor that analyzes your portfolio, 
            plans your retirement, and optimizes your taxes with surgical precision.
          </p>
          <div style={{ display: 'flex', gap: '20px', justifyContent: 'center' }}>
            <button 
              onClick={() => navigate('/dashboard')}
              className="btn btn-primary btn-lg glow-emerald"
              style={{ padding: '1rem 2.5rem', borderRadius: '50px' }}
            >
              Get Started for Free <ArrowRight size={20} style={{ marginLeft: 8 }} />
            </button>
            <button className="btn btn-secondary btn-lg" style={{ padding: '1rem 2.5rem', borderRadius: '50px' }}>
              Watch Demo
            </button>
          </div>
        </div>

        {/* Mockup Preview */}
        <div className="hero-mockup floating reveal" style={{ animationDelay: '0.2s' }}>
          <div style={{ padding: '20px', background: 'var(--bg-primary)', borderRadius: '12px' }}>
             <div className="grid grid-3" style={{ marginBottom: '20px' }}>
                <div className="stat-card glass" style={{ border: 'none' }}>
                  <div className="stat-info">
                    <div className="stat-label">Net Worth</div>
                    <div className="stat-value">₹84.2L</div>
                  </div>
                </div>
                <div className="stat-card glass" style={{ border: 'none' }}>
                  <div className="stat-info">
                    <div className="stat-label">Tax Saved</div>
                    <div className="stat-value" style={{ color: 'var(--accent-emerald)' }}>₹1.2L</div>
                  </div>
                </div>
                <div className="stat-card glass" style={{ border: 'none' }}>
                  <div className="stat-info">
                    <div className="stat-label">FIRE Date</div>
                    <div className="stat-value" style={{ color: 'var(--accent-gold)' }}>Sept 2034</div>
                  </div>
                </div>
             </div>
             <div style={{ height: '200px', background: 'rgba(255,255,255,0.03)', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>Interactive Financial Projection Chart</span>
             </div>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section id="features" className="feature-grid-landing">
        <div className="feature-card-landing glass reveal" style={{ animationDelay: '0.3s' }}>
          <div className="stat-icon emerald" style={{ marginBottom: '20px' }}><PieChart /></div>
          <h3 style={{ marginBottom: '12px' }}>Portfolio X-Ray</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Upload your CAMS statement and let our agents detect overlaps, calculate XIRR, 
            and suggest rebalancing strategies.
          </p>
        </div>
        <div className="feature-card-landing glass reveal" style={{ animationDelay: '0.4s' }}>
          <div className="stat-icon gold" style={{ marginBottom: '20px' }}><Zap /></div>
          <h3 style={{ marginBottom: '12px' }}>Fire Path Planner</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Calculate exactly when you can retire based on your current lifestyle and 
            investment velocity.
          </p>
        </div>
        <div className="feature-card-landing glass reveal" style={{ animationDelay: '0.5s' }}>
          <div className="stat-icon purple" style={{ marginBottom: '20px' }}><Shield /></div>
          <h3 style={{ marginBottom: '12px' }}>Tax Wizard</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Compare Old vs New regime automatically using Form 16 and maximize your 
            80C/80D deductions.
          </p>
        </div>
        <div className="feature-card-landing glass reveal" style={{ animationDelay: '0.6s' }}>
          <div className="stat-icon rose" style={{ marginBottom: '20px' }}><Heart /></div>
          <h3 style={{ marginBottom: '12px' }}>Couple's Planner</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Joint financial optimization for partners. Maximize combined tax savings 
            and reach mutual goals faster.
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer style={{ padding: '60px 5%', borderTop: '1px solid var(--glass-border)', textAlign: 'center' }}>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
          &copy; 2026 FinSaarthi AI. Built for the ET AI Hackathon.
        </p>
      </footer>
    </div>
  );
}
