import { useState } from 'react';
import {
  Calculator,
  Upload,
  FileText,
  AlertCircle,
  CheckCircle2,
  IndianRupee,
  Zap
} from 'lucide-react';
import { analyzeTax } from '../services/api';

export default function Tax() {
  const [activeTab, setActiveTab] = useState('manual');
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [manual, setManual] = useState({
    gross_salary: 1500000,
    basic: 600000,
    hra_received: 180000,
    rent_paid: 300000,
    city_type: 'metro',
    deductions_80c: 150000,
    deductions_80d: 25000,
    nps_80ccd: 50000,
    home_loan_interest: 0,
    other_deductions: 0,
  });

  const handleManualChange = (field, value) => {
    setManual((prev) => ({ ...prev, [field]: field === 'city_type' ? value : Number(value) }));
  };

  const handleFileUpload = (e) => {
    const f = e.target.files[0];
    if (f && f.type === 'application/pdf') {
      setFile(f);
      setError('');
    }
  };

  const handleAnalyze = async () => {
    setLoading(true);
    setError('');
    try {
      if (activeTab === 'upload') {
        if (!file) {
          setError('Please upload a Form 16 PDF.');
          setLoading(false);
          return;
        }
        const res = await analyzeTax({ file });
        setResult(res.data);
      } else {
        const res = await analyzeTax({ manualData: manual });
        setResult(res.data);
      }
    } catch (err) {
      setError(err.message || 'Tax analysis failed. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  const oldTax = result?.old_regime_tax || 0;
  const newTax = result?.new_regime_tax || 0;
  const recommended = result?.recommended_regime || '';
  const savings = result?.tax_saving_potential || Math.abs(oldTax - newTax);

  return (
    <div className="reveal">
      <div className="page-header">
        <h1>🧙‍♂️ Tax Wizard</h1>
        <p>Compare Old vs New tax regime and discover hidden savings with AI</p>
      </div>

      {error && (
        <div className="alert alert-error reveal">
          <AlertCircle size={18} />
          {error}
        </div>
      )}

      {/* Tabs */}
      <div className="tabs glass reveal fade-in-delay-1" style={{ maxWidth: '400px' }}>
        <button
          className={`tab-item ${activeTab === 'manual' ? 'active' : ''}`}
          onClick={() => setActiveTab('manual')}
        >
          <Calculator size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
          Manual Entry
        </button>
        <button
          className={`tab-item ${activeTab === 'upload' ? 'active' : ''}`}
          onClick={() => setActiveTab('upload')}
        >
          <Upload size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
          Upload Form 16
        </button>
      </div>

      <div className="reveal fade-in-delay-2">
        {activeTab === 'upload' ? (
          <div className="card glass glow-emerald" style={{ marginBottom: '1.5rem' }}>
            <div className="card-header">
              <span className="card-title">Form 16 (Part B)</span>
              <span className="badge badge-blue">PDF Analysis</span>
            </div>
            <label className={`file-upload glass ${file ? 'has-file' : ''}`}>
              <input type="file" accept=".pdf" onChange={handleFileUpload} style={{ display: 'none' }} />
              {file ? (
                <>
                  <FileText size={48} className="floating" style={{ color: 'var(--accent-emerald)', marginBottom: '1rem' }} />
                  <p className="file-name">{file.name}</p>
                  <p style={{ fontSize: '0.75rem', opacity: 0.6 }}>{(file.size/1024).toFixed(1)} KB</p>
                </>
              ) : (
                <>
                  <Upload size={48} className="upload-icon floating" />
                  <p style={{ fontSize: '1.1rem', fontWeight: 600 }}>Drop your Form 16 PDF here</p>
                  <p style={{ opacity: 0.6 }}>Our agent will extract income & deductions automatically</p>
                </>
              )}
            </label>
            <button
              className="btn btn-primary btn-lg btn-block"
              onClick={handleAnalyze}
              disabled={loading || !file}
              style={{ marginTop: '1.5rem', borderRadius: '50px' }}
            >
              {loading ? 'Agent Extracting Data...' : 'Analyze Form 16'}
            </button>
          </div>
        ) : (
          <div className="card glass" style={{ marginBottom: '1.5rem' }}>
            <div className="card-header">
              <span className="card-title">Income & Deduction Details</span>
              <span className="badge badge-blue">FY 2025-26</span>
            </div>

            <div className="grid grid-2">
              <div className="form-group">
                <label className="form-label">Gross Salary (₹)</label>
                <input
                  type="number"
                  className="form-input"
                  value={manual.gross_salary}
                  onChange={(e) => handleManualChange('gross_salary', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Basic Salary (₹)</label>
                <input
                  type="number"
                  className="form-input"
                  value={manual.basic}
                  onChange={(e) => handleManualChange('basic', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">HRA Received (₹)</label>
                <input
                  type="number"
                  className="form-input"
                  value={manual.hra_received}
                  onChange={(e) => handleManualChange('hra_received', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Annual Rent Paid (₹)</label>
                <input
                  type="number"
                  className="form-input"
                  value={manual.rent_paid}
                  onChange={(e) => handleManualChange('rent_paid', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">City Type</label>
                <select
                  className="form-select"
                  value={manual.city_type}
                  onChange={(e) => handleManualChange('city_type', e.target.value)}
                >
                  <option value="metro">Metro</option>
                  <option value="non-metro">Non-Metro</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">80C Investments (₹)</label>
                <input
                  type="number"
                  className="form-input"
                  value={manual.deductions_80c}
                  onChange={(e) => handleManualChange('deductions_80c', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">80D Health Insurance (₹)</label>
                <input
                  type="number"
                  className="form-input"
                  value={manual.deductions_80d}
                  onChange={(e) => handleManualChange('deductions_80d', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">NPS 80CCD(1B) (₹)</label>
                <input
                  type="number"
                  className="form-input"
                  value={manual.nps_80ccd}
                  onChange={(e) => handleManualChange('nps_80ccd', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Home Loan Interest (₹)</label>
                <input
                  type="number"
                  className="form-input"
                  value={manual.home_loan_interest}
                  onChange={(e) => handleManualChange('home_loan_interest', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Other Deductions (₹)</label>
                <input
                  type="number"
                  className="form-input"
                  value={manual.other_deductions}
                  onChange={(e) => handleManualChange('other_deductions', e.target.value)}
                />
              </div>
            </div>

            <button
              className="btn btn-primary btn-lg btn-block"
              onClick={handleAnalyze}
              disabled={loading}
              style={{ marginTop: '0.5rem', borderRadius: '50px' }}
            >
              {loading ? (
                <>
                  <div className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }}></div>
                  Agent Comparing Regimes...
                </>
              ) : (
                <>
                  <Calculator size={18} />
                  Calculate Optimization
                </>
              )}
            </button>
          </div>
        )}
      </div>

      {/* Results */}
      {result && !loading && (
        <div className="reveal">
          <div className="divider" style={{ margin: '3rem 0' }}></div>

          <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
             <h2 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>Optimization <span className="text-gradient">Results</span></h2>
             <p style={{ color: 'var(--text-secondary)' }}>Our agents compared both slabs across all your deductions</p>
          </div>

          {/* Regime Comparison */}
          <div className="regime-comparison" style={{ marginBottom: '2rem' }}>
            <div className={`regime-card glass ${recommended === 'old' ? 'recommended glow-emerald' : ''}`}>
              {recommended === 'old' && (
                <div className="badge badge-emerald" style={{ marginBottom: '1rem' }}>
                  <CheckCircle2 size={12} style={{ marginRight: 4 }} /> AI Preferred
                </div>
              )}
              <p className="regime-label">Old Tax Regime</p>
              <p className="regime-tax" style={{ color: recommended === 'old' ? 'var(--accent-emerald)' : 'var(--text-primary)' }}>
                ₹{oldTax.toLocaleString('en-IN')}
              </p>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>With all deductions applied</p>
            </div>

            <div className="vs-divider glass" style={{ borderRadius: '50%', width: 50, height: 50 }}>VS</div>

            <div className={`regime-card glass ${recommended === 'new' ? 'recommended glow-emerald' : ''}`}>
              {recommended === 'new' && (
                <div className="badge badge-emerald" style={{ marginBottom: '1rem' }}>
                  <CheckCircle2 size={12} style={{ marginRight: 4 }} /> AI Preferred
                </div>
              )}
              <p className="regime-label">New Tax Regime</p>
              <p className="regime-tax" style={{ color: recommended === 'new' ? 'var(--accent-emerald)' : 'var(--text-primary)' }}>
                ₹{newTax.toLocaleString('en-IN')}
              </p>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Flat slabs with standard deduction</p>
            </div>
          </div>

          {/* Savings Card */}
          <div className="stat-card glass glow-emerald" style={{ justifyContent: 'center', padding: '2rem', border: 'none' }}>
            <div className="stat-icon emerald" style={{ width: 60, height: 60 }}><IndianRupee size={30} /></div>
            <div className="stat-info" style={{ textAlign: 'center' }}>
              <div className="stat-label" style={{ fontSize: '0.9rem' }}>Annual Tax Savings</div>
              <div className="stat-value" style={{ fontSize: '2.5rem', color: 'var(--accent-emerald)' }}>
                ₹{savings.toLocaleString('en-IN')} /year
              </div>
              <div className="stat-change positive" style={{ fontSize: '1rem' }}>
                By opting for the {recommended.toUpperCase()} regime
              </div>
            </div>
          </div>

          <div className="ai-insight glass" style={{ marginTop: '2rem' }}>
            <div className="ai-tag"><Zap size={10} /> AI Agent Insight</div>
            <p style={{ fontSize: '1rem' }}>
               The <strong>{recommended.toUpperCase()} regime</strong> is clear winner for your profile. 
               {recommended === 'old' 
                 ? ` Your high investment velocity in 80C and rent payments (HRA) make the old regime significantly more efficient.` 
                 : ` Even with your deductions, the lower tax slabs and increased ₹75,000 standard deduction in the New Regime provide a better net outcome.`}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
