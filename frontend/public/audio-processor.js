/**
 * Leksa AudioWorkletProcessor
 * Runs on a dedicated audio-rendering thread (off main thread).
 *
 * Responsibilities:
 *   1. Receive raw Float32 microphone frames from the browser (44.1 or 48 kHz).
 *   2. Downsample to exactly 24,000 Hz mono. (Gemini Live native input rate)
 *   3. Convert Float32 → PCM16 (Int16).
 *   4. Accumulate into ~4096-sample chunks (~85 ms at 48 kHz → ~51 ms at 24 kHz).
 *   5. Post the Int16Array buffer to the main thread via MessagePort.
 *
 * Why AudioWorklet instead of ScriptProcessorNode?
 *   - Runs on a separate audio worklet thread → no main-thread JS lag.
 *   - Eliminates audio "cuts" caused by React re-renders or heavy UI work.
 *   - Required by modern Chrome (ScriptProcessorNode is deprecated).
 */
class LeksaAudioProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    // Target sample rate for Gemini Live PCM input
    this._targetRate = 24000;
    // Input rate will be the AudioContext sampleRate (44100 or 48000)
    this._inputRate = sampleRate; // global 'sampleRate' inside AudioWorklet scope
    // Downsample ratio (e.g. 48000/24000 = 2)
    this._ratio = this._inputRate / this._targetRate;

    // Accumulation buffer (after downsampling) before we post a chunk
    this._chunkSize = 4096;
    this._buffer = new Float32Array(this._chunkSize);
    this._bufferFill = 0;

    // Carry-over fractional index for linear interpolation downsampling
    this._phase = 0;
  }

  /**
   * Called by the audio engine for every 128-sample render quantum.
   * @param {Float32Array[][]} inputs - [[channel0Data, channel1Data, ...]]
   */
  process(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;

    // Use first channel only (mono)
    const channelData = input[0];
    if (!channelData || channelData.length === 0) return true;

    // --- Downsample via linear interpolation ---
    let inputIdx = this._phase;
    while (inputIdx < channelData.length) {
      const lo = Math.floor(inputIdx);
      const hi = Math.min(lo + 1, channelData.length - 1);
      const frac = inputIdx - lo;
      const sample = channelData[lo] * (1 - frac) + channelData[hi] * frac;

      this._buffer[this._bufferFill++] = sample;

      // When chunk is full, convert to PCM16 and post
      if (this._bufferFill >= this._chunkSize) {
        this._flush();
      }

      inputIdx += this._ratio;
    }

    // Store carry-over phase for next quantum (preserve continuity)
    this._phase = inputIdx - channelData.length;
    if (this._phase < 0) this._phase = 0;

    // Return true to keep processor alive
    return true;
  }

  _flush() {
    // Convert Float32 → Int16 (PCM 16-bit)
    const pcm16 = new Int16Array(this._bufferFill);
    for (let i = 0; i < this._bufferFill; i++) {
      const s = Math.max(-1, Math.min(1, this._buffer[i]));
      pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }

    // Post transferable buffer to main thread (zero-copy)
    this.port.postMessage({ pcm16: pcm16.buffer }, [pcm16.buffer]);

    this._bufferFill = 0;
  }
}

registerProcessor("leksa-audio-processor", LeksaAudioProcessor);
