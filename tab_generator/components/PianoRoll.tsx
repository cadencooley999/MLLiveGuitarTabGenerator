import React, { useState } from 'react';
import { useRef, useEffect } from 'react';

interface PianoRollProps {
  logits: number[];
}


const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
const DATA_START_MIDI = 28; // E1 (The start of your 64 logits)

const PianoRollView: React.FC<PianoRollProps> = ({ logits }) => {
  const memoryRef = useRef<number[]>(new Array(64).fill(-20));
  const [displayProbs, setDisplayProbs] = useState<number[]>(new Array(64).fill(-20))

    const ALPHA = 0.25;
    const THRESHOLD = -0.5;
    const GAIN = 2.0;

    // 3. Process the data inside useEffect (The "Safe" Zone)
    useEffect(() => {
        const rawData = Array.isArray(logits) ? logits.flat() : [];
        console.log(rawData, "RAW DATA")
        if (rawData.length === 0) {
            memoryRef.current = new Array(64).fill(0);
            // eslint-disable-next-line
            setDisplayProbs(new Array(64).fill(0));
            console.log("RAW IS 0")
            return
        }

        const nextProbs = rawData.map((val, i) => {
            if (i >= 64) return 0;
            
            // Update memory
            const prev = memoryRef.current[i];
            const smoothed = (val * ALPHA) + (prev * (1 - ALPHA));
            memoryRef.current[i] = smoothed;

            // Calculate prob
            const shifted = (smoothed - THRESHOLD) * GAIN;
            return 1 / (1 + Math.exp(-shifted));
        });

        console.log("NEXT PROBS", nextProbs)

        setDisplayProbs(nextProbs);
    }, [logits]); 
  
    // 12 Rows (C through B), 5 Columns (Octaves 1 through 5)
    const pitches = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
    const octaves = [1, 2, 3, 4, 5]; 

  return (
    <div className="w-full py-2 px-1">
      <h3 className="text-[10px] uppercase font-bold text-[#8a7a67] tracking-widest mb-4 px-1">
        Note Heatmap
      </h3>
      
      <div className="grid grid-cols-5 gap-0.5 bg-[#0c0a09] p-0.5 rounded-sm">
        {pitches.map((pitch) => (
          <React.Fragment key={`pitch-${pitch}`}>
            {octaves.map((octave) => {
              const midi = (octave + 1) * 12 + pitch; // Standard MIDI math
              const idx = midi - DATA_START_MIDI; // Offset relative to E1
              const prob = displayProbs[idx]
              // Get logit, apply raw sigmoid (no normalization)
              
              // Filter out noise: only glow if it's a "real" prediction
              const glow = prob > 0.4 ? (prob - 0.4) / 0.6 : 0;

              return (
                <div
                  key={midi}
                  className="aspect-square relative rounded-[1px] transition-all duration-75 border"
                  style={{
                    backgroundColor: `rgba(217, 160, 102, ${glow})`,
                    borderColor: glow > 0.9 ? '#fff' : `rgba(45, 36, 30, 0.4)`,
                    boxShadow: glow > 0.5 
                      ? `0 0 ${glow * 15}px rgba(217, 160, 102, ${glow * 0.5})` 
                      : 'none',
                    zIndex: glow > 0.5 ? 10 : 1,
                    backgroundClip: 'padding-box',
                  }}
                >
                  <div className="absolute inset-0 bg-[#161210] -z-10" />
                  
                  <span className={`absolute top-0.5 right-1 text-[7px] font-bold ${glow < 0.6 ? 'text-black/40' : 'text-[#4a3a2e]'}`}>
                    {octave}
                  </span>
                  
                  <span className={`absolute bottom-0.5 left-1 text-[9px] font-black uppercase ${glow < 0.6 ? 'text-black' : 'text-[#6a5a47]'}`}>
                    {NOTE_NAMES[pitch].replace('#', '♯')}
                  </span>
                </div>
              );
            })}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
};

export default PianoRollView;