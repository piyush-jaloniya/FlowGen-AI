# 🚀 Quick Groq Setup (3 Minutes!)

Get **FREE** AI-powered code analysis in FlowGen AI!

## Steps:

### 1. Get Free Groq API Key
👉 Visit: **https://console.groq.com/keys**
- Sign up (free, no credit card!)
- Click "Create API Key"
- Copy the key (starts with `gsk_...`)

### 2. Create .env file
```bash
cd backend
copy .env.example .env
```

### 3. Add your key to .env
Open `backend/.env` and paste:
```env
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=llama-3.1-70b-versatile
```

### 4. Done! ✅
Backend will auto-reload. Generate a diagram and see AI insights!

---

## What You Get:
- 📝 **Code descriptions**
- 🎯 **Algorithm detection**  
- 💡 **Improvement suggestions**
- 🆓 **14,400 free requests/day!**

## Example Output:
```
🤖 AI Insights

📝 Description:
This code swaps the first and last elements of a list using 
tuple unpacking, then prints the modified list.

🎯 Algorithm Pattern: Data Structure Operation

💡 Suggestions:
- Add validation for empty or single-element lists
- Consider adding a function wrapper for reusability
```

**That's it!** Enjoy free AI-powered code analysis! 🎉
