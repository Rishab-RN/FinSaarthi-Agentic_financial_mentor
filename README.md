# FinSaarthi — AI-Powered Personal Financial Mentor

FinSaarthi is a multi-agent financial planning system that helps you manage your portfolio, plan for retirement (FIRE), optimize taxes, and coordinate finances with your partner.

## Tech Stack
- **Backend:** FastAPI, LangGraph, Google Gemini Pro
- **Agents:** Multi-agent system for specialized financial modules.
- **Frontend:** Streamlit for a premium user experience.
- **RAG:** Knowledge base for tax and investment advice.

## How to Run

1. **Setup Environment:**
   Create a `.env` file and add your `GOOGLE_API_KEY`:
   ```env
   GOOGLE_API_KEY=your_genai_api_key_here
   ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the Backend:**
   ```bash
   python api.py
   ```

4. **Start the Frontend:**
   ```bash
   streamlit run app.py
   ```

## Key Modules
- **📊 Portfolio X-Ray:** Asset allocation and performance analysis from CAMS PDF.
- **🔥 FIRE Planner:** Retire early with goal-based SIP roadmaps.
- **🧙‍♂️ Tax Wizard:** Regime comparison and deduction discovery.
- **💍 Couple's Money Planner:** Joint financial optimization for partners.
