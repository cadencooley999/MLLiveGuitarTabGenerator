import { useEffect, useRef } from "react"

export default function useAudioStream(
  socket: WebSocket | null,
  isActive: boolean,
  setPermission: React.Dispatch<React.SetStateAction<"granted" | "denied" | "prompt" | "unknown">>,
  onDbChange: (db: number) => void
) {
  const audioContextRef = useRef<AudioContext | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)

  const onDbChangeRef = useRef(onDbChange);
  const setPermissionRef = useRef(setPermission)

  useEffect(() => {
    onDbChangeRef.current = onDbChange;
  }, [onDbChange]);

  useEffect(() => {
    if (!isActive || !socket) return;

    let stream: MediaStream;

    let rawRecorder: MediaRecorder | null = null;
    let processedRecorder: MediaRecorder | null = null;

    const start = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: false,
            noiseSuppression: false,
            autoGainControl: false,
            channelCount: 1
          }
        });

        setPermissionRef.current("granted");

        const ctx = new AudioContext();
        audioContextRef.current = ctx;

        const source = ctx.createMediaStreamSource(stream);

        const processor = ctx.createScriptProcessor(
          4096,
          1,
          1
        );

        processorRef.current = processor;

        // RAW RECORDING
        const rawDest =
          ctx.createMediaStreamDestination();

        source.connect(rawDest);

        rawRecorder = new MediaRecorder(
          rawDest.stream
        );

        const rawChunks: Blob[] = [];

        rawRecorder.ondataavailable = e => {
          rawChunks.push(e.data);
        };

        rawRecorder.onstop = () => {
          const blob = new Blob(rawChunks, {
            type: "audio/webm"
          });

          const url = URL.createObjectURL(blob);

          console.log("RAW AUDIO:", url);

          const a = document.createElement("a");
          a.href = url;
          a.download = "raw_audio.webm";
          a.click();
        };

        // FILTERS
        const highpass = ctx.createBiquadFilter();
        highpass.type = "highpass";
        highpass.frequency.value = 70;

        const presence = ctx.createBiquadFilter();
        presence.type = "peaking";
        presence.frequency.value = 2500;
        presence.Q.value = 1.0;
        presence.gain.value = 5;

        const whitening = ctx.createBiquadFilter();
        whitening.type = "highshelf";
        whitening.frequency.value = 1200;
        whitening.gain.value = 4;

        const compressor =
          ctx.createDynamicsCompressor();

        compressor.threshold.value = -28;
        compressor.knee.value = 20;
        compressor.ratio.value = 4.0;
        compressor.attack.value = 0.003;
        compressor.release.value = 0.1;

        // AUDIO GRAPH
        source.connect(highpass);
        highpass.connect(presence);
        presence.connect(whitening);
        whitening.connect(compressor);
        compressor.connect(processor);

        // PROCESSED RECORDING
        const processedDest =
          ctx.createMediaStreamDestination();

        compressor.connect(processedDest);

        processedRecorder = new MediaRecorder(
          processedDest.stream
        );

        const processedChunks: Blob[] = [];

        processedRecorder.ondataavailable = e => {
          processedChunks.push(e.data);
        };

        processedRecorder.onstop = () => {
          const blob = new Blob(processedChunks, {
            type: "audio/webm"
          });

          const url = URL.createObjectURL(blob);

          console.log("PROCESSED AUDIO:", url);

          setTimeout(() => {
            const a = document.createElement("a");
            a.href = url;
            a.download = "processed_audio.webm";
            a.click();
          }, 500);
        };

        // KEEP GRAPH ALIVE
        const gain = ctx.createGain();
        gain.gain.value = 0;

        processor.connect(gain);
        gain.connect(ctx.destination);

        // SEND CONFIG
        if (socket.readyState === WebSocket.OPEN) {
          socket.send(
            JSON.stringify({
              type: "config",
              sample_rate: ctx.sampleRate,
              buffer_size: 4096
            })
          );
        }

        // // START RECORDING
        // rawRecorder.start();
        // processedRecorder.start();

        // AUDIO PROCESSING
        processor.onaudioprocess = e => {
          const data =
            e.inputBuffer.getChannelData(0);

          let sum = 0;

          for (let i = 0; i < data.length; i++) {
            sum += data[i] * data[i];
          }

          const rms = Math.sqrt(
            sum / data.length
          );

          const db =
            rms > 0
              ? 20 * Math.log10(rms)
              : -100;

          onDbChangeRef.current(db);

          // NOISE GATE
          if (db < -70) return;

          if (
            !socket ||
            socket.readyState !== WebSocket.OPEN
          ) {
            return;
          }

          socket.send(data.buffer);
        };

      } catch {
        setPermissionRef.current("denied");
      }
    };

    start();

    return () => {
      rawRecorder?.stop();
      processedRecorder?.stop();

      processorRef.current?.disconnect();

      audioContextRef.current?.close();

      stream?.getTracks().forEach(track =>
        track.stop()
      );
    };

  }, [isActive, socket]);
}