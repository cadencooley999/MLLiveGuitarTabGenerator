import React, { useRef, useState, useEffect } from 'react';

interface StringPredictionsProps {
  logits: number[]; 
}

const STRING_LABELS = ['E', 'A', 'D', 'G', 'B', 'e'];

const StringPredictionsView: React.FC<StringPredictionsProps> = ({ logits }) => {
  const memoryRef = useRef<number[]>(new Array(6).fill(0));
  const [displayProbs, setDisplayProbs] = useState<number[]>(new Array(6).fill(0))

    const ALPHA = 0.25;
    const THRESHOLD = 0.4;
    const GAIN = 5.0;

    // 3. Process the data inside useEffect (The "Safe" Zone)
    useEffect(() => {
        const rawData = Array.isArray(logits) ? logits.flat() : [];
        if (rawData.length === 0) {
            memoryRef.current = new Array(6).fill(0);
            // eslint-disable-next-line
            setDisplayProbs(new Array(6).fill(0));
            return;
        }

        const nextProbs = rawData.map((val, i) => {
            if (i >= 6) return 0;
            
            // Update memory
            const prev = memoryRef.current[i];
            const smoothed = (val * ALPHA) + (prev * (1 - ALPHA));
            memoryRef.current[i] = smoothed;

            // Calculate prob
            const shifted = (smoothed - THRESHOLD) * GAIN;
            return 1 / (1 + Math.exp(-shifted));
        });

        setDisplayProbs(nextProbs);
    }, [logits]); 

  return (
    <div className="mt-0 px-2 w-full">
      <h3 className="text-[10px] uppercase font-bold text-[#8a7a67] tracking-widest mb-4">
        String Predictions
      </h3>

      {/* Container for all 6 strings */}
      <div className="flex flex-row justify-between w-full h-48 relative">
        
        {/* Ticks positioned relative to the BAR height area */}
        <div className="absolute top-0 w-full h-32 pointer-events-none">
          {/* 60% line */}
          <div className="absolute w-full flex items-center gap-2 opacity-20" style={{ bottom: '60%' }}>
            <div className="flex-1 border-t border-[#d9a066] border-dashed" />
            <span className="text-[8px] font-mono text-[#d9a066]">60%</span>
          </div>
          {/* 20% line */}
          <div className="absolute w-full flex items-center gap-2 opacity-20" style={{ bottom: '20%' }}>
            <div className="flex-1 border-t border-[#d9a066] border-dashed" />
            <span className="text-[8px] font-mono text-[#d9a066]">20%</span>
          </div>
        </div>

        {/* The 6 Strings */}
        {displayProbs.map((prob, i) => (
          <div key={`string-${i}`} className="flex flex-col items-center justify-end h-full flex-1">
            
            {/* 1. The Bar (Set to h-32 to match the tick area) */}
            <div className="w-1.5 h-32 bg-[#1a1410] rounded-full relative overflow-hidden border border-[#5a4636]/30">
              <div 
                className="absolute bottom-0 w-full bg-linear-to-t from-[#8b5e3c] to-[#d9a066] transition-all duration-300 ease-out shadow-[0_0_8px_rgba(217,160,102,0.4)]"
                style={{ height: `${prob * 100}%` }}
              />
            </div>
            
            {/* 2. String Nut */}
            <div className="w-8 h-1.5 bg-[#f5f5f0] rounded-sm my-3" />

            {/* 3. Labels */}
            <div className="flex flex-col items-center">
              <span className="text-sm font-black text-[#d9a066] leading-none mb-1">
                {STRING_LABELS[i]}
              </span>
              <span className="text-[10px] font-mono text-[#8a7a67]">
                {(prob * 100).toFixed(0)}%
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default StringPredictionsView;