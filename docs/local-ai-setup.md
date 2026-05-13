# Running AI Locally with Ollama

This guide walks you through installing **Ollama** — the tool that lets PrivateAI run an AI model entirely on your own computer, with no internet connection required and no data sent anywhere.

**You do not need a technical background to follow this guide.** Every step is explained in plain language.

---

## First — which AI companies actually offer local/offline models?

This is one of the most common points of confusion, so let us clear it up before anything else.

| Company | Can you run their AI locally? | Why |
|---|---|---|
| **Meta** | ✅ Yes | Released **Llama** as open-weight models — free to download and run on your own machine |
| **Google** | ✅ Yes | Released **Gemma** as open-weight models — free to download and run on your own machine |
| **Mistral AI** | ✅ Yes | French AI company, released **Mistral** and **Mixtral** as open-weight models |
| **Microsoft** | ✅ Yes | Released **Phi** as open-weight models — surprisingly capable for their small size |
| **OpenAI** | ❌ No | GPT-4, GPT-4o, and all ChatGPT models are **cloud-only**. They require an internet connection and API key. OpenAI has not released any conversational AI models for local use. |
| **Anthropic** | ❌ No | Claude (all versions) is **cloud-only**. Anthropic has not released any models for local use. |

> **What does "open-weight" mean?** It means the company has published the AI model's internal numbers (its "weights") for anyone to download and use for free. It is the AI equivalent of open-source software. Meta, Google, Mistral, and Microsoft have done this. OpenAI and Anthropic have not.

PrivateAI uses **Meta's Llama models** by default, with Google's Gemma and Mistral as excellent alternatives — all free, all running on your machine.

---

## Before you start — do you need this?

PrivateAI works in two modes:

| Mode | What it uses | Cost | Data leaves your machine? |
|---|---|---|---|
| **Local AI** (this guide) | Ollama on your computer | Free | Never |
| **Cloud AI** (default fallback) | OpenAI GPT-4o | ~$0.01–0.10 per conversation | Yes, to OpenAI |

If maximum privacy is your goal, local AI is the right choice. If you just want to get started quickly, you can skip this guide and use the OpenAI fallback — just add your API key in Settings.

---

## Step 1 — Understand the two types of memory

This is the one technical concept worth understanding before you pick a model.

Your computer has **two completely separate pools of memory**:

| Memory type | What it's called | What it does | Where to find it |
|---|---|---|---|
| **System RAM** | RAM, Memory | Your computer's main working memory. Used for everything — your browser, apps, files. | "16 GB RAM" on a laptop spec sheet |
| **GPU VRAM** | Video RAM, VRAM, Graphics Memory | Memory built into your graphics card (GPU). AI models run here when a GPU is present. | "8 GB GDDR6" on a graphics card spec |

**Why does this matter?**
- If you have **no graphics card**, AI models run on your system RAM. This works fine but is slower.
- If you have **a graphics card**, AI models run on VRAM. This is much faster — but VRAM is typically smaller than system RAM, so it limits which model sizes you can use.

> **The golden rule:** The AI model must fit in whichever memory it runs in. A 7B model needs roughly 5–6 GB. A 70B model needs roughly 40 GB. If it does not fit, Ollama cannot run it (or will run it very slowly by using a mix of both).

---

## Step 2 — Check your hardware

### Check your system RAM

- **Windows:** Press `Windows + R`, type `dxdiag`, press Enter. Look for "Memory."
- **Mac:** Click the Apple menu → About This Mac → look for "Memory."
- **Linux:** Open a terminal and type `free -h`.

### Check your GPU and VRAM (if you have one)

- **Windows:** Press `Ctrl + Shift + Esc` to open Task Manager → click the "Performance" tab → click "GPU." You will see your GPU name and its dedicated memory (VRAM).
- **Mac:** Click the Apple menu → About This Mac → More Info → System Report → Graphics/Displays.
- **Linux:** Run `nvidia-smi` (NVIDIA) or `rocm-smi` (AMD) in a terminal.

> **Not sure if you have a GPU?** Most laptops have only integrated graphics (built into the processor), which does not have its own VRAM. Desktop computers are more likely to have a dedicated GPU. Ollama works with both — a dedicated GPU just makes things faster.

---

## Step 3 — GPU cards and what they can run

If you are considering buying a GPU specifically to run local AI, or want to know what your existing card supports, use this reference.

### NVIDIA GeForce (consumer / gaming cards)

| Card | VRAM | Models it can run comfortably |
|---|---|---|
| RTX 4060 / 3060 | 8 GB | Llama 3.2 3B, Gemma 2 2B, Phi-3 mini, Mistral 7B (just fits) |
| RTX 4060 Ti | 8 GB or 16 GB | 8 GB: same as above · 16 GB: Llama 3.1 8B, Mistral 7B with room to spare |
| RTX 4070 / 3070 | 8–12 GB | Llama 3.1 8B, Mistral 7B, Gemma 2 9B |
| RTX 4070 Super | 12 GB | Llama 3.1 8B, Mistral 7B comfortably |
| RTX 4080 / 3080 | 10–16 GB | Llama 3.1 8B, Gemma 2 9B easily; 13B models possible |
| RTX 4090 / 3090 | 24 GB | Llama 3.1 8B, Gemma 2 27B, Mixtral 8x7B, most 13B models |
| RTX 3090 Ti | 24 GB | Same as RTX 4090 for AI purposes |

> **Budget recommendation:** The **RTX 4060 Ti 16 GB** (~$400–500) is currently the best value card for running local AI. The 16 GB VRAM version comfortably runs 8B models that produce high-quality answers.

### AMD Radeon (consumer cards)

| Card | VRAM | Models it can run comfortably |
|---|---|---|
| RX 7600 | 8 GB | Llama 3.2 3B, Phi-3 mini, smaller 7B models |
| RX 7700 XT | 12 GB | Llama 3.1 8B, Mistral 7B |
| RX 7800 XT | 16 GB | Llama 3.1 8B, Gemma 2 9B comfortably |
| RX 7900 GRE | 16 GB | Llama 3.1 8B, Mistral 7B easily |
| RX 7900 XTX | 24 GB | Llama 3.1 8B, Gemma 2 27B, most 13B models |

> **Note on AMD:** AMD cards work with Ollama but require slightly more setup than NVIDIA. If you are buying specifically for local AI, NVIDIA currently has broader support and is the safer choice.

### Apple Silicon (M1 / M2 / M3 / M4)

Apple Silicon Macs are in a class of their own for local AI. Because the CPU and GPU share the same memory pool, the full system memory is available to AI models — there is no separate VRAM limit.

| Chip | Unified Memory | Models it can run comfortably |
|---|---|---|
| M1 / M2 (base) | 8 GB | Llama 3.2 3B, Phi-3 mini |
| M1 / M2 (16 GB) | 16 GB | Llama 3.1 8B, Mistral 7B |
| M1 Pro / M2 Pro | 16–32 GB | Llama 3.1 8B easily; 32 GB: 27B models |
| M1 Max / M2 Max | 32–64 GB | 27B–70B models |
| M1 Ultra / M2 Ultra | 64–192 GB | 70B models comfortably |
| M3 / M4 (any tier) | Same as equivalent M2 | Same as above — faster per watt |

> Apple Silicon is **the most efficient option** for local AI. An M2 MacBook Pro with 16 GB runs 8B models faster than a desktop with an RTX 3070. If you are buying new hardware specifically for private AI, a MacBook Pro or Mac Mini with 16–32 GB unified memory is an excellent choice.

### NVIDIA workstation / data center cards

These are for teams or power users who need to run very large models.

| Card | VRAM | What it unlocks |
|---|---|---|
| RTX 4000 Ada | 20 GB | 13B models comfortably |
| RTX 6000 Ada | 48 GB | 70B models |
| A100 | 40 or 80 GB | 70B models, multiple users simultaneously |
| H100 | 80 GB | 70B+ models at high speed |

> These cards cost thousands to tens of thousands of dollars. For a personal or small-team deployment of PrivateAI, consumer cards or Apple Silicon are the right choice.

---

## Step 4 — Choose a model by your hardware

| Your hardware | Best model to start with | Quality level |
|---|---|---|
| No GPU, 8 GB RAM | `llama3.2:1b` or `phi3.5:mini` | Good for simple Q&A |
| No GPU, 16 GB RAM | `llama3.2:3b` or `mistral` | Solid for document analysis |
| No GPU, 32 GB RAM | `llama3.1:8b` | Excellent, near GPT-3.5 level |
| GPU with 8 GB VRAM | `llama3.1:8b` or `mistral` | Excellent, fast responses |
| GPU with 12–16 GB VRAM | `llama3.1:8b`, `gemma2:9b` | Excellent, very fast |
| GPU with 24 GB VRAM | `gemma2:27b` or `llama3.1:8b` | Outstanding |
| Apple Silicon 8 GB | `llama3.2:3b` | Solid |
| Apple Silicon 16 GB | `llama3.1:8b` or `mistral` | Excellent, fast |
| Apple Silicon 32 GB+ | `gemma2:27b` | Outstanding |

### What do 1b, 3b, 8b, 27b, 70b mean?

These numbers stand for **billion parameters** — the internal values that define how the model thinks. Think of it like engine displacement in a car: a larger number generally means more capable reasoning, but requires more memory and runs slower.

| Size | Parameters | Capability |
|---|---|---|
| 1B | 1 billion | Fast, lightweight. Good for simple questions and short documents. |
| 3B | 3 billion | Noticeably smarter. Good for most document Q&A tasks. |
| 7B–8B | 7–8 billion | Strong reasoning. Handles complex documents well. Roughly GPT-3.5 level. |
| 13B | 13 billion | Very capable. Close to early GPT-4 for many tasks. |
| 27B | 27 billion | Excellent. Handles nuanced, multi-step reasoning. |
| 70B | 70 billion | Outstanding. Requires significant hardware. |

---

## Step 5 — Install Ollama

Go to **[ollama.com](https://ollama.com)** and click the **Download** button. The website automatically detects your operating system.

### Windows
1. Click **Download for Windows**
2. Run the downloaded `OllamaSetup.exe`
3. Click through the installer — it works like any normal Windows program
4. Ollama runs quietly in the background. Look for a small llama icon in your system tray (bottom-right corner)

### Mac
1. Click **Download for macOS**
2. Open the downloaded `.zip` — it creates an `Ollama` app
3. Drag `Ollama` into your **Applications** folder
4. Open it from Applications. macOS may ask you to confirm — click **Open**
5. Look for a small llama icon in your menu bar (top-right)

### Linux
Open a terminal and run:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

> **Video help:** Search YouTube for **"How to install Ollama [Windows/Mac/Linux] 2025"** to watch a walkthrough. The official Ollama channel also publishes getting-started videos — search **"Ollama official tutorial"**.

---

## Step 6 — Download a model

Open a terminal (or Command Prompt on Windows) and run:

```bash
ollama pull llama3.2
```

This downloads Meta's Llama 3.2 model (~2 GB). To download a specific size:

```bash
# Small and fast (good for 8 GB RAM or less)
ollama pull llama3.2:1b

# Balanced (good for 16 GB RAM)
ollama pull llama3.2:3b

# High quality (good for GPU with 8+ GB VRAM or 32 GB RAM)
ollama pull llama3.1:8b

# Google's model — strong alternative to Llama
ollama pull gemma2:9b

# Mistral — excellent for document analysis
ollama pull mistral
```

> **How do I open a terminal?**
> - **Windows:** Press `Windows + R`, type `cmd`, press Enter
> - **Mac:** Press `Command + Space`, type "Terminal", press Enter
> - **Linux:** Press `Ctrl + Alt + T`

---

## Step 7 — Test it works

In your terminal, type:

```bash
ollama run llama3.2
```

Type a question at the `>>>` prompt. If you get a response, everything is working.

Press `Ctrl + D` or type `/bye` to exit.

---

## Step 8 — Connect it to PrivateAI

Ollama runs as a background service and PrivateAI detects it automatically.

1. Confirm the llama icon is visible in your system tray or menu bar
2. Open PrivateAI → go to **Settings**
3. Under **Local model**, select your downloaded model
4. Adjust the **Complexity threshold** to control when PrivateAI uses local vs. cloud

Responses using your local model will show a **🟢 LOCAL** badge — confirming no data left your machine.

---

## Troubleshooting

**"Ollama not running" in PrivateAI**
Open Ollama manually from your Start menu (Windows) or Applications folder (Mac), or run `ollama serve` in a terminal (Linux).

**Responses are very slow**
Expected on CPU-only machines with larger models. Switch to a smaller model:
```bash
ollama pull llama3.2:1b
```

**"Error: model not found"**
Pull the model first (Step 6). To see what you have downloaded:
```bash
ollama list
```

**Model runs but quality is poor**
Try a larger model if your hardware supports it. The 1B models are fast but limited — 8B models produce significantly better answers for document analysis.

---

## Explore all available models

Browse every available model at **[ollama.com/library](https://ollama.com/library)**.

Notable models for document Q&A:

| Model | Command | Made by | Best for |
|---|---|---|---|
| Llama 3.2 | `ollama pull llama3.2` | Meta | General use, great default |
| Llama 3.1 8B | `ollama pull llama3.1:8b` | Meta | Complex reasoning, long docs |
| Gemma 2 | `ollama pull gemma2` | Google | Strong reasoning, efficient |
| Mistral | `ollama pull mistral` | Mistral AI | Document analysis, instruction following |
| Phi-3.5 Mini | `ollama pull phi3.5` | Microsoft | Very small, surprisingly capable |
| Qwen 2.5 | `ollama pull qwen2.5` | Alibaba | Strong multilingual support |

---

## Further reading

- **Official Ollama documentation:** [ollama.com](https://ollama.com)
- **All available models:** [ollama.com/library](https://ollama.com/library)
- **YouTube — getting started:** Search `"Ollama getting started 2025"` or `"run AI locally no GPU"`
- **YouTube — GPU setup:** Search `"Ollama GPU acceleration NVIDIA"` or `"Ollama Apple Silicon M2"`
- **Ollama GitHub:** [github.com/ollama/ollama](https://github.com/ollama/ollama)

> All models listed here are open-weight — free to download, free to use, run entirely on your machine after the initial download. No accounts, no subscriptions, no data sent anywhere.
