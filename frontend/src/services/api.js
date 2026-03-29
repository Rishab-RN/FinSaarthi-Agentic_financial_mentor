const API_BASE = 'http://127.0.0.1:8000/api';

async function apiFetch(endpoint, options = {}) {
  try {
    const url = `${API_BASE}/${endpoint}`;
    const res = await fetch(url, options);
    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`API Error ${res.status}: ${errorText}`);
    }
    return await res.json();
  } catch (err) {
    console.error('API call failed:', err);
    throw err;
  }
}

export async function healthCheck() {
  return apiFetch('health');
}

export async function analyzePortfolio(file, riskProfile) {
  const formData = new FormData();
  formData.append('cams_pdf', file);
  formData.append('risk_profile', riskProfile);

  return apiFetch('portfolio/analyze', {
    method: 'POST',
    body: formData,
  });
}

export async function planFire(payload) {
  return apiFetch('fire/plan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function analyzeTax({ file, manualData }) {
  const formData = new FormData();
  if (file) {
    formData.append('form16_pdf', file);
  }
  if (manualData) {
    formData.append('manual_data', JSON.stringify(manualData));
  }

  return apiFetch('tax/analyze', {
    method: 'POST',
    body: formData,
  });
}

export async function optimizeCouple(payload) {
  return apiFetch('couple/optimize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function getAuditLogs() {
  return apiFetch('audit/recent');
}

export async function downloadReport() {
  const url = `${API_BASE}/portfolio/report`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Report download failed');
  const blob = await res.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'FinSaarthi_Financial_Report.pdf';
  a.click();
  URL.revokeObjectURL(a.href);
}
