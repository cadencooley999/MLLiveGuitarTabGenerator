import type {Note} from "../types/music"
import { useEffect, useRef, useState } from "react";

function Fretboard({ notes, width }: { notes: Note[], width: number }) {

  const [displayNotes, setDisplayNotes] = useState<Note[]>([]);

  const noteTimesRef = useRef<Map<string, number>>(new Map());

  const HOLD_TIME = 1000;

  useEffect(() => {
    const now = Date.now();

    setDisplayNotes(prev => {
      const updated = [...prev];

      for (const incoming of notes) {
        const key = `${incoming.string}-${incoming.fret}`;

        noteTimesRef.current.set(key, now);

        const existingIdx = updated.findIndex(
          n => n.string === incoming.string
        );

        if (existingIdx !== -1) {
          updated.splice(existingIdx, 1);
        }

        updated.push(incoming);
      }

      return updated.filter(note => {
        const key = `${note.string}-${note.fret}`;
        const t = noteTimesRef.current.get(key);

        return t !== undefined && now - t < HOLD_TIME;
      });
    });
  }, [notes]);

  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now();

      setDisplayNotes(prev =>
        prev.filter(note => {
          const key = `${note.string}-${note.fret}`;
          const t = noteTimesRef.current.get(key);

          return t !== undefined && now - t < HOLD_TIME;
        })
      );
    }, 50);

    return () => clearInterval(interval);
  }, []);

  const strings = 6;
  const frets = 24;

  const safeWidth = Math.max(width, 100);
  const scaleLength = safeWidth - 50;

  // Calculate fret positions based on the 18/17.817 rule for accuracy
  const fretPositions = Array.from({ length: frets + 1 }).map(
    (_, i) => scaleLength - (scaleLength / Math.pow(2, i / 12))
  );

  const fretWidths = fretPositions
    .slice(1)
    .map((pos, i) => pos - fretPositions[i]);

  return (
    <div className="flex items-center justify-center mt-6">
      {/* HEADSTOCK */}
      <div className="w-10 h-50 bg-[#3a2a1f] rounded-l-xl flex flex-col justify-around items-center mr-1">
        {/* {Array.from({ length: strings }).map((_, i) => (
          <div key={i} className="w-2 h-2 bg-[#cbb89d] rounded-full" />
        ))} */}
        {Array.from({ length: strings }).map((_, stringIndex) => {
          const isOpen = displayNotes.some(n => n.string === (5-stringIndex) && n.fret === 0);
          return (
            <div key={stringIndex} className="h-8 flex items-center justify-center">
              {isOpen ? <div className="w-3 h-3 bg-yellow-400 rounded-full shadow-[0_0_8px_2px_rgba(250,204,21,0.8)]" /> : <div key={stringIndex} className="w-2 h-2 bg-[#cbb89d] rounded-full" />}
            </div>
          );
        })}
      </div>

      {/* FRETBOARD CONTAINER */}
      <div className="bg-[#2b211a] p-3 shadow-md flex" style={{ clipPath: "polygon(0% 6%, 100% 0%, 100% 100%, 0% 94%)" }}>
        
        {/* NUT (For Open Strings)
        <div className="w-8 border-r-4 border-[#5a4636] flex flex-col justify-around">
          {Array.from({ length: strings }).map((_, stringIndex) => {
            const isOpen = notes.some(n => n.string === (6-stringIndex) && n.fret === 0);
            return (
              <div key={stringIndex} className="h-8 flex items-center justify-center">
                {isOpen && (
                  <div className="w-3 h-3 bg-yellow-400 rounded-full shadow-[0_0_8px_2px_rgba(250,204,21,0.8)]" />
                )}
              </div>
            );
          })}
        </div> */}

        {/* FRETS 1-24 */}
        {fretWidths.map((width, fretIndex) => (
          <div key={fretIndex} style={{ width }} className="relative border-r border-[#5a4636]">
            {Array.from({ length: strings }).map((_, stringIndex) => {
              const currentString = (5-stringIndex);
              const isActive = displayNotes.some(n => n.string === currentString && n.fret === (fretIndex+1));

              return (
                <div key={stringIndex} className="relative h-8 flex items-center">
                  <div className={`w-full ${stringIndex > 4 ? "h-[2.5px]" : "h-[1.5px]"} bg-[#cbb89d]`} />
                  
                  {isActive && (
                    <div className="absolute left-1/2 -translate-x-1/2 w-4 h-4 bg-white rounded-full shadow-[0_0_10px_2px_rgba(255,255,255,0.8)]" />
                  )}
                </div>
              );
            })}

            {/* Fret markers */}
            {[2, 4, 6, 8, 11, 14, 16, 18, 20].includes(fretIndex) && (
              <div className="absolute top-1/2 -translate-y-1/2 left-1/2 -translate-x-1/2 w-2 h-2 bg-[#8a7a67] rounded-full" />
            )}
          </div>
        ))}
      </div>

      {/* BODY */}
      <div className="w-16 h-44 bg-[#1a1410] rounded-r-full ml-1" />
    </div>
  );
}

export default Fretboard