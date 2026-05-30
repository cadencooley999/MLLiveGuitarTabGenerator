
interface decibelMeterProps {
    inputDB: number;
    isMirroring: boolean;
}

const DecibelMeterView: React.FC<decibelMeterProps> = ({inputDB, isMirroring}) => {
    return (
        <div className="flex flex-col gap-1 px-2">
            {/* 1. Label */}
            <label className="text-[10px] uppercase font-bold text-[#8a7a67] tracking-widest">
                Input Level
            </label>

            {/* 2. Number Value */}
            <span className="text-2xl font-mono font-bold text-[#d9a066] mb-2">
                {inputDB > -100 ? inputDB.toFixed(0) : "-"} <span className="text-sm font-normal text-[#5a4636]">dB</span>
            </span>

            {/* 3. The Meter Bar */}
            <div className="h-4 bg-[#1a1410] rounded-sm overflow-hidden border border-[#5a4636] relative">
                
                {/* The "Track" Gradient - This stays still */}
                <div 
                className="absolute inset-0 opacity-0 bg-linear-to-r from-[#8b5e3c] via-[#d9a066] to-[#f34949]"
                style={{ width: '100%' }}
                />

                {/* The Active Bar - This grows and reveals the bright colors */}
                <div 
                className="h-full relative transition-all duration-75 ease-out" 
                style={{ 
                    width: isMirroring ? `${Math.min(Math.max(((inputDB + 80) / 90) * 100, 0), 100)}%` : '0%',
                    // This is the magic: the background is fixed to the PARENT'S width
                    background: 'linear-gradient(to right, #8b5e3c, #d9a066 40%, #f34949 100%)',
                    backgroundSize: `${100 / (Math.min(Math.max(((inputDB + 80) / 90) * 100, 0.1)) / 100)}% 100%`,
                }} 
                />
            </div>

            {/* 4. Ticks and Labels Underneath */}
            <div className="relative h-8 mt-1">
                {[
                { val: -80, label: '-80', pos: '2%', color: 'text-[#5a4636]' },
                { val: -60, label: '-60', pos: '22%', color: 'text-[#5a4636]' },
                { val: -20, label: '-20', pos: '66%', color: 'text-[#5a4636]' },
                { val: 0,   label: '0',   pos: '88%', color: 'text-[#d9a066]' },
                { val: 10,  label: '+10', pos: '98%',  color: 'text-[#f34949]' }
                ].map((mark) => (
                <div 
                    key={mark.label} 
                    className="absolute flex flex-col items-center -translate-x-1/2" 
                    style={{ left: mark.pos }}
                >
                    {/* The Tick Mark */}
                    <div className={`w-px h-1.5 bg-current ${mark.color} opacity-50 mb-0`} />
                    
                    {/* The Label */}
                    <span className={`text-[9px] font-mono ${mark.color}`}>
                    {mark.label}
                    </span>
                </div>
                ))}
            </div>
        </div>
    )
}

export default DecibelMeterView;