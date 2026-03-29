import { useState } from 'react';
import { Flame, Target, AlertCircle, TrendingUp, Wallet, Calendar } from 'lucide-react';
import { planFire } from '../services/api';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

export default function Fire() {
  const [form, setForm] = useState({
    current_age: 28,
    target_retirement_age: 45,
    monthly_income: 120000,
    monthly_expenses: 45000,
    existing_corpus: 800000,
    expected_return: 12,
    inflation_rate: 6,
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const handleChange = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: Number(value) }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await planFire(form);
      setResult(res.data);
    } catch (err) {
      setError(err.message || 'FIRE plan failed. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  // Generate projection data for chart
  const generateProjection = () => {
    if (!result) return [];
    const years = form.target_retirement_age - form.current_age;
    const monthlyGrowth = (form.expected_return / 100) / 12;
    const monthlySIP = result?.sip_calc?.monthly_sip_required || result?.fire_metrics?.monthly_sip_needed || 25000;
    let corpus = form.existing_corpus;
    const data = [];
    for (let y = 0; y <= years; y++) {
      data.push({
        age: form.current_age + y,
        corpus: Math.round(corpus),
      });
      for (let m = 0; m < 12; m++) {
        corpus = corpus * (1 + monthlyGrowth) + monthlySIP;
      }
    }
    return data;
  };

  const projData = generateProjection();

  const fireNumber = result?.fire_metrics?.fire_corpus || result?.fire_number || 0;
  const sipRequired = result?.sip_calc?.monthly_sip_required || result?.fire_metrics?.monthly_sip_needed || 0;

  return (
    <div>
      <div className="page-header fade-in">
        <h1>🔥 FIRE Path Planner</h1>
        <p>Calculate your Financial Independence, Retire Early number and SIP roadmap</p>
      </div>

      {error && (
        <div className="alert alert-error fade-in">
          <AlertCircle size={18} />
          {error}
        </div>
      )}

      <div className="grid grid-2 reveal fade-in-delay-1">
        {/* Form */}
        <div className="card glass glow-gold">
          <div className="card-header">
            <span className="card-title">Your Financial Profile</span>
            <span className="badge badge-gold">FIRE</span>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="grid grid-2">
              <div className="form-group">
                <label className="form-label">Current Age</label>
                <input
                  type="number"
                  className="form-input"
                  value={form.current_age}
                  onChange={(e) => handleChange('current_age', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Target Retirement Age</label>
                <input
                  type="number"
                  className="form-input"
                  value={form.target_retirement_age}
                  onChange={(e) => handleChange('target_retirement_age', e.target.value)}
                />
              </div>
            </div>

            <div className="grid grid-2">
              <div className="form-group">
                <label className="form-label">Monthly Income (₹)</label>
                <input
                  type="number"
                  className="form-input"
                  value={form.monthly_income}
                  onChange={(e) => handleChange('monthly_income', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Monthly Expenses (₹)</label>
                <input
                  type="number"
                  className="form-input"
                  value={form.monthly_expenses}
                  onChange={(e) => handleChange('monthly_expenses', e.target.value)}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Existing Corpus (₹)</label>
              <input
                type="number"
                className="form-input"
                value={form.existing_corpus}
                onChange={(e) => handleChange('existing_corpus', e.target.value)}
              />
            </div>

            <div className="range-group">
              <div className="range-header">
                <label className="form-label">Expected Return</label>
                <span className="range-value">{form.expected_return}%</span>
              </div>
              <input
                type="range"
                min="5"
                max="20"
                step="0.5"
                value={form.expected_return}
                onChange={(e) => handleChange('expected_return', e.target.value)}
              />
            </div>

            <div className="range-group">
              <div className="range-header">
                <label className="form-label">Inflation Rate</label>
                <span className="range-value">{form.inflation_rate}%</span>
              </div>
              <input
                type="range"
                min="3"
                max="10"
                step="0.5"
                value={form.inflation_rate}
                onChange={(e) => handleChange('inflation_rate', e.target.value)}
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary btn-lg btn-block"
              disabled={loading}
              style={{ marginTop: '0.5rem' }}
            >
              {loading ? (
                <>
                  <div className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }}></div>
                  Calculating...
                </>
              ) : (
                <>
                  <Target size={18} />
                  Calculate FIRE Path
                </>
              )}
            </button>
          </form>
        </div>

        {/* Results Panel */}
        <div>
          {result ? (
            <div className="fade-in">
              {/* Metrics */}
              <div className="stat-card" style={{ marginBottom: '1.25rem' }}>
                <div className="stat-icon gold"><Flame size={20} /></div>
                <div className="stat-info">
                  <div className="stat-label">FIRE Corpus Required</div>
                  <div className="stat-value">₹{fireNumber.toLocaleString('en-IN')}</div>
                  <div className="stat-change positive">
                    25x your annual expenses
                  </div>
                </div>
              </div>

              <div className="stat-card" style={{ marginBottom: '1.25rem' }}>
                <div className="stat-icon emerald"><Wallet size={20} /></div>
                <div className="stat-info">
                  <div className="stat-label">Monthly SIP Required</div>
                  <div className="stat-value">₹{sipRequired.toLocaleString('en-IN')}</div>
                </div>
              </div>

              <div className="stat-card" style={{ marginBottom: '1.25rem' }}>
                <div className="stat-icon blue"><Calendar size={20} /></div>
                <div className="stat-info">
                  <div className="stat-label">Years to FIRE</div>
                  <div className="stat-value">{form.target_retirement_age - form.current_age} years</div>
                </div>
              </div>

              {/* Projection Chart */}
              {projData.length > 0 && (
                <div className="card" style={{ marginTop: '0.5rem' }}>
                  <div className="card-header">
                    <span className="card-title">Corpus Growth Projection</span>
                  </div>
                  <ResponsiveContainer width="100%" height={250}>
                    <AreaChart data={projData}>
                      <defs>
                        <linearGradient id="colorCorpus" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis
                        dataKey="age"
                        stroke="#64748b"
                        fontSize={12}
                        tickLine={false}
                        label={{ value: 'Age', position: 'insideBottom', offset: -5, fill: '#64748b' }}
                      />
                      <YAxis
                        stroke="#64748b"
                        fontSize={12}
                        tickLine={false}
                        tickFormatter={(val) => `₹${(val / 100000).toFixed(0)}L`}
                      />
                      <Tooltip
                        contentStyle={{
                          background: '#1a2235',
                          border: '1px solid rgba(255,255,255,0.06)',
                          borderRadius: 8,
                          color: '#f1f5f9',
                        }}
                        formatter={(val) => [`₹${val.toLocaleString('en-IN')}`, 'Corpus']}
                        labelFormatter={(label) => `Age: ${label}`}
                      />
                      <Area
                        type="monotone"
                        dataKey="corpus"
                        stroke="#10b981"
                        strokeWidth={2}
                        fill="url(#colorCorpus)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}

              <div className="ai-insight" style={{ marginTop: '1.25rem' }}>
                <span className="ai-tag">AI</span>
                <p>
                  With ₹{form.monthly_expenses.toLocaleString('en-IN')}/mo expenses and {form.expected_return}% returns,
                  you need a ₹{fireNumber.toLocaleString('en-IN')} corpus to achieve FIRE by age {form.target_retirement_age}.
                  Start a monthly SIP of ₹{sipRequired.toLocaleString('en-IN')} today!
                </p>
              </div>
            </div>
          ) : (
            <div className="card" style={{ textAlign: 'center', padding: '4rem 2rem' }}>
              <Flame size={48} style={{ color: 'var(--accent-gold)', marginBottom: '1rem', opacity: 0.5 }} />
              <h3 style={{ color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>Plan Your FIRE Journey</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                Fill in your details and click "Calculate FIRE Path" to see your personalized retirement plan.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
