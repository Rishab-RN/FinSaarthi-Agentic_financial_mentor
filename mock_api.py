"""
FinSaarthi — Zero-Dependency Mock API Server
==========================================
Minimalistic HTTP server using http.server to provide mock data for the 
FinSaarthi frontend without requiring external dependencies (like FastAPI).

Usage: python mock_api.py
Connects to: http://localhost:8000
"""

import json
import random
import http.server
import socketserver
from datetime import datetime

PORT = 8080

# Mock data generators
def get_portfolio_data():
    return {
        "success": True,
        "data": {
            "total_current_value": 1825000,
            "total_invested": 1450000,
            "avg_xirr": 16.4,
            "holdings": [
                {"name": "HDFC Mid-Cap Opportunities", "value": 450000, "invested": 350000, "xirr": 18.2},
                {"name": "Parag Parikh Flexi Cap", "value": 520000, "invested": 380000, "xirr": 14.5},
                {"name": "SBI Small Cap", "value": 315000, "invested": 220000, "xirr": 22.1},
                {"name": "ICICI Pru Balanced Adv", "value": 285000, "invested": 250000, "xirr": 9.8},
                {"name": "Nippon Liquid", "value": 255000, "invested": 250000, "xirr": 1.2}
            ],
            "rebalancing_plan": "⚠️ Portfolio Alert: Exposure to Small-Cap funds is currently 22.4%, which exceeds the 15% threshold for a 'Moderate' risk profile. Consider shifting dividends or profits to the HDFC Liquid or Nifty 50 Index fund for better stability.",
            "asset_allocation": {"Large Cap": 35, "Mid Cap": 25, "Small Cap": 22, "Flexi": 18}
        }
    }

def get_fire_data(req):
    # Simplified mock for FIRE
    age = req.get('current_age', 30)
    ret_age = req.get('target_retirement_age', 45)
    years = max(0, ret_age - age)
    fire_num = req.get('monthly_expenses', 50000) * 12 * 25
    sip = fire_num * 0.003 # naive mock
    
    return {
        "success": True,
        "data": {
            "fire_number": int(fire_num),
            "monthly_sip_required": int(sip),
            "years_to_fire": years,
            "year_wise_projection": [{"age": age + i, "corpus": int(sip*12*i*1.1)} for i in range(years + 1)]
        }
    }

class FinSaarthiMockHandler(http.server.BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Requested-With')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        if self.path == '/api/health':
            self._send_json({"status": "ok", "modules_loaded": ["portfolio", "fire", "tax", "couple"], "knowledge_base_ready": True, "timestamp": datetime.now().isoformat()})
        elif self.path == '/api/audit/recent':
            self._send_json([{"timestamp": datetime.now().isoformat(), "agent_name": "portfolio_agent", "action": "analyze_portfolio", "output_summary": "Analyzed 5 MF holdings", "tools_called": ["pdf_parser"], "duration_ms": 450}])
        elif self.path == '/api/portfolio/report':
            # This is a bit complex for http.server without actual PDF file, 
            # let's just send 404 for now or mock it if needed
            self.send_error(404, "Report not found in mock")
        else:
            self.send_error(404)

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        # Simple routing
        if '/api/portfolio/analyze' in self.path:
            # Note: Multipart/form-data is hard to parse manually in http.server, 
            # but we can just ignore it and return mock results.
            self._send_json(get_portfolio_data())
        elif '/api/fire/plan' in self.path:
            req = json.loads(post_data.decode('utf-8'))
            self._send_json(get_fire_data(req))
        elif '/api/tax/analyze' in self.path:
            self._send_json({
                "success": True, 
                "data": {
                    "old_regime_tax": 185000, "new_regime_tax": 142000, "recommended_regime": "new", 
                    "tax_saving_potential": 43000, "gross_salary": 1500000
                }
            })
        elif '/api/couple/optimize' in self.path:
            self._send_json({
                "success": True, 
                "data": {
                    "annual_savings": 28500, "partner1_tax": 115000, "partner2_tax": 85000, 
                    "strategy_summary": "🤖 AI Suggestion: Relocate ₹1.2L of HRA to Partner A for maximum joint tax reduction."
                }
            })
        else:
            self.send_error(404)

    def _send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

if __name__ == '__main__':
    with socketserver.TCPServer(("", PORT), FinSaarthiMockHandler) as httpd:
        print(f"🚀 FinSaarthi ZERO-DEP Mock Server running on http://localhost:{PORT}")
        httpd.serve_forever()
