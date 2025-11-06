# 🤖 Google Gemini API Setup - FREE!

Get AI-powered code analysis in your FlowGen AI app using Google's free Gemini API.

## ⚡ Quick Setup (3 minutes)

### Step 1: Get Your Free API Key

1. Visit: **https://aistudio.google.com/app/apikey**
2. Sign in with your Google account
3. Click **"Create API Key"** button
4. Copy the generated key

### Step 2: Configure the App

1. Open `backend/.env` file
2. Replace `your_gemini_api_key_here` with your actual API key:
   ```env
   GEMINI_API_KEY=AIzaSy...your_actual_key_here
   ```
3. Save the file

### Step 3: Restart Backend

- The backend should auto-reload
- If not, restart it manually

### Step 4: Test It!

1. Open http://localhost:3000
2. Upload a code file or paste code
3. Click "Generate Diagrams"
4. Click the **🤖 AI Insights** tab
5. See AI-powered explanations and improvements!

## 📊 Available Models

The `.env` file is configured to use `gemini-1.5-flash` (recommended):

- **gemini-1.5-flash** - Fast, efficient, FREE ✅
- **gemini-1.5-pro** - More powerful, still FREE
- **gemini-2.0-flash-exp** - Experimental, latest features

## 🆓 Pricing

- **100% FREE** for standard usage
- Rate limits: 15 requests/minute, 1500 requests/day
- Perfect for development and personal projects!

## 🎯 What You Get

With Gemini AI integration, you get:

✅ **Code Explanation** - Natural language description of what your code does  
✅ **Algorithm Detection** - Automatically identifies patterns (Sorting, Searching, etc.)  
✅ **Code Improvements** - Actionable suggestions to improve your code  
✅ **Copy to Clipboard** - Easy copy buttons for all insights

## ❓ Troubleshooting

### Backend shows "No Gemini API key found"
- Check that `.env` file exists in `backend/` folder
- Verify the key starts with `AIzaSy`
- Make sure there are no extra spaces

### AI Insights tab is disabled
- Make sure backend restarted after adding the API key
- Check browser console (F12) for errors
- Verify backend shows "Using Google Gemini" in startup logs

### API errors
- Verify your API key is valid
- Check you haven't exceeded rate limits
- Try regenerating your API key

## 🔗 Resources

- API Key Dashboard: https://aistudio.google.com/app/apikey
- Gemini Documentation: https://ai.google.dev/docs
- Rate Limits: https://ai.google.dev/pricing

---

**Made with ❤️ - Enjoy your AI-powered code visualization!**
