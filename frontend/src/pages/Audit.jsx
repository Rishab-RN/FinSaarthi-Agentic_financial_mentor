import { useState, useEffect } from 'react';
import { ScrollText, RefreshCw, Clock, Bot, Wrench } from 'lucide-react';
import { getAuditLogs } from '../services/api';

export default function Audit() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const data = await getAuditLogs();
      setLogs(Array.isArray(data) ? data : []);
    } catch (err) {
      setError('Could not fetch audit logs. Is the backend running?');
      setLogs([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const formatTime = (ts) => {
    if (!ts) return '—';
    try {
      return new Date(ts).toLocaleString('en-IN', {
        dateStyle: 'short',
        timeStyle: 'medium',
      });
    } catch {
      return ts;
    }
  };

  return (
    <div>
      <div className="page-header fade-in">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1>📜 Agent Audit Log</h1>
            <p>Complete transparency into every AI agent action and tool call</p>
          </div>
          <button className="btn btn-secondary" onClick={fetchLogs} disabled={loading}>
            <RefreshCw size={16} className={loading ? 'animate-pulse' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert-error fade-in">
          {error}
        </div>
      )}

      {loading ? (
        <div className="loading-state fade-in">
          <div className="spinner"></div>
          <p>Loading audit logs...</p>
        </div>
      ) : logs.length === 0 ? (
        <div className="card fade-in" style={{ textAlign: 'center', padding: '4rem 2rem' }}>
          <ScrollText size={48} style={{ color: 'var(--text-muted)', marginBottom: '1rem', opacity: 0.4 }} />
          <h3 style={{ color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>No Audit Logs Yet</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            Run an analysis in any module to see agent actions recorded here.
          </p>
        </div>
      ) : (
        <div className="fade-in fade-in-delay-1">
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Agent</th>
                  <th>Action</th>
                  <th>Output Summary</th>
                  <th>Duration</th>
                  <th>Tools</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log, i) => (
                  <tr key={i}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Clock size={14} style={{ color: 'var(--text-muted)' }} />
                        {formatTime(log.timestamp)}
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Bot size={14} style={{ color: 'var(--accent-emerald)' }} />
                        <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
                          {log.agent_name || '—'}
                        </span>
                      </div>
                    </td>
                    <td>
                      <span className="badge badge-blue">{log.action || '—'}</span>
                    </td>
                    <td style={{ maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {log.output_summary || '—'}
                    </td>
                    <td>
                      {log.duration_ms ? `${log.duration_ms}ms` : '—'}
                    </td>
                    <td>
                      {log.tools_called && log.tools_called.length > 0 ? (
                        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                          {log.tools_called.map((tool, j) => (
                            <span key={j} className="badge badge-gold" style={{ fontSize: '0.6rem' }}>
                              <Wrench size={10} style={{ marginRight: 2 }} />
                              {tool}
                            </span>
                          ))}
                        </div>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ marginTop: '1rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Showing {logs.length} log entries
          </div>
        </div>
      )}
    </div>
  );
}
