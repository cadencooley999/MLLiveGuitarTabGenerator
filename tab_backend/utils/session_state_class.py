import numpy as np
import librosa

class SessionState:
    def __init__(self, alpha=0.05, headroom_db=12.0):
        """
        headroom_db: how many dB above the noise floor a frame must be
                     before we consider it active. 12 dB means the frame
                     needs to be ~4x louder in amplitude than the floor.
                     Raise to 15-18 if still hallucinating in noisy rooms.
        """
        self.session_max_mag      = 1e-8
        self.running_energy_floor = None   # now tracked in dB
        self.alpha                = alpha
        self.headroom_db          = headroom_db
 
        # Onset stats — unchanged
        self.flux_count  = 0
        self.flux_sum    = 0.0
        self.flux_sq_sum = 0.0
 
    def update(self, C_mag):
        # 1. Update global max for dB reference
        current_max = np.max(C_mag)
        if current_max > self.session_max_mag:
            self.session_max_mag = current_max
 
        # 2. Track noise floor in dB using the quietest 15th percentile
        #    of the current frame — same percentile as before but now
        #    converted to dB so the headroom threshold is interpretable.
        floor_mag = np.percentile(C_mag, 15)
        floor_db  = float(librosa.amplitude_to_db(
            np.array([floor_mag]), ref=self.session_max_mag
        )[0])
 
        if self.running_energy_floor is None:
            self.running_energy_floor = floor_db
        else:
            # Slow-moving EMA — floor creeps up slowly, never down fast
            # Use a slower alpha for the floor so transient loud notes
            # don't corrupt the floor estimate upward
            self.running_energy_floor = (
                self.alpha * floor_db +
                (1 - self.alpha) * self.running_energy_floor
            )
 
    def update_flux_stats(self, flux_vector):
        for f in flux_vector:
            self.flux_count  += 1
            self.flux_sum    += f
            self.flux_sq_sum += f ** 2
 
    @property
    def flux_mean(self):
        return self.flux_sum / (self.flux_count + 1e-8)
 
    @property
    def flux_std(self):
        variance = (self.flux_sq_sum / (self.flux_count + 1e-8)) - self.flux_mean ** 2
        return np.sqrt(max(variance, 1e-8))