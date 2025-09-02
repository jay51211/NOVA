document.addEventListener("DOMContentLoaded", () => {
  const intro = document.getElementById("intro"); // 2
  const novaWord = document.getElementById("novaWord"); // 3
  const hiWord = document.getElementById("hiWord"); // 4
  const introAudio = document.getElementById("introAudio"); // 5
  const app = document.getElementById("app"); // 6
  const authBtnWrap = document.getElementById("authBtnWrap"); // 7
  const promptEl = document.getElementById("prompt"); // 8
  const sendBtn = document.getElementById("sendBtn"); // 9
  const messages = document.getElementById("messages"); // 10
  const status = document.getElementById("status"); // 11
  const micBtn = document.getElementById("micBtn"); // 12
  const listening = document.getElementById("listening"); // 13
  const authModal = document.getElementById("authModal"); // 14
  const authOpen = document.getElementById("authOpen"); // 15
  const authSubmit = document.getElementById("authSubmit"); // 16
  const authUser = document.getElementById("authUser"); // 17
  const authPass = document.getElementById("authPass"); // 18
  const authMsg = document.getElementById("authMsg"); // 19
  const closeAuth = document.getElementById("closeAuth"); // 20
  const stopBtn = document.getElementById("stopBtn"); // 21

  let currentAudio = null; // 23

  // Intro animation and audio
  setTimeout(() => { // 26
    introAudio.play().catch(() => {}); // 27
  }, 120); // 28
  setTimeout(() => { // 29
    novaWord.classList.add("hidden"); // 30
    hiWord.classList.remove("hidden"); // 31
  }, 2600); // 32
  setTimeout(() => { // 33
    intro.style.transition = "opacity .6s ease"; // 34
    intro.style.opacity = "0"; // 35
    setTimeout(() => { // 36
      intro.classList.add("hidden"); // 37
      authBtnWrap.classList.remove("hidden"); // 38
      app.classList.remove("hidden"); // 39
    }, 600); // 40
  }, 4000); // 41

  // Add chat message
  function addMsg(role, text) { // 44
    const d = document.createElement("div"); // 45
    d.className = "msg " + role; // 46

    if (role === "nova") { // 48
      d.innerHTML = marked.parse(text); // 49
    } else { // 50
      d.textContent = text; // 51
    } // 52

    messages.appendChild(d); // 54
    messages.scrollTop = messages.scrollHeight; // 55
  } // 56

  // ========================
  // Browser TTS
  async function playVoice(text) { // 60
    try { // 61
      if (currentAudio) { // 62
        currentAudio.pause(); // 63
        currentAudio = null; // 64
      } // 65
      const res = await fetch("http://127.0.0.1:5000/api/say_browser", {
        method: "POST", // 67
        headers: { "Content-Type": "application/json" }, // 68
        body: JSON.stringify({ text }), // 69
      }); // 70
      const blob = await res.blob(); // 71
      const url = URL.createObjectURL(blob); // 72

      currentAudio = new Audio(url); // 74
      currentAudio.play(); // 75

      stopBtn.onclick = () => { // 77
        if (currentAudio) { // 78
          currentAudio.pause(); // 79
          currentAudio = null; // 80
        } // 81
      }; // 82
    } catch (err) { // 83
      console.error("Voice error:", err); // 84
    } // 85
  } // 86

  // Send message to backend
  async function sendPrompt(text) { // 89
    if (!text) return; // 90
    addMsg("user", text); // 91
    promptEl.value = ""; // 92
    status.textContent = "Thinking..."; // 93
    try { // 94
      const res = await fetch("http://127.0.0.1:5000/api/chat", {
        method: "POST", // 96
        headers: { "Content-Type": "application/json" }, // 97
        body: JSON.stringify({ prompt: text }), // 98
      }); // 99
      const j = await res.json(); // 100
      const reply = j.text || j.error || "No response"; // 101
      addMsg("nova", reply); // 102
      playVoice(reply); // 103  <-- NEW: play TTS
    } catch (e) { // 104
      addMsg("nova", "Network error"); // 105
    } finally { // 106
      status.textContent = "Ready"; // 107
    } // 108
  } // 109

  sendBtn.addEventListener("click", () => sendPrompt(promptEl.value.trim())); // 112
  promptEl.addEventListener("keydown", (e) => { // 113
    if (e.key === "Enter") sendPrompt(promptEl.value.trim()); // 114
  }); // 115

  stopBtn.addEventListener("click", () => { // 117
    if (currentAudio) { // 118
      currentAudio.pause(); // 119
      currentAudio = null; // 120
    } // 121
  }); // 122

  // ========================
  // Speech recognition
  function getRecognition() { // 126
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition; // 127
    if (!SR) return null; // 128
    const r = new SR(); // 129
    r.lang = "en-US"; // 130
    r.interimResults = false; // 131
    r.maxAlternatives = 1; // 132
    return r; // 133
  } // 134

  const rec = getRecognition(); // 136
  function startListening() { // 137
    if (!rec) { // 138
      alert("Speech recognition not supported"); // 139
      return; // 140
    } // 141
    micBtn.classList.add("listening"); // 142
    listening.classList.remove("hidden"); // 143
    rec.start(); // 144
  } // 145
  function stopListening() { // 146
    if (!rec) return; // 147
    rec.stop(); // 148
    micBtn.classList.remove("listening"); // 149
    listening.classList.add("hidden"); // 150
  } // 151

  if (rec) { // 153
    rec.onresult = (ev) => { // 154
      const t = ev.results[0][0].transcript; // 155
      sendPrompt(t); // 156
    }; // 157
    rec.onend = stopListening; // 158
    rec.onerror = stopListening; // 159
  } // 160

  micBtn.addEventListener("mousedown", startListening); // 162
  micBtn.addEventListener( // 163
    "touchstart", // 164
    (e) => { // 165
      e.preventDefault(); // 166
      startListening(); // 167
    }, // 168
    { passive: false } // 169
  ); // 170
  ["mouseup", "mouseleave", "touchend", "touchcancel"].forEach((evt) => // 171
    micBtn.addEventListener(evt, stopListening) // 172
  ); // 173

  // ========================
  // Authentication modal
  authOpen?.addEventListener("click", () => { // 176
    authModal.classList.remove("hidden"); // 177
    authMsg.textContent = ""; // 178
  }); // 179
  closeAuth?.addEventListener("click", () => authModal.classList.add("hidden")); // 180

  authSubmit?.addEventListener("click", async () => { // 182
    const u = authUser.value.trim(), // 183
      p = authPass.value.trim(); // 184
    if (!u || !p) { // 185
      authMsg.textContent = "Enter username and password"; // 186
      return; // 187
    } // 188
    try { // 189
      const res = await fetch("http://127.0.0.1:5000/api/signup", {
        method: "POST", // 191
        headers: { "Content-Type": "application/json" }, // 192
        body: JSON.stringify({ username: u, password: p }), // 193
      }); // 194
      const j = await res.json(); // 195
      authMsg.textContent = j.message || j.error || "Done"; // 196
      if (j.ok) { // 197
        setTimeout(() => authModal.classList.add("hidden"), 500); // 198
      } // 199
    } catch (e) { // 200
      authMsg.textContent = "Network error"; // 201
    } // 202
  }); // 203
}); // 204
