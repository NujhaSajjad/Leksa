

import { useState, useEffect, useRef } from "react";

// ── Backend URL — .env mein set karo ─────────────
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
const WS_URL = BACKEND_URL.replace(/^http/, "ws");

const injectFonts = () => {
  if (document.getElementById("leksa-fonts")) return;
  const link = document.createElement("link");
  link.id = "leksa-fonts";
  link.rel = "stylesheet";
  link.href =
    "https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=DM+Sans:wght@300;400;500&family=DM+Mono:wght@400;500&display=swap";
  document.head.appendChild(link);
};

const C = {
  ivory: "#F3F1EC",
  garden: "#E0DFD2",
  moss: "#B6B8AB",
  smoke: "#9FA3AD",
  midnight: "#3C3E4A",
};

const GlobalStyles = () => (
  <style>{`
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html, body, #root { height: 100%; width: 100%; overflow: hidden; }
    body { font-family: 'DM Sans', sans-serif; background: ${C.ivory}; color: ${C.midnight}; }
    button { font-family: 'DM Sans', sans-serif; cursor: pointer; }

    @keyframes pulse-dot  { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.4;transform:scale(.7)} }
    @keyframes bar-bounce { 0%,100%{transform:scaleY(.3)} 50%{transform:scaleY(1)} }
    @keyframes fade-in    { from{opacity:0;transform:translateY(5px)} to{opacity:1;transform:translateY(0)} }
    @keyframes slide-r    { from{opacity:0;transform:translateX(14px)} to{opacity:1;transform:translateX(0)} }
    @keyframes spin       { to{transform:rotate(360deg)} }

    .hov-card:hover  { transform:translateY(-2px)!important; box-shadow:0 6px 20px rgba(60,62,74,.09)!important; }
    .begin-btn:hover { background:#848891!important; }
    .back-btn:hover  { background:${C.garden}!important; }
    ::-webkit-scrollbar{ width:3px } ::-webkit-scrollbar-track{background:transparent}
    ::-webkit-scrollbar-thumb{background:${C.moss}44;border-radius:10px}
  `}</style>
);

/* ─── Waveform ─────────────────────────────────── */
function Waveform({ playing }) {
  const ref = useRef(null);
  const raf = useRef(null);
  const t = useRef(0);
  const playRef = useRef(playing);

  useEffect(() => {
    playRef.current = playing;
  }, [playing]);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    function draw() {
      const ctx = canvas.getContext("2d");
      const W = canvas.offsetWidth,
        H = canvas.offsetHeight;
      canvas.width = W * devicePixelRatio;
      canvas.height = H * devicePixelRatio;
      ctx.scale(devicePixelRatio, devicePixelRatio);
      ctx.clearRect(0, 0, W, H);
      const isPlaying = playRef.current;
      const pts = Array.from({ length: 301 }, (_, i) => {
        const p = i / 300;
        const env = Math.sin(p * Math.PI) ** 1.1;
        const amp = isPlaying
          ? env *
          H *
          0.3 *
          (0.55 + 0.45 * Math.sin(p * Math.PI * 3 + t.current * 0.9))
          : H * 0.018;
        return [
          p * W,
          H / 2 + amp * Math.sin(p * 9 * Math.PI + t.current * 1.5),
        ];
      });
      ctx.beginPath();
      pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      [...pts]
        .reverse()
        .forEach(([x, y]) =>
          ctx.lineTo(x, H - (y - H / 2) * 0.4 - H / 2 + H / 2),
        );
      ctx.closePath();
      ctx.fillStyle = `${C.smoke}1E`;
      ctx.fill();
      ctx.beginPath();
      pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.strokeStyle = C.smoke;
      ctx.lineWidth = 1.6;
      ctx.stroke();
      t.current += isPlaying ? 0.038 : 0.004;
      raf.current = requestAnimationFrame(draw);
    }
    raf.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf.current);
  }, []);

  return (
    <canvas
      ref={ref}
      style={{ width: "100%", height: "100%", display: "block" }}
    />
  );
}

/* ─── Mic bars ─────────────────────────────────── */
function MicBars({ active, count = 10 }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 3, height: 14 }}>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          style={{
            width: 3,
            height: active ? `${28 + (i % 4) * 17}%` : "16%",
            background: C.smoke,
            borderRadius: 10,
            transformOrigin: "center",
            animation: active
              ? `bar-bounce ${0.4 + (i % 3) * 0.13}s ease-in-out infinite`
              : "none",
            animationDelay: `${i * 0.05}s`,
            transition: "height .12s ease",
          }}
        />
      ))}
    </div>
  );
}

/* ─── SESSION SCREEN ───────────────────────────── */
function SessionScreen({ onBack, sessionId, uploadedFiles = [] }) {
  const [playing, setPlaying] = useState(false);
  const [intrupt, setIntrupt] = useState(false);
  const [tab, setTab] = useState("Subtitles");
  const [slides, setSlides] = useState(false);
  const [secs, setSecs] = useState(0);
  const [status, setStatus] = useState("connecting");
  const [transcript, setTranscript] = useState("");
  const [segInfo, setSegInfo] = useState(null);
  const [error, setError] = useState(null);
  const [userSpeaking, setUserSpeaking] = useState(false); // VAD: user ki real voice detect hui?
  const [vadReady, setVadReady] = useState(false); // VAD load hua ya nahi?

  const wsRef = useRef(null);
  const audioCtxRef = useRef(null);
  const micStreamRef = useRef(null);
  const workletNodeRef = useRef(null); // AudioWorklet node
  const audioQueueRef = useRef([]);
  const isPlayingARef = useRef(false);
  const vadRef = useRef(null); // VAD instance
  const geminiGainRef = useRef(null); // GainNode for local muting on barge-in

  const fmt = (s) =>
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  // ── Timer ─────────────────────────────────────
  useEffect(() => {
    const t = setInterval(() => setSecs((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);

  // ── WebSocket + Audio setup ───────────────────
  useEffect(() => {
    if (!sessionId) return;

    const ws = new WebSocket(`${WS_URL}/ws/live/${sessionId}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("speaking");
      startMic(ws);
    };

    ws.onmessage = async (event) => {
      const msg = JSON.parse(event.data);

      if (msg.type === "audio") {
        const raw = atob(msg.data);
        const bytes = new Uint8Array(raw.length);
        for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
        audioQueueRef.current.push(bytes.buffer);
        drainAudioQueue();
        setPlaying(true);
      }
      if (msg.type === "transcript") setTranscript(msg.text);
      if (msg.type === "segment")
        setSegInfo({
          index: msg.index,
          title: msg.title,
          key_points: msg.key_points || [],
        });
      if (msg.type === "status") {
        setStatus(msg.status);
        if (msg.status === "listening") setPlaying(false);
        if (msg.status === "speaking") setPlaying(true);
      }
      if (msg.type === "done") {
        setStatus("idle");
        setPlaying(false);
        setTranscript("🎓 Lecture complete! Well done.");
      }
      if (msg.type === "error") {
        setError(msg.message);
        setStatus("idle");
      }
    };

    ws.onerror = () => setError("Connection error. is backend  on?");
    ws.onclose = () => {
      setStatus("idle");
      setPlaying(false);
    };

    return () => {
      try {
        ws.send(JSON.stringify({ type: "end" }));
      } catch { }
      ws.close();
      stopMic();
    };
  }, [sessionId]);

  // ── Audio playback (PCM 24kHz mono) ──────────
  // ── Scheduled gapless playback ─────────────────
  const nextStartTimeRef = useRef(0);

  const getAudioCtx = () => {
    if (!audioCtxRef.current) {
      audioCtxRef.current = new (window.AudioContext || window.AudioContext)(
        { sampleRate: 24000 }
      );
      const gain = audioCtxRef.current.createGain();
      gain.gain.value = 1.0;
      gain.connect(audioCtxRef.current.destination);
      geminiGainRef.current = gain;
      nextStartTimeRef.current = 0; // reset
    }
    return audioCtxRef.current;
  };

  const drainAudioQueue = () => {
    // Sab queued chunks ek hi loop mein scheduled kar do — no await, no gaps
    const ctx = getAudioCtx();
    while (audioQueueRef.current.length > 0) {
      const buf = audioQueueRef.current.shift();
      const int16 = new Int16Array(buf);
      const f32 = new Float32Array(int16.length);
      for (let i = 0; i < int16.length; i++) f32[i] = int16[i] / 32768;

      const ab = ctx.createBuffer(1, f32.length, 24000);
      ab.copyToChannel(f32, 0);

      const src = ctx.createBufferSource();
      src.buffer = ab;
      src.connect(geminiGainRef.current || ctx.destination);

      // Schedule immediately after previous chunk — zero gap
      const startAt = Math.max(ctx.currentTime, nextStartTimeRef.current);
      src.start(startAt);
      nextStartTimeRef.current = startAt + ab.duration;
    }
  };
  // ── Float32 → PCM16 → base64 helper ──────────
  const toPCM16b64 = (float32) => {
    const i16 = new Int16Array(float32.length);
    for (let i = 0; i < float32.length; i++)
      i16[i] = Math.max(-32768, Math.min(32767, float32[i] * 32768));
    // btoa large buffers ke liye safe method
    const bytes = new Uint8Array(i16.buffer);
    let binary = "";
    for (let i = 0; i < bytes.byteLength; i++)
      binary += String.fromCharCode(bytes[i]);
    return btoa(binary);
  };

  // ── Mic → WebSocket  (VAD-gated) ─────────────
  // Primary: @ricky0123/vad-web — sirf tab audio bhejta hai jab user bol raha ho
  // Fallback: AudioWorklet (off-main-thread) — ScriptProcessorNode deprecated hai
  const startMic = async (ws) => {
    try {
      const { MicVAD } = await import("@ricky0123/vad-web");

      const vad = await MicVAD.new({
        // ── Thresholds ────────────────────────────────────────────────────
        positiveSpeechThreshold: 0.85, // is se upar = voice confirmed
        negativeSpeechThreshold: 0.35, // is se neeche = silence confirmed
        minSpeechFrames: 3,            // itne frames ke baad hi "speech start" maano
        preSpeechPadFrames: 5,         // speech se pehle ke frames bhi bhejo (word cut-off rokta hai)
        redemptionFrames: 8,           // short pause ke baad bhi thoda wait karo

        onSpeechStart: () => {
          setUserSpeaking(true);

          // Gemini ko interrupt signal bhejo
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "interrupt" }));
          }

          // Local audio mute
          if (geminiGainRef.current) {
            geminiGainRef.current.gain.setTargetAtTime(
              0, audioCtxRef.current.currentTime, 0.015
            );
          }
          audioQueueRef.current = [];
          nextStartTimeRef.current = 0;
        },

        // har frame real-time mein check hota hai
        onFrameProcessed: (probabilities, frame) => {
          if (
            probabilities.isSpeech > 0.5 &&
            ws.readyState === WebSocket.OPEN
          ) {
            ws.send(JSON.stringify({ type: "audio", data: toPCM16b64(frame) }));
          }
        },

        onSpeechEnd: () => {
          setUserSpeaking(false);
          if (geminiGainRef.current) {
            geminiGainRef.current.gain.setTargetAtTime(
              1.0, audioCtxRef.current.currentTime, 0.05
            );
          }
        },
        onVADMisfire: () => {
          // bahut choti noise thi — restore gain and ignore
          setUserSpeaking(false);
          if (geminiGainRef.current) {
            geminiGainRef.current.gain.setTargetAtTime(
              1.0, audioCtxRef.current.currentTime, 0.05
            );
          }
        },
      });

      vadRef.current = vad;
      vad.start();
      setVadReady(true);
    } catch (err) {
      // VAD package not available — use AudioWorklet fallback (off-main-thread)
      // AudioWorklet prevents UI jank from causing audio cuts (unlike ScriptProcessorNode)
      console.warn("VAD unavailable, falling back to AudioWorklet:", err.message);
      setVadReady(false);
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        micStreamRef.current = stream;
        const ctx = getAudioCtx();

        // Load the worklet module from /public (served as static asset by Vite)
        await ctx.audioWorklet.addModule("/audio-processor.js");
        const workletNode = new AudioWorkletNode(ctx, "leksa-audio-processor");
        workletNodeRef.current = workletNode;

        // Receive downsampled PCM16 chunks from worklet thread
        workletNode.port.onmessage = (e) => {
          if (ws.readyState !== WebSocket.OPEN) return;
          const pcm16 = new Int16Array(e.data.pcm16);
          // Convert Int16Array → base64 for WebSocket transport
          const bytes = new Uint8Array(pcm16.buffer);
          let binary = "";
          for (let i = 0; i < bytes.byteLength; i++)
            binary += String.fromCharCode(bytes[i]);
          ws.send(JSON.stringify({ type: "audio", data: btoa(binary) }));
        };

        const source = ctx.createMediaStreamSource(stream);
        source.connect(workletNode);
        // Do NOT connect workletNode to destination — we only want to capture, not play back mic
      } catch (workletErr) {
        console.error("AudioWorklet also failed:", workletErr);
        setError("Mic access nahi mili. Browser se mic allow karo.");
      }
    }
  };

  const stopMic = () => {
    if (vadRef.current) {
      try {
        vadRef.current.pause();
        vadRef.current.destroy?.();
      } catch { }
      vadRef.current = null;
    }
    // Disconnect AudioWorklet node (fallback path)
    workletNodeRef.current?.disconnect();
    workletNodeRef.current?.port.close?.();
    workletNodeRef.current = null;
    micStreamRef.current?.getTracks().forEach((t) => t.stop());
  };

  const doIntrupt = () => {
    if (intrupt) return;
    setIntrupt(true);
    setTimeout(() => setIntrupt(false), 3500);
  };

  const togglePlay = () => {
    if (!wsRef.current) return;
    if (playing) {
      wsRef.current.send(JSON.stringify({ type: "pause" }));
      setPlaying(false);
    } else {
      wsRef.current.send(JSON.stringify({ type: "resume" }));
      setPlaying(true);
    }
  };

  const docs = uploadedFiles.map((f) => f.name);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        overflow: "hidden",
        background: C.ivory,
      }}
    >
      {/* NAV */}
      <nav
        style={{
          height: 54,
          flexShrink: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 28px",
          background: C.ivory,
          borderBottom: `1px solid ${C.moss}44`,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button
            className="back-btn"
            onClick={onBack}
            style={{
              width: 30,
              height: 30,
              borderRadius: "50%",
              border: `1px solid ${C.moss}55`,
              background: "none",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: C.moss,
              fontSize: ".85rem",
              transition: "background .2s",
            }}
          >
            ←
          </button>
          <span
            style={{
              fontFamily: "'Instrument Serif',serif",
              fontSize: "1.1rem",
              color: C.midnight,
            }}
          >
            Leksa
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              background: C.garden,
              border: `1px solid ${C.moss}44`,
              borderRadius: 100,
              padding: "4px 12px",
              fontSize: ".7rem",
              color: C.smoke,
              fontFamily: "'DM Mono',monospace",
            }}
          >
            <div
              style={{
                width: 5,
                height: 5,
                borderRadius: "50%",
                background:
                  status === "speaking"
                    ? "#6bbd6e"
                    : status === "listening"
                      ? "#e0a34a"
                      : C.smoke,
                animation:
                  status !== "idle"
                    ? "pulse-dot 1.5s ease-in-out infinite"
                    : "none",
              }}
            />
            {status === "connecting"
              ? "Connecting…"
              : status === "speaking"
                ? "Speaking"
                : status === "listening"
                  ? "Listening"
                  : "Idle"}
          </div>
          <span
            style={{
              fontFamily: "'DM Mono',monospace",
              fontSize: ".75rem",
              color: C.smoke,
            }}
          >
            {fmt(secs)}
          </span>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: "50%",
              background: C.midnight,
              color: C.ivory,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: ".63rem",
              fontWeight: 500,
            }}
          >
            BD
          </div>
        </div>
      </nav>

      {/* DOCS BAR */}
      <div
        style={{
          height: 40,
          flexShrink: 0,
          display: "flex",
          alignItems: "center",
          gap: 7,
          padding: "0 28px",
          background: C.ivory,
          borderBottom: `1px solid ${C.moss}33`,
          overflowX: "auto",
        }}
      >
        {docs.map((d) => (
          <div
            key={d}
            style={{
              background: C.smoke,
              border: `1px solid ${C.smoke}`,
              borderRadius: 100,
              padding: "3px 13px",
              fontSize: ".68rem",
              color: C.midnight,
              fontFamily: "'DM Mono',monospace",
              fontWeight: 500,
              whiteSpace: "nowrap",
            }}
          >
            {d}
          </div>
        ))}
        {segInfo && (
          <div
            style={{
              marginLeft: "auto",
              fontSize: ".68rem",
              color: C.moss,
              fontFamily: "'DM Mono',monospace",
              whiteSpace: "nowrap",
            }}
          >
            Seg {segInfo.index + 1} — {segInfo.title}
          </div>
        )}
      </div>

      {/* ERROR BANNER */}
      {error && (
        <div
          style={{
            background: "#fde8e8",
            borderBottom: "1px solid #f5c0c0",
            padding: "8px 28px",
            fontSize: ".78rem",
            color: "#c0392b",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          ⚠️ {error}
          <button
            onClick={() => setError(null)}
            style={{
              background: "none",
              border: "none",
              color: "#c0392b",
              cursor: "pointer",
            }}
          >
            ×
          </button>
        </div>
      )}

      {/* BODY */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "space-evenly",
          padding: "8px 24px",
          overflow: "hidden",
          minHeight: 0,
        }}
      >
        {/* Waveform */}
        <div
          style={{
            width: "100%",
            maxWidth: 600,
            height: 0,
            flexGrow: 2,
            minHeight: 60,
            maxHeight: 130,
            borderRadius: 14,
            overflow: "hidden",
            background: `${C.smoke}0A`,
          }}
        >
          <Waveform playing={playing && !intrupt} />
        </div>

        {/* Subtitle */}
        {tab !== "Slides" && (
          <div
            style={{
              width: "100%",
              maxWidth: 600,
              flexShrink: 0,
              background: C.garden,
              border: `1px solid ${C.moss}44`,
              borderRadius: 12,
              padding: "9px 16px",
              fontSize: ".78rem",
              lineHeight: 1.6,
              color: C.midnight,
              height: 62,
              overflow: "hidden",
              animation: "fade-in .25s ease",
            }}
          >
            {tab === "Subtitles" ? (
              transcript ? (
                <span>{transcript}</span>
              ) : (
                <span style={{ color: C.moss, fontStyle: "italic" }}>
                  {status === "connecting"
                    ? "Backend se connect ho raha hai…"
                    : "AI teacher bolne wala hai…"}
                </span>
              )
            ) : (
              <>
                <p
                  style={{
                    color: C.moss,
                    fontSize: ".6rem",
                    marginBottom: 4,
                    fontFamily: "'DM Mono',monospace",
                    letterSpacing: ".08em",
                  }}
                >
                  TRANSCRIPT
                </p>
                <span style={{ color: C.moss, fontStyle: "italic" }}>
                  {transcript || "Transcript yahan aayega…"}
                </span>
              </>
            )}
          </div>
        )}

        {/* Mic button + VAD status */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 6,
            flexShrink: 0,
          }}
        >
          <button
            onClick={doIntrupt}
            style={{
              width: 56,
              height: 56,
              borderRadius: "50%",
              // VAD detect kare to alag color dikhao
              background: userSpeaking
                ? "#6bbd6e"
                : intrupt
                  ? C.smoke
                  : C.midnight,
              border: "none",
              color: C.ivory,
              fontSize: "1.05rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all .25s ease",
              boxShadow: userSpeaking
                ? `0 0 0 7px ${"#6bbd6e"}33`
                : intrupt
                  ? `0 0 0 7px ${C.smoke}2A`
                  : "none",
            }}
          >
            🎙
          </button>

          {/* MicBars: VAD se real signal milta hai */}
          <MicBars active={intrupt || userSpeaking} count={11} />

          {/* VAD status indicator — chota hint neeche */}
          <span
            style={{
              fontSize: ".58rem",
              fontFamily: "'DM Mono',monospace",
              letterSpacing: ".06em",
              color: userSpeaking ? "#6bbd6e" : C.moss,
              transition: "color .2s",
            }}
          >
            {!vadReady
              ? "mic active"
              : userSpeaking
                ? "● speaking"
                : "○ listening for voice"}
          </span>
        </div>

        {/* Interrupt */}
        <button
          onClick={doIntrupt}
          style={{
            background: intrupt ? C.smoke : C.garden,
            border: `1.5px solid ${intrupt ? C.smoke : C.moss}`,
            borderRadius: 100,
            padding: "7px 20px",
            fontSize: ".76rem",
            color: intrupt ? C.midnight : C.moss,
            fontWeight: intrupt ? 500 : 400,
            display: "flex",
            alignItems: "center",
            gap: 8,
            transition: "all .25s ease",
            flexShrink: 0,
          }}
        >
          {intrupt && <MicBars active count={5} />}
          {intrupt ? "Listening… speak now" : "Interrupt & Ask"}
        </button>

        {/* Controls */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 14,
            flexShrink: 0,
          }}
        >
          <button
            onClick={togglePlay}
            style={{
              width: 42,
              height: 42,
              borderRadius: "50%",
              background: C.midnight,
              border: "none",
              color: C.ivory,
              fontSize: ".88rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "transform .2s",
            }}
          >
            {playing ? "⏸" : "▶"}
          </button>
          <button
            onClick={() =>
              wsRef.current?.send(JSON.stringify({ type: "next" }))
            }
            style={{
              background: "none",
              border: "none",
              color: C.moss,
              fontSize: ".76rem",
              transition: "color .2s",
            }}
            onMouseEnter={(e) => (e.target.style.color = C.midnight)}
            onMouseLeave={(e) => (e.target.style.color = C.moss)}
          >
            Next Segment →
          </button>
        </div>

        {/* Tabs */}
        <div style={{ display: "flex", gap: 5, flexShrink: 0 }}>
          {["Subtitles", "Transcript", "Slides"].map((tb) => {
            const on = tab === tb;
            return (
              <button
                key={tb}
                onClick={() => {
                  setTab(tb);
                  if (tb === "Slides") setSlides((v) => !v);
                }}
                style={{
                  background: on ? C.smoke : C.garden,
                  border: `1px solid ${on ? C.smoke : C.moss + "44"}`,
                  borderRadius: 100,
                  padding: "5px 15px",
                  fontSize: ".71rem",
                  color: on ? C.midnight : C.moss,
                  fontWeight: on ? 500 : 400,
                  transition: "all .2s",
                }}
              >
                {tb}
                {tb === "Slides" ? (slides ? " ‹" : " ›") : ""}
              </button>
            );
          })}
        </div>
      </div>

      {/* SLIDES PANEL */}
      {slides && (
        <div
          style={{
            position: "fixed",
            right: 0,
            top: 0,
            bottom: 0,
            width: 310,
            flexShrink: 0,
            background: C.garden,
            borderLeft: `1px solid ${C.moss}44`,
            display: "flex",
            flexDirection: "column",
            padding: "20px 18px",
            overflowY: "auto",
            animation: "slide-r .25s ease",
            zIndex: 50,
          }}
        >
          <p
            style={{
              fontFamily: "'Instrument Serif',serif",
              fontSize: ".95rem",
              color: C.midnight,
              marginBottom: 14,
            }}
          >
            {segInfo?.title || "Current Slide"}
          </p>
          {segInfo?.key_points?.length > 0 ? (
            <ul
              style={{
                listStyle: "none",
                display: "flex",
                flexDirection: "column",
                gap: 12,
              }}
            >
              {segInfo.key_points.map((kp, i) => (
                <li
                  key={i}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 8,
                    fontSize: ".75rem",
                    lineHeight: 1.55,
                    color: C.midnight,
                  }}
                >
                  <span
                    style={{
                      width: 5,
                      height: 5,
                      borderRadius: "50%",
                      flexShrink: 0,
                      background: C.midnight,
                      marginTop: 5,
                    }}
                  />
                  {kp}
                </li>
              ))}
            </ul>
          ) : (
            <p
              style={{
                fontSize: ".75rem",
                color: C.moss,
                fontStyle: "italic",
                lineHeight: 1.6,
              }}
            >
              Key points yahan aayenge jab lecture shuru ho…
            </p>
          )}
        </div>
      )}

      {/* Tip */}
      <div
        style={{
          position: "fixed",
          bottom: 18,
          right: 18,
          background: C.ivory,
          border: `1px solid ${C.moss}55`,
          borderRadius: 12,
          padding: "9px 13px",
          fontSize: ".7rem",
          color: C.midnight,
          maxWidth: 195,
          lineHeight: 1.55,
          boxShadow: `0 2px 8px ${C.midnight}0B`,
          animation: "fade-in 1s ease 2s both",
          zIndex: 100,
        }}
      >
        🔥 <strong>Tip:</strong> Interrupt anytime and ask a question.
      </div>
    </div>
  );
}

/* ─── UPLOAD MODAL ─────────────────────────────── */
function UploadModal({ onClose, onStart }) {
  const [files, setFiles] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadErr, setUploadErr] = useState(null);
  const inputRef = useRef(null);

  const addFiles = (incoming) => {
    const arr = Array.from(incoming).filter((f) =>
      f.name.match(/\.(pdf|ppt|pptx|doc|docx|txt)$/i),
    );
    setFiles((prev) => [...prev, ...arr]);
  };

  const iconFor = (name) => {
    if (name.match(/\.pdf$/i)) return "📄";
    if (name.match(/\.pptx?$/i)) return "📊";
    if (name.match(/\.docx?$/i)) return "📝";
    return "📃";
  };

  const fmt = (b) =>
    b < 1024 * 1024
      ? `${(b / 1024).toFixed(0)} KB`
      : `${(b / (1024 * 1024)).toFixed(1)} MB`;

  const handleStart = async () => {
    if (files.length === 0) return;
    setUploading(true);
    setUploadErr(null);
    try {
      const fd = new FormData();
      fd.append("file", files[0]);
      const res = await fetch(`${BACKEND_URL}/api/upload`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) {
        const e = await res.json();
        throw new Error(e.detail || "Upload failed");
      }
      const data = await res.json();
      onStart(files, data.session_id);
    } catch (err) {
      setUploadErr(err.message || "Upload fail hua. Backend chal raha hai?");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 200,
        background: "rgba(60,62,74,.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        animation: "fade-in .2s ease",
        padding: "20px",
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        style={{
          background: C.ivory,
          borderRadius: 20,
          width: "min(520px,92vw)",
          padding: "28px 28px 22px",
          boxShadow: `0 16px 48px ${C.midnight}22`,
          animation: "fade-in .25s ease",
          maxHeight: "90vh",
          overflowY: "auto",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 20,
          }}
        >
          <span
            style={{
              fontFamily: "'Instrument Serif',serif",
              fontSize: "1.1rem",
              color: C.midnight,
            }}
          >
            New Session
          </span>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: C.moss,
              fontSize: "1.1rem",
              cursor: "pointer",
            }}
          >
            ×
          </button>
        </div>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            addFiles(e.dataTransfer.files);
          }}
          onClick={() => inputRef.current.click()}
          style={{
            border: `1.5px dashed ${dragging ? C.smoke : C.moss + "88"}`,
            borderRadius: 14,
            padding: "28px 20px",
            textAlign: "center",
            cursor: "pointer",
            background: dragging ? `${C.smoke}0C` : C.garden,
            transition: "all .2s ease",
            marginBottom: 16,
          }}
        >
          <div style={{ fontSize: "1.6rem", marginBottom: 8 }}>📂</div>
          <p style={{ fontSize: ".82rem", color: C.midnight, marginBottom: 4 }}>
            Drag & drop your documents here
          </p>
          <p style={{ fontSize: ".72rem", color: C.moss }}>
            PDF · PPT · DOCX · TXT
          </p>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".pdf,.ppt,.pptx,.doc,.docx,.txt"
            style={{ display: "none" }}
            onChange={(e) => addFiles(e.target.files)}
          />
        </div>

        {files.length > 0 && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 7,
              maxHeight: 160,
              overflowY: "auto",
              marginBottom: 16,
            }}
          >
            {files.map((f, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  background: C.garden,
                  borderRadius: 10,
                  padding: "8px 12px",
                }}
              >
                <span style={{ fontSize: "1rem" }}>{iconFor(f.name)}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: ".76rem",
                      color: C.midnight,
                      fontWeight: 500,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {f.name}
                  </div>
                  <div
                    style={{
                      fontSize: ".65rem",
                      color: C.moss,
                      fontFamily: "'DM Mono',monospace",
                    }}
                  >
                    {fmt(f.size)}
                  </div>
                </div>
                <button
                  onClick={() =>
                    setFiles((prev) => prev.filter((_, j) => j !== i))
                  }
                  style={{
                    background: "none",
                    border: "none",
                    color: C.moss,
                    fontSize: ".85rem",
                    cursor: "pointer",
                  }}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}

        {uploadErr && (
          <div
            style={{
              background: "#fde8e8",
              border: "1px solid #f5c0c0",
              borderRadius: 8,
              padding: "8px 12px",
              fontSize: ".75rem",
              color: "#c0392b",
              marginBottom: 12,
            }}
          >
            ⚠️ {uploadErr}
          </div>
        )}

        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            gap: 10,
          }}
        >
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: C.moss,
              fontSize: ".8rem",
              cursor: "pointer",
              padding: "8px 4px",
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleStart}
            disabled={files.length === 0 || uploading}
            style={{
              background:
                files.length > 0 && !uploading ? C.midnight : `${C.midnight}55`,
              color: C.ivory,
              border: "none",
              borderRadius: 100,
              padding: "9px 22px",
              fontSize: ".8rem",
              fontWeight: 500,
              cursor:
                files.length > 0 && !uploading ? "pointer" : "not-allowed",
              transition: "background .2s",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            {uploading && (
              <div
                style={{
                  width: 12,
                  height: 12,
                  borderRadius: "50%",
                  border: `2px solid ${C.ivory}44`,
                  borderTopColor: C.ivory,
                  animation: "spin .7s linear infinite",
                }}
              />
            )}
            {uploading ? "Processing…" : "Start Lecture →"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─── HOME SCREEN ──────────────────────────────── */
function HomeScreen({ onStart }) {
  const [showModal, setShowModal] = useState(false);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        overflow: "hidden",
        background: C.ivory,
      }}
    >
      {showModal && (
        <UploadModal
          onClose={() => setShowModal(false)}
          onStart={(files, sid) => {
            setShowModal(false);
            onStart(files, sid);
          }}
        />
      )}

      <nav
        style={{
          height: 60,
          flexShrink: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 40px",
          background: C.ivory,
          borderBottom: `1px solid ${C.moss}44`,
        }}
      >
        <span
          style={{
            fontFamily: "'Instrument Serif',serif",
            fontSize: "1.2rem",
            color: C.midnight,
          }}
        >
          Leksa
        </span>
        <div
          style={{
            width: 34,
            height: 34,
            borderRadius: "50%",
            background: C.midnight,
            color: C.ivory,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: ".65rem",
            fontWeight: 500,
          }}
        >
          BD
        </div>
      </nav>

      <div style={{ flex: 1, overflowY: "auto", padding: "38px 40px 28px" }}>
        <div style={{ maxWidth: 840, margin: "0 auto" }}>
          <h1
            style={{
              fontFamily: "'Instrument Serif',serif",
              fontSize: "2.3rem",
              fontWeight: 400,
              color: C.midnight,
              marginBottom: 5,
              letterSpacing: "-.02em",
              animation: "fade-in .4s ease",
            }}
          >
            Good morning, Buddy
          </h1>
          <p
            style={{
              fontSize: ".85rem",
              color: C.moss,
              marginBottom: 30,
              fontWeight: 300,
            }}
          >
            Ready to continue learning?
          </p>

          <div
            className="hov-card"
            onClick={() => setShowModal(true)}
            style={{
              background: C.midnight,
              borderRadius: 18,
              padding: "22px 26px",
              marginBottom: 32,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              cursor: "pointer",
              transition: "transform .2s ease,box-shadow .2s ease",
              animation: "fade-in .4s ease .08s both",
            }}
          >
            <div>
              <div
                style={{
                  fontFamily: "'Instrument Serif',serif",
                  fontSize: "1.15rem",
                  color: C.ivory,
                  marginBottom: 3,
                }}
              >
                Start New Session
              </div>
              <div
                style={{
                  fontSize: ".76rem",
                  color: `${C.ivory}66`,
                  fontWeight: 300,
                }}
              >
                Upload your documents and begin an AI-guided lecture
              </div>
            </div>
            <button
              className="begin-btn"
              style={{
                background: C.smoke,
                color: C.ivory,
                border: "none",
                borderRadius: 100,
                padding: "8px 18px",
                fontSize: ".78rem",
                fontWeight: 500,
                transition: "background .2s",
                whiteSpace: "nowrap",
              }}
            >
              Begin →
            </button>
          </div>

          <p
            style={{
              fontFamily: "'Instrument Serif',serif",
              fontSize: ".98rem",
              color: C.midnight,
              marginBottom: 14,
              animation: "fade-in .4s ease .16s both",
            }}
          >
            Recent Sessions
          </p>

          <div
            style={{
              background: C.garden,
              border: `1px solid ${C.moss}33`,
              borderRadius: 16,
              padding: "32px 28px",
              display: "flex",
              alignItems: "center",
              gap: 24,
              animation: "fade-in .4s ease .22s both",
            }}
          >
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: "50%",
                flexShrink: 0,
                background: `${C.moss}22`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "1.3rem",
              }}
            >
              📖
            </div>
            <div style={{ flex: 1 }}>
              <p
                style={{
                  fontSize: ".88rem",
                  color: C.midnight,
                  fontWeight: 500,
                  marginBottom: 4,
                }}
              >
                No sessions yet
              </p>
              <p style={{ fontSize: ".78rem", color: C.moss, lineHeight: 1.6 }}>
                Upload a document above to start your first AI-guided lecture.
              </p>
            </div>
            <button
              onClick={() => setShowModal(true)}
              style={{
                background: C.midnight,
                color: C.ivory,
                border: "none",
                borderRadius: 100,
                padding: "9px 20px",
                fontSize: ".76rem",
                fontWeight: 500,
                cursor: "pointer",
                whiteSpace: "nowrap",
                flexShrink: 0,
                transition: "opacity .2s",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.opacity = ".8")}
              onMouseLeave={(e) => (e.currentTarget.style.opacity = "1")}
            >
              + New Session
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── ROOT ─────────────────────────────────────── */
export default function App() {
  useEffect(() => {
    injectFonts();
  }, []);
  const [screen, setScreen] = useState("home");
  const [files, setFiles] = useState([]);
  const [sessionId, setSessionId] = useState(null);

  const handleStart = (uploadedFiles, sid) => {
    setFiles(uploadedFiles);
    setSessionId(sid);
    setScreen("session");
  };

  return (
    <>
      <GlobalStyles />
      {screen === "home" ? (
        <HomeScreen onStart={handleStart} />
      ) : (
        <SessionScreen
          onBack={() => {
            setScreen("home");
            setSessionId(null);
          }}
          sessionId={sessionId}
          uploadedFiles={files}
        />
      )}
    </>
  );
}
