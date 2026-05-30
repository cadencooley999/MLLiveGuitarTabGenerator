import { useState, useEffect } from "react"
import useDeviceSize from "../custom_hooks/WindowSize"
import useAudioStream from "../custom_hooks/useAudioStream"
import useMicPermission from "../custom_hooks/useMicPermission"
import Fretboard from "../components/Fretboard"
import ErrorBoundary from "../components/ErrorBoundary"
import type {Note} from "../types/music"
import { BarChart2, ChevronLeft } from 'lucide-react'; // Standard icon library
import StringPredictionsView from '../components/stringPredsView'
import DecibelMeterView from '../components/decibelMeterView'
import PianoRollView from '../components/PianoRoll'

function App() {
  const [isMirroring, setIsMirroring] = useState(false)
  const [notes, setNotes] = useState<Note[]>([])
  const [stringPreds, setStringPreds] = useState([])
  const [notePreds, setNotePreds] = useState([])
  const {width} = useDeviceSize()
  const [socket, setSocket] = useState<WebSocket | null>(null)
  const [permission, setPermission] = useState<"unknown" | "granted" | "denied" | "prompt">("unknown")
  const [showAnalytics, setShowAnalytics] = useState(false)
  const [error, setError] = useState(false)
  const [inputDB, setInputDB] = useState(-100)
  const [audioUrl, setAudioUrl] = useState<string | null>(null);

  const micPermission = useMicPermission()

  function clearUIStates() {
    setAudioUrl(null)
    setNotes([])
    setNotePreds([])
    setStringPreds([])
    setInputDB(-100)
  }

  useEffect(() => {
    setPermission(micPermission)
  }, [micPermission])

  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/ws")
    ws.onopen = () => {
      console.log("socket connected")
      setSocket(ws)
    }

    ws.onmessage = (event) => {
      try {
          // 1. Try to parse the raw string
          const data = JSON.parse(event.data);
          console.log("DATA: ", data)

          // 2. Use "Optional Chaining" (?.) to access properties safely
          // This won't crash if 'data' or 'data.notes' is undefined
          const incomingNotes = data?.notes.notes ?? [];
          const incomingStringPreds = data?.string_preds ?? [];
          const incomingNotePreds = data?.note_preds ?? [];
          const status = data?.status ?? "unknown";

          if (status === "success" && Array.isArray(incomingNotes)) {
            setNotes(incomingNotes);
            setStringPreds(incomingStringPreds)
            setNotePreds(incomingNotePreds)
            setError(false);
          }
          else if (status === "success") {
            setStringPreds(incomingStringPreds)
            setNotePreds(incomingNotePreds)
          } 
          else if (status === "stream_end") {
            console.log("stream_end, clearing")
            clearUIStates()
          } else {
            console.log("not success")
            setError(true);
          }
        } catch (err) {
          // This catches JSON.parse errors or logic errors above
          console.error("Frontend Parse Error:", err);
          setError(true);
        }
    }

    ws.onclose = () => {
      console.log("socket closed")
    }

    return () => {
      if (ws.readyState === WebSocket.OPEN) { ws.close() }
    }
  }, [])

  useAudioStream(socket, isMirroring, setPermission, (currentDb) => {
    setInputDB(currentDb)
  })

  const handleFileUpload = async (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0]
    if (!file || !socket) return

    try {
      const url = URL.createObjectURL(file)
      const arrayBuffer = await file.arrayBuffer()
      const audioCtx = new AudioContext()

      const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer)
      const samples = audioBuffer.getChannelData(0)

      console.log("Decoded WAV")
      console.log("Samples:", samples.length)
      console.log("Sample Rate:", audioBuffer.sampleRate)

      // Send config
      socket.send(JSON.stringify({
        type: "config",
        sample_rate: audioBuffer.sampleRate,
        buffer_size: 4096
      }))

      const CHUNK_SIZE = 4096
      const sampleRate = audioBuffer.sampleRate

      // REAL-TIME CLOCK
      const startTime = performance.now()
      setAudioUrl(url)

      let i = 0

      const streamNext = async () => {
        if (i >= samples.length) {
          console.log("Finished streaming wav")
          socket.send(JSON.stringify({
            type: "end_stream"
          }))
          return
        }

        const chunk = new Float32Array(
          samples.slice(i, i + CHUNK_SIZE)
        )

        socket.send(chunk.buffer)

        // expected playback time of this chunk
        const expectedTime =
          (i / sampleRate) * 1000

        const now = performance.now()
        const drift = expectedTime - (now - startTime)

        i += CHUNK_SIZE

        // schedule next chunk with drift correction
        setTimeout(() => {
          streamNext()
        }, Math.max(0, drift))
      }

      streamNext()

    } catch (err) {
      console.error("Upload error:", err)
    }
  }

  return (
    <main className="min-h-screen bg-[#1a1410] text-white flex overflow-hidden">

      <aside 
        className={`bg-[#201a15] border-r border-[#d9a066]/20 transition-all duration-300 ease-in-out z-20 shrink-0 
          ${showAnalytics ? "w-72" : "w-0"} 
          /* Enable vertical scrolling and always show scrollbar area */
          h-screen sticky top-0 overflow-y-auto overflow-x-hidden
          /* Custom Scrollbar Styling */
          scrollbar-thin scrollbar-thumb-[#d9a066]/30 scrollbar-track-[#1a1410]`}
      >
        <div className={`p-6 w-72 min-h-full transition-opacity duration-300 ${showAnalytics ? "opacity-100" : "opacity-0"}`}>
          <div className="flex items-center gap-2 mb-10">
            <BarChart2 className="w-5 h-5 text-[#d9a066]" /> 
            <h2 className="text-xl font-bold text-[#d9a066] tracking-tight">Analytics</h2>
          </div>
          
          <div className="flex flex-col gap-4">
              <DecibelMeterView inputDB={inputDB} isMirroring={isMirroring}/>
              <StringPredictionsView logits={stringPreds}/>
              <PianoRollView logits={notePreds}/>
          </div>
        </div>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col items-center justify-start px-20 py-10 relative overflow-y-auto overflow-x-hidden z-50">

        <button 
          onClick={() => {
            console.log("PRESSED")
            console.log(showAnalytics)
            setShowAnalytics(!showAnalytics)
          }
          }
          className="absolute top-10 left-6 p-2 rounded-lg bg-[#2a221b] border border-[#d9a066]/20 text-[#d9a066] hover:bg-[#3d3128] transition-colors"
        >
          {showAnalytics ? <ChevronLeft size={20} /> : <BarChart2 size={20} />}
        </button>
                
        {/* Title */}
        <h1 className="text-4xl font-bold mb-8 tracking-wide">
          ML Guitar Mirror
        </h1>

        {/* Fretboard Placeholder */}
        <div className="py-10">
          <ErrorBoundary>
            <Fretboard notes={notes} width={!showAnalytics ? width : width-35}/>
          </ErrorBoundary>
        </div>

        {/* Permission Error Message */}
        {permission === "denied" && (
          <div className="mb-8 flex flex-col items-center animate-in fade-in slide-in-from-top-4 duration-500">
            <div className="flex items-center gap-3 px-6 py-4 rounded-2xl bg-[#2a221b] border border-[#d9a066]/30">
              {/* Subtle Warning Icon */}
              <div className="w-2 h-2 rounded-full bg-[#f4a261] animate-pulse" />
              
              <div className="flex flex-col">
                <p className="text-[#f4d35e] font-medium tracking-tight">
                  Microphone Access Required
                </p>
                <p className="text-xs text-[#a08d7a]">
                  Please enable your microphone in browser settings and refresh to start mirroring.
                </p>
              </div>
            </div>
          </div>
        )}

              {/* Server Error Message */}
        {error && (
          <div className="mb-8 flex flex-col items-center animate-in fade-in slide-in-from-top-4 duration-500">
            <div className="flex items-center gap-3 px-6 py-4 rounded-2xl bg-[#2a221b] border border-[#d9a066]/30">
              {/* Subtle Warning Icon */}
              <div className="w-2 h-2 rounded-full bg-[#f34949] animate-pulse" />
              
              <div className="flex flex-col">
                <p className="text-[#fbfbfb] font-medium tracking-tight">
                  Unexpected Server Error
                </p>
                <p className="text-xs text-[#a08d7a]">
                  Please try again or refresh browser.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Button */}
        <button
          onClick={() => {
            if (!socket) {return}
            if (!isMirroring) {
              console.log("startig mirror")
              setIsMirroring(true)
            } else {
              console.log("stopping mirror")
              setIsMirroring(false)
              clearUIStates()
            }
          }}
          className={`px-8 py-3 mb-6 rounded-xl font-semibold text-lg transition-all duration-200
            ${
              isMirroring
                ? "bg-[#5a4636] hover:bg-[#6b5442]"
                : "bg-[#8b5e3c] hover:bg-[#a06b45]"
            }`}
        >
          {isMirroring && socket && permission == "granted" ? "Stop Mirroring" : "Begin Mirroring"}
        </button>

        <h1>Or</h1>

        <div className="mt-6 flex justify-center">
          <label
            className="
              cursor-pointer
              px-5 py-3
              rounded-xl
              bg-[#2a221b]
              border border-[#5a4636]
              hover:border-[#8b5e3c]
              hover:bg-[#33291f]
              transition-all duration-200
              text-sm text-[#a06b45]
              font-medium
              shadow-md
            "
          >
            <span>Select WAV File</span>

            <input
              type="file"
              accept=".wav,audio/wav"
              onChange={handleFileUpload}
              className="hidden"
            />
          </label>
        </div>

        {audioUrl && (
          <audio
            controls
            autoPlay
            src={audioUrl}
            className="mt-4"
          />
        )}

        {/* Optional subtle footer vibe */}
        <p className="mt-10 text-sm text-[#8a7a67]">
          Real-time guitar tab prediction powered by machine learning
        </p>
      </div>
    </main>
  )
}

export default App
