import { useState, useEffect } from "react";

const useDeviceSize = () => {
  // 1. Initialize with actual values if window exists
  const [size, setSize] = useState({
    width: typeof window !== "undefined" ? window.innerWidth : 0,
    height: typeof window !== "undefined" ? window.innerHeight : 0,
  });

  useEffect(() => {
    // 2. Check for window existence (SSR safety)
    if (typeof window === "undefined") return;

    const handleWindowResize = () => {
      setSize({
        width: window.innerWidth,
        height: window.innerHeight,
      });
    };

    // 3. Set the size immediately on mount in case the initial state was 0
    handleWindowResize();

    window.addEventListener('resize', handleWindowResize);
    return () => window.removeEventListener('resize', handleWindowResize);
  }, []);

  // 4. Returning an object is usually safer for scaling than an array
  return size;
};

export default useDeviceSize;