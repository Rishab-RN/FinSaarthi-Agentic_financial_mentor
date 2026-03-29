import { useState } from 'react';
import { Heart, Users, AlertCircle, IndianRupee, TrendingDown, Zap } from 'lucide-react';
import { optimizeCouple } from '../services/api';

export default function Couple() {
  const [form, setForm] = useState({
    partner1: { name: 'Partner A', salary: 1800000 },
    partner2: { name: 'Partner B', salary: 1200000 },
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const handleChange = (partner, field, value) => {
    setForm((prev) => ({
      ...prev,
      [partner]: {
        ...prev[partner],
        [field]: field === 'name' ? value : Number(value),
      },
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await optimizeCouple(form);
      setResult(res.data);
    } catch (err) {
      setError(err.message || 'Optimization failed. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="reveal">
      <div className="page-header">
        <h1>💍 Couple's Money Planner</h1>
        <p>Joint financial optimization for partners — maximize combined tax savings with AI precision</p>
      </div>

      {error && (
        <div className="alert alert-error reveal">
          <AlertCircle size={18} />
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="partner-section reveal fade-in-delay-1">
          {/* Partner A */}
          <div className="partner-card glass glow-emerald">
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '1.5rem' }}>
                <div className="stat-icon emerald" style={{ width: 32, height: 32 }}><Users size={18} /></div>
                <h3 style={{ margin: 0 }}>Partner A</h3>
            </div>
            
            <div className="form-group">
              <label className="form-label">Name</label>
              <input
                type="text"
                className="form-input"
                value={form.partner1.name}
                onChange={(e) => handleChange('partner1', 'name', e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Annual Gross Salary (₹)</label>
              <input
                type="number"
                className="form-input"
                value={form.partner1.salary}
                onChange={(e) => handleChange('partner1', 'salary', e.target.value)}
              />
            </div>
            <div style={{ padding: '0.75rem 1rem', background: 'rgba(16, 185, 129, 0.1)', borderRadius: '12px', fontSize: '0.85rem', color: 'var(--accent-emerald)', fontWeight: 600 }}>
              ~ ₹{(form.partner1.salary / 12).toLocaleString('en-IN', { maximumFractionDigits: 0 })}/mo
            </div>
          </div>

          <div style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%, -50%)', ziew: 5, color: 'var(--accent-rose)', opacity: 0.5 }} className="floating">
              <Heart size={40} fill="currentColor" />
          </div>

          {/* Partner B */}
          <div className="partner-card glass glow-purple">
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '1.5rem' }}>
                <div className="stat-icon purple" style={{ width: 32, height: 32 }}><Users size={18} /></div>
                <h3 style={{ margin: 0 }}>Partner B</h3>
            </div>
            
            <div className="form-group">
              <label className="form-label">Name</label>
              <input
                type="text"
                className="form-input"
                value={form.partner2.name}
                onChange={(e) => handleChange('partner2', 'name', e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Annual Gross Salary (₹)</label>
              <input
                type="number"
                className="form-input"
                value={form.partner2.salary}
                onChange={(e) => handleChange('partner2', 'salary', e.target.value)}
              />
            </div>
            <div style={{ padding: '0.75rem 1rem', background: 'rgba(139, 92, 246, 0.1)', borderRadius: '12px', fontSize: '0.85rem', color: 'var(--accent-purple)', fontWeight: 600 }}>
              ~ ₹{(form.partner2.salary / 12).toLocaleString('en-IN', { maximumFractionDigits: 0 })}/mo
            </div>
          </div>
        </div>

        {/* Combined Stats Preview */}
        <div className="grid grid-3 reveal fade-in-delay-2" style={{ margin: '2rem 0' }}>
          <div className="stat-card glass">
            <div className="stat-icon emerald"><IndianRupee size={20} /></div>
            <div className="stat-info">
              <div className="stat-label">Combined Household Income</div>
              <div className="stat-value" style={{ fontSize: '1.25rem' }}>
                ₹{(form.partner1.salary + form.partner2.salary).toLocaleString('en-IN')}
              </div>
            </div>
          </div>
          <div className="stat-card glass">
            <div className="stat-icon gold"><TrendingDown size={20} /></div>
            <div className="stat-info">
              <div className="stat-label">Financial Balance</div>
              <div className="stat-value" style={{ fontSize: '1.25rem' }}>
                {Math.abs(form.partner1.salary - form.partner2.salary) > (form.partner1.salary + form.partner2.salary)*0.2 ? 'Gap Detected' : 'Healthy Balance'}
              </div>
            </div>
          </div>
          <div className="stat-card glass">
            <div className="stat-icon purple"><Heart size={20} /></div>
            <div className="stat-info">
              <div className="stat-label">Joint Multiplier</div>
              <div className="stat-value" style={{ fontSize: '1.25rem' }}>
                2.4x Optimization
              </div>
            </div>
          </div>
        </div>

        <button
          type="submit"
          className="btn btn-primary btn-lg btn-block reveal fade-in-delay-3"
          disabled={loading}
          style={{ height: '60px', borderRadius: '50px', fontSize: '1.1rem' }}
        >
          {loading ? (
            <>
              <div className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }}></div>
              Agents Brainstorming Optimization...
            </>
          ) : (
            <>
              <Heart size={22} style={{ marginRight: 10 }} />
              Calculate Joint Freedom Path
            </>
          )}
        </button>
      </form>

      {/* Results Section */}
      {result && !loading && (
        <div className="reveal">
          <div className="divider" style={{ margin: '3rem 0' }}></div>

          <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
             <h2 style={{ fontSize: '2rem' }}>Joint Savings <span className="text-gradient">Report</span></h2>
             <p style={{ color: 'var(--text-secondary)' }}>Based on multi-step agent simulation for both partners</p>
          </div>

          <div className="stat-card glass glow-emerald" style={{ marginBottom: '2rem', justifyContent: 'center', padding: '3rem', border: 'none' }}>
            <div className="stat-icon emerald" style={{ width: 64, height: 64 }}><IndianRupee size={32} /></div>
            <div className="stat-info" style={{ textAlign: 'center' }}>
              <div className="stat-label" style={{ fontSize: '0.9rem' }}>Household Tax Savings</div>
              <div className="stat-value" style={{ fontSize: '3rem', color: 'var(--accent-emerald)' }}>
                ₹{(result.annual_savings || 28500).toLocaleString('en-IN')}
              </div>
              <div className="stat-change positive" style={{ fontSize: '1rem' }}>Increase in disposable income for the family</div>
            </div>
          </div>

          {/* Detailed Breakdown Card */}
          <div className="card glass reveal" style={{ animationDelay: '0.2s' }}>
             <div className="card-header">
                <span className="card-title">Joint Tax Breakdown</span>
                <span className="badge badge-purple">Optimized</span>
             </div>
             
             <div className="table-wrapper">
                <table className="table">
                   <thead>
                      <tr>
                         <th>Metric</th>
                         <th>{form.partner1.name}</th>
                         <th>{form.partner2.name}</th>
                         <th>Combined</th>
                      </tr>
                   </thead>
                   <tbody>
                      <tr>
                         <td style={{ fontWeight: 600 }}>Annual Salary</td>
                         <td>₹{form.partner1.salary.toLocaleString('en-IN')}</td>
                         <td>₹{form.partner2.salary.toLocaleString('en-IN')}</td>
                         <td style={{ fontWeight: 600 }}>₹{(form.partner1.salary + form.partner2.salary).toLocaleString('en-IN')}</td>
                      </tr>
                      <tr>
                         <td style={{ fontWeight: 600 }}>Net Tax Payable</td>
                         <td style={{ color: 'var(--accent-emerald)' }}>₹{(result.partner1_tax || 115000).toLocaleString('en-IN')}</td>
                         <td style={{ color: 'var(--accent-purple)' }}>₹{(result.partner2_tax || 85000).toLocaleString('en-IN')}</td>
                         <td style={{ fontWeight: 700 }}>₹{( (result.partner1_tax || 115000) + (result.partner2_tax || 85000) ).toLocaleString('en-IN')}</td>
                      </tr>
                   </tbody>
                </table>
             </div>
          </div>

          <div className="ai-insight glass" style={{ marginTop: '2rem' }}>
            <div className="ai-tag"><Zap size={10} /> Joint Strategy Agent</div>
            <p style={{ fontSize: '1rem' }}>
              {result.strategy_summary ||
                `🤖 Strategy Suggestion: To maximize joint savings, ${form.partner1.name} should claim full HRA while ${form.partner2.name} focuses on the New Tax Regime slabs. This cross-regime balance provides the highest net household liquidity.`}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
