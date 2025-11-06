# 🤖 AI Integration Setup Guide

FlowGen AI now includes LLM-powered code analysis using **Groq** (free & fast!) or OpenAI GPT models!

## Features

### ✨ AI-Powered Analysis
- **Code Description**: Natural language explanation of what your code does
- **Algorithm Detection**: Automatically identifies patterns (Sorting, Searching, Recursion, etc.)
- **Smart Suggestions**: Get improvement recommendations for code quality and performance
- **Semantic Understanding**: Better flowchart labels using AI comprehension

## 🆓 Recommended: Groq API (FREE!)

### Why Groq?
- ✅ **Completely FREE** - 14,400 requests/day (that's ~600/hour!)
- ✅ **Lightning Fast** - 10x faster than OpenAI
- ✅ **Great Quality** - Uses Llama 3.1 70B model
- ✅ **No Credit Card** - Just sign up and get API key
- ✅ **High Limits** - 30 requests/minute

## Setup Instructions (Groq)

### 1. Install Dependencies (Already Done!)

```bash
cd backend
pip install openai python-dotenv
```

### 2. Get Free Groq API Key

1. Go to [https://console.groq.com/keys](https://console.groq.com/keys)
2. Sign up (free, no credit card needed)
3. Create a new API key
4. Copy the key (starts with `gsk_...`)

### 3. Configure Environment

Create a `.env` file in the `backend` folder:

```bash
cd backend
copy .env.example .env    # Windows
# or
cp .env.example .env      # Linux/Mac
```

Edit `.env` and add your Groq API key:

```env
# Groq API (Free & Fast - RECOMMENDED!)
GROQ_API_KEY=gsk_your_actual_groq_key_here
GROQ_MODEL=llama-3.1-70b-versatile
```

### 4. Model Options (Groq - All FREE!)

| Model | Speed | Quality | Context | Best For |
|-------|-------|---------|---------|----------|
| `llama-3.1-70b-versatile` | ⚡⚡ Fast | ⭐⭐⭐⭐ Excellent | 128K | **Recommended** - Best overall |
| `llama-3.1-8b-instant` | ⚡⚡⚡ Ultra Fast | ⭐⭐⭐ Good | 128K | Speed priority |
| `mixtral-8x7b-32768` | ⚡⚡ Fast | ⭐⭐⭐⭐ Excellent | 32K | Long code files |
| `gemma2-9b-it` | ⚡⚡ Fast | ⭐⭐⭐ Good | 8K | Google's model |

Update `GROQ_MODEL` in `.env` to your preferred model.

### 5. Restart Backend

```bash
# The backend should auto-reload!
# But if needed, restart:
cd backend
.\venv\Scripts\Activate.ps1    # Windows PowerShell
# or
source venv/bin/activate        # Linux/Mac

uvicorn app.main:app --reload
```

---

## Alternative: OpenAI API (Paid)

If you prefer OpenAI (paid but very high quality):

### Get OpenAI API Key

1. Go to [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Create a new API key
3. Copy the key (starts with `sk-...`)

### Configure for OpenAI

Edit `.env`:

```env
# Comment out Groq or remove it
# GROQ_API_KEY=...

# Add OpenAI
OPENAI_API_KEY=sk-your_actual_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

### OpenAI Model Options (Paid)

| Model | Speed | Quality | Cost | Best For |
|-------|-------|---------|------|----------|
| `gpt-4o-mini` | ⚡⚡⚡ Fast | ⭐⭐⭐ Good | 💰 Cheap | **Recommended** for paid |
| `gpt-4o` | ⚡⚡ Medium | ⭐⭐⭐⭐⭐ Excellent | 💰💰 Moderate | Highest quality |
| `gpt-3.5-turbo` | ⚡⚡⚡ Fast | ⭐⭐ Basic | 💰 Very Cheap | Budget |

---

## Usage

Once configured, AI insights will automatically appear when you generate diagrams:

1. Enter or upload code
2. Click "Generate Diagrams"
3. See AI insights below the button:
   - 📝 **Description**: What the code does
   - 🎯 **Algorithm Pattern**: Detected algorithm type
   - 💡 **Suggestions**: Code improvement tips

## Without API Key

The app works perfectly fine **without** any API key:
- All core features remain functional
- Uses spaCy NLP for basic semantic analysis
- AI insights section simply won't appear

## Cost Comparison

| Provider | Cost | Limits | Speed | Quality |
|----------|------|--------|-------|---------|
| **Groq** | **FREE!** | 14,400/day | ⚡⚡⚡ Ultra Fast | ⭐⭐⭐⭐ Excellent |
| OpenAI (mini) | ~$0.0001/req | Pay as you go | ⚡⚡ Fast | ⭐⭐⭐ Good |
| OpenAI (gpt-4o) | ~$0.001/req | Pay as you go | ⚡⚡ Medium | ⭐⭐⭐⭐⭐ Best |

**Groq is the clear winner for this use case!** 🏆

## Troubleshooting

### "OPENAI_API_KEY not found"
- Check if `.env` file exists in `backend` folder
- Verify the key starts with `sk-`
- Restart the backend server

### "OpenAI initialization failed"
- Verify your API key is valid
- Check your OpenAI account has credits
- Ensure internet connection is active

### AI insights not showing
- Check browser console (F12) for errors
- Verify backend logs for API errors
- API key might be invalid or out of credits

## Privacy & Security

⚠️ **Important**: 
- Your code is sent to OpenAI for analysis
- Keep your API key secret (never commit `.env` to Git)
- `.gitignore` already excludes `.env` files
- For sensitive code, don't enable LLM features

## Disabling AI Features

To disable LLM analysis:
1. Remove or comment out `OPENAI_API_KEY` in `.env`
2. Or delete the `.env` file
3. App will work normally without AI insights

---

**Questions?** Check the OpenAI documentation: https://platform.openai.com/docs
