# 🚀 Deploying FinSaarthi (Hackathon Demo)

Follow these steps to host your FinSaarthi project online for the judges.

## **1. Push All Changes**
I have already pushed your latest code to the `frontend` branch. Ensure the GitHub repo reflects this.

---

## **2. Deploy the Backend (Render)**
1. Go to [Render](https://render.com/).
2. Create **New Web Service**.
3. Point to your GitHub Repo and the `frontend` branch.
4. **Build Command**: `pip install -r requirements.txt`
5. **Start Command**: `python mock_api.py`
6. Note the URL (e.g., `https://finsaarthi-api.onrender.com`).

---

## **3. Update Frontend API**
Before the final frontend deploy, update this file with your Render URL:
**File**: `frontend/src/services/api.js`
```javascript
// Replace 127.0.0.1 with your Render URL
const API_BASE = 'https://finsaarthi-api.onrender.com/api'; 
```

---

## **4. Deploy the Frontend (Vercel)**
1. Go to [Vercel](https://vercel.com/).
2. **New Project** > Import GitHub Repo.
3. Select the `frontend` folder as the root.
4. Framework: **Vite**.
5. Click **Deploy**.

---

## **✅ Demo Day Configuration**
- **CORS**: Correctly handled in `mock_api.py`.
- **Base URL**: Ensure it points to the live backend.
- **Backend Status**: Verify the green dot in your sidebar is active!

**Good luck with the demo! 🏆**
