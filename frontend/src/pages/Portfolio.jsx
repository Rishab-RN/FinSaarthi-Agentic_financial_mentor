import { useState } from 'react';
import { Upload, FileText, TrendingUp, AlertCircle, Download, PieChart } from 'lucide-react';
import { analyzePortfolio, downloadReport } from '../services/api';
import { PieChart as RechartsPie, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#8b5cf6', '#f43f5e', '#06b6d4', '#ec4899'];

export default function Portfolio() {
  const [file, setFile] = useState(null);
  const [risk, setRisk] = useState('moderate');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const handleFileChange = (e) => {
    const f = e.target.files[0];
    if (f && f.type === 'application/pdf') {
      setFile(f);
      setError('');
    }
  };

  const handleAnalyze = async () => {
    if (!file) {
      setError('Please upload a CAMS CAS PDF first.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await analyzePortfolio(file, risk);
      setResult(res.data);
    } catch (err) {
      setError(err.message || 'Analysis failed. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  // Build pie data from result
  const pieData = result?.holdings?.map((h, i) => ({
    name: h.name || `Fund ${i + 1}`,
    value: h.value || h.current_value || 0,
  })) || [];

  return (
    <div>
      <div className="page-header fade-in">
        <h1>📊 Portfolio X-Ray</h1>
        <p>Upload your CAMS CAS (Detail) statement for comprehensive MF analysis</p>
      </div>

      {error && (
        <div className="alert alert-error fade-in">
          <AlertCircle size={18} />
          {error}
        </div>
      )}

      {/* Upload Section */}
      <div className="grid grid-2 reveal fade-in-delay-1">
        <div className="card glass glow-emerald">
          <div className="card-header">
            <span className="card-title">Upload CAMS Statement</span>
            <span className="badge badge-emerald">PDF</span>
          </div>

          <label className={`file-upload glass ${file ? 'has-file' : ''}`}>
            <input
              type="file"
              accept=".pdf"
              onChange={handleFileChange}
              style={{ display: 'none' }}
              id="portfolio-upload"
            />
            {file ? (
              <>
                <FileText size={32} style={{ color: 'var(--accent-emerald)', marginBottom: '0.5rem' }} />
                <p className="file-name">{file.name}</p>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                  {(file.size / 1024).toFixed(1)} KB — Click to change
                </p>
              </>
            ) : (
              <>
                <Upload size={32} className="upload-icon" />
                <p>Click to upload your CAMS CAS PDF</p>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                  Supports CAS Detail Statement from CAMS/KFintech
                </p>
              </>
            )}
          </label>
        </div>

        <div className="card glass">
          <div className="card-header">
            <span className="card-title">Analysis Settings</span>
          </div>

          <div className="form-group">
            <label className="form-label">Risk Tolerance</label>
            <select
              className="form-select"
              value={risk}
              onChange={(e) => setRisk(e.target.value)}
            >
              <option value="conservative">Conservative</option>
              <option value="moderate">Moderate</option>
              <option value="aggressive">Aggressive</option>
            </select>
          </div>

          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: 1.6, marginBottom: '1.5rem' }}>
            The AI agent will analyze your portfolio allocation, calculate XIRR for each fund,
            detect overlap, and provide personalized rebalancing suggestions based on your risk profile.
          </p>

          <button
            className="btn btn-primary btn-lg btn-block"
            onClick={handleAnalyze}
            disabled={loading || !file}
          >
            {loading ? (
              <>
                <div className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }}></div>
                Analyzing...
              </>
            ) : (
              <>
                <TrendingUp size={18} />
                Analyze Portfolio
              </>
            )}
          </button>
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="loading-state fade-in" style={{ marginTop: '2rem' }}>
          <div className="spinner"></div>
          <p>Running agentic analysis on your portfolio...</p>
          <p style={{ fontSize: '0.75rem' }}>This may take a moment</p>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <div className="fade-in" style={{ marginTop: '2rem' }}>
          <div className="divider"></div>

          {/* Metrics */}
          <div className="grid grid-3" style={{ marginBottom: '1.5rem' }}>
            <div className="stat-card">
              <div className="stat-icon emerald"><TrendingUp size={20} /></div>
              <div className="stat-info">
                <div className="stat-label">Current Value</div>
                <div className="stat-value">₹{(result.total_current_value || 0).toLocaleString('en-IN')}</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon blue"><PieChart size={20} /></div>
              <div className="stat-info">
                <div className="stat-label">Total Invested</div>
                <div className="stat-value">₹{(result.total_invested || 0).toLocaleString('en-IN')}</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon gold"><TrendingUp size={20} /></div>
              <div className="stat-info">
                <div className="stat-label">Average XIRR</div>
                <div className="stat-value">{(result.avg_xirr || 0).toFixed(2)}%</div>
              </div>
            </div>
          </div>

          {/* Pie Chart */}
          {pieData.length > 0 && (
            <div className="card" style={{ marginBottom: '1.5rem' }}>
              <div className="card-header">
                <span className="card-title">Asset Allocation</span>
              </div>
              <ResponsiveContainer width="100%" height={300}>
                <RechartsPie>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    outerRadius={110}
                    innerRadius={60}
                    paddingAngle={3}
                    dataKey="value"
                    label={({ name, percent }) => `${name} (${(percent * 100).toFixed(1)}%)`}
                    labelLine={{ stroke: '#64748b' }}
                  >
                    {pieData.map((_, index) => (
                      <Cell key={index} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(val) => `₹${val.toLocaleString('en-IN')}`}
                    contentStyle={{
                      background: '#1a2235',
                      border: '1px solid rgba(255,255,255,0.06)',
                      borderRadius: 8,
                      color: '#f1f5f9',
                    }}
                  />
                </RechartsPie>
              </ResponsiveContainer>
            </div>
          )}

          {/* AI Insight */}
          <div className="ai-insight">
            <span className="ai-tag">AI</span>
            <p>{result.rebalancing_plan || 'Analysis complete. Review your holdings above for detailed insights.'}</p>
          </div>

          {/* Download Report */}
          <div style={{ marginTop: '1.25rem' }}>
            <button className="btn btn-secondary" onClick={downloadReport}>
              <Download size={16} /> Download PDF Report
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
