# Running AI Locally with Ollama

This guide walks you through installing **Ollama** — the tool that lets PrivateAI run an AI model entirely on your own computer, with no internet connection required and no data sent anywhere.

**You do not need a technical background to follow this guide.** Every step is explained in plain language.

---

## Before you start — do you need this?

PrivateAI works in two modes:

| Mode | What it uses | Cost | Data leaves your machine? |
|---|---|---|---|
| **Local AI** (this guide) | Ollama on your computer | Free | Never |
| **Cloud AI** (default fallback) | OpenAI GPT-4o | ~$0.01–0.10 per conversation | Yes, to OpenAI |

If maximum privacy is your goal, local AI is the right choice. If you just want to get started quickly, you can skip this guide and use the OpenAI fallback — just add your API key in Settings.

---

## Step 1 — Check if your computer is ready

You do not need a special computer. Most laptops and desktops bought in the last 5–6 years will work.

### Minimum requirements

| What | Minimum | Recommended |
|---|---|---|
| RAM (memory) | 8 GB | 16 GB or more |
| Storage (free space) | 5 GB | 10 GB or more |
| Operating system | Windows 10, macOS 12, or Ubuntu 20.04 | Any current version |
| Internet | Needed once to download the model | Not needed after that |

> **How do I check my RAM?**
> - **Windows:** Press `Windows + R`, type `dxdiag`, press Enter. Look for "Memory."
> - **Mac:** Click the Apple menu → About This Mac → look for "Memory."
> - **Linux:** Open a terminal and type `free -h`.

### What about a graphics card (GPU)?

A GPU is **not required**. Ollama runs on your computer's regular processor (CPU). A GPU makes responses arrive faster, but the answers are the same quality either way.

| Your setup | What to expect |
|---|---|
| Laptop, no GPU, 8 GB RAM | Works. Responses take 10–30 seconds. Good for occasional use. |
| Desktop, no GPU, 16 GB RAM | Works well. Responses take 5–15 seconds. |
| Any computer with an NVIDIA or AMD GPU | Fast. Responses in 1–5 seconds. |
| Apple Silicon Mac (M1/M2/M3/M4) | Excellent. Apple's chip handles AI very efficiently. |

If you want to enable GPU acceleration later, search YouTube for **"Ollama GPU setup [Windows/Mac]"** — but start without it. It is an optional upgrade, not a requirement.

---

## Step 2 — Download Ollama

Go to **[ollama.com](https://ollama.com)** and click the **Download** button.

The website automatically detects your operating system and shows the right version.

### Windows
1. Click **Download for Windows**
2. Run the downloaded file (`OllamaSetup.exe`)
3. Click through the installer — it installs like any normal Windows program
4. Ollama runs quietly in the background. You will see a small llama icon in your system tray (bottom-right corner of the screen)

### Mac
1. Click **Download for macOS**
2. Open the downloaded `.zip` file — it will create an `Ollama` app
3. Drag `Ollama` into your **Applications** folder
4. Open it from Applications — macOS may ask you to confirm opening a downloaded app, click **Open**
5. Ollama runs in the background. You will see a small llama icon in your menu bar (top-right of the screen)

### Linux
Open a terminal and run this single command:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

That's it. Ollama installs and starts automatically.

> **Video help:** If you'd prefer to watch someone do this, search YouTube for **"How to install Ollama [Windows/Mac/Linux] 2025"**. The official Ollama channel also has getting-started videos — search **"Ollama official tutorial"**.

---

## Step 3 — Choose a model

A "model" is the AI brain that runs on your computer. Different models have different sizes and capabilities. Bigger is generally smarter but requires more memory.

**Our recommendation for most users: `llama3.2`**

It is made by Meta (the company behind Facebook), it is free, and it strikes the best balance between quality and speed for typical computers.

### Which size should I pick?

| Your RAM | Recommended model | Why |
|---|---|---|
| 8 GB | `llama3.2:1b` | Lightweight, fits comfortably, fast responses |
| 8 GB | `phi3.5:mini` | Microsoft's compact model, surprisingly capable |
| 16 GB | `llama3.2:3b` | Better answers, still fast |
| 16 GB | `mistral` | Excellent for document analysis, strong reasoning |
| 32 GB or more | `llama3.1:8b` | High quality, close to GPT-3.5 level |
| Apple M1/M2/M3/M4 (any RAM) | `llama3.2:3b` or `mistral` | Apple Silicon handles these very efficiently |

> **Not sure?** Start with `llama3.2` (no size tag). Ollama will pick a sensible default for your machine.

### What do 1b, 3b, 7b, 8b mean?

These are "billion parameters" — a rough measure of model size and capability. Think of it like engine size in a car: bigger engines are more powerful but use more fuel. Larger models give better answers but need more memory and are slower.

---

## Step 4 — Download the model

Once Ollama is installed, open a **terminal** (or **Command Prompt** on Windows) and type:

```bash
ollama pull llama3.2
```

Press Enter. You will see a progress bar as the model downloads. A typical model is **2–5 GB**, so this may take a few minutes depending on your internet speed.

> **How do I open a terminal?**
> - **Windows:** Press `Windows + R`, type `cmd`, press Enter. Or search for "Command Prompt" in the Start menu.
> - **Mac:** Press `Command + Space`, type "Terminal", press Enter.
> - **Linux:** Press `Ctrl + Alt + T`.

To download a specific size (for example, the smaller 1b version):

```bash
ollama pull llama3.2:1b
```

To download Mistral:

```bash
ollama pull mistral
```

---

## Step 5 — Test that it works

In your terminal, type:

```bash
ollama run llama3.2
```

You will see a prompt like `>>>`. Type a question and press Enter:

```
>>> What is the capital of France?
Paris is the capital of France.
```

If you get a response, Ollama is working correctly. Press `Ctrl + D` or type `/bye` to exit.

---

## Step 6 — Connect it to PrivateAI

Ollama runs as a background service. PrivateAI automatically detects it — you do not need to do anything extra.

1. Make sure Ollama is running (check for the llama icon in your system tray or menu bar)
2. Open PrivateAI and go to **Settings**
3. Under **Local model**, you should see your downloaded model listed
4. Set your **Complexity threshold** — this controls how often PrivateAI uses Ollama vs. OpenAI

That is it. The next time you ask a question in PrivateAI, it will route simple queries to your local Ollama model and show a **🟢 LOCAL** badge on the response.

---

## Troubleshooting

### "Ollama not running" message in PrivateAI

Ollama may not have started automatically. Open it manually:
- **Windows:** Search for "Ollama" in the Start menu and open it
- **Mac:** Open the Ollama app from your Applications folder
- **Linux:** Run `ollama serve` in a terminal

### The model is very slow

This is normal on computers without a GPU, especially for larger models. Try a smaller model:

```bash
ollama pull llama3.2:1b
```

Then set it as your local model in PrivateAI Settings.

### "Error: model not found"

Make sure you pulled the model first (Step 4). You can see all downloaded models by running:

```bash
ollama list
```

### I want to try a different model

Browse all available models at **[ollama.com/library](https://ollama.com/library)**. Pull any of them the same way:

```bash
ollama pull <model-name>
```

Popular choices for document Q&A:
- `mistral` — strong reasoning, good with long documents
- `phi3.5` — Microsoft model, very efficient
- `gemma2` — Google's open model, good general purpose
- `qwen2.5` — Alibaba's model, good multilingual support

---

## Keeping Ollama up to date

Ollama updates itself automatically on Mac and Windows. On Linux, re-run the install command to get the latest version:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

To update a model to its latest version:

```bash
ollama pull llama3.2
```

---

## Further reading and videos

- **Official Ollama documentation:** [ollama.com](https://ollama.com)
- **All available models:** [ollama.com/library](https://ollama.com/library)
- **YouTube — getting started:** Search `"Ollama getting started 2025"` or `"run AI locally no GPU"`
- **YouTube — Mac-specific:** Search `"Ollama Mac M1 M2 setup"` for Apple Silicon guides
- **YouTube — Windows-specific:** Search `"Ollama Windows install tutorial"`
- **Ollama GitHub (technical users):** [github.com/ollama/ollama](https://github.com/ollama/ollama)

> All models available through Ollama are open-weight models, meaning they are free to download and use. They run entirely on your machine — no account, no subscription, no data sent anywhere after the initial download.
