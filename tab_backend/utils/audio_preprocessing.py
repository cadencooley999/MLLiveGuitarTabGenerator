import numpy as np
import librosa
import torch

class AudioBuffer:
    def __init__(self, max_samples):
        self.max_samples = max_samples
        self.buffer = np.zeros(0, dtype=np.float32)

    def update_max_samples(self, max):
        self.max_samples = max

    def add_chunk(self, chunk: np.ndarray):
        # append new audio
        self.buffer = np.concatenate([self.buffer, chunk])

        # keep only last max_samples
        if len(self.buffer) > self.max_samples:
            self.buffer = self.buffer[-self.max_samples:]

    def is_ready(self):
        return len(self.buffer) == self.max_samples

    def get_window(self):
        return self.buffer
    
def preprocess_audio(samples, client_sr, global_mean, global_std, session):
    resampled = librosa.resample(samples, orig_sr=client_sr, target_sr=22050)
    cqts = librosa.cqt(y=resampled, sr=22050, hop_length=1024, n_bins=144, bins_per_octave=24)

    if cqts.shape[1] < 51: return None
    C_mag = np.abs(cqts)

    session.update(C_mag)

    if is_silent_frame(C_mag=C_mag, session=session):
        return None

    C_db = librosa.amplitude_to_db(C_mag, ref=session.session_max_mag)

    silences = detect_silence(C_mag, session)
    
    top_k_pitch_matrix = get_top_k_pitches(C_mag)
    onsets = get_onsets(C_mag, session).astype(np.float32)

    # Channel expansion and slicing
    onsets_ch = np.repeat(np.expand_dims(onsets, axis=0), 144, axis=0)
    silences_ch = np.repeat(np.expand_dims(silences, axis=0), 144, axis=0)
    
    X = np.stack([C_db[:, -51:], top_k_pitch_matrix[:, -51:], 
                  onsets_ch[:, -51:], silences_ch[:, -51:]], axis=0)

    X = np.transpose(X, (0, 2, 1))

    X = (X - global_mean.reshape(4, 1, 1)) / (global_std.reshape(4, 1, 1) + 1e-8)

    return torch.tensor(X, dtype=torch.float32)

def is_silent_frame(C_mag, session):
    """
    Returns True if the frame should be gated (no prediction).
 
    Logic:
        1. Convert the current frame's median energy to dB
           (using the same session_max_mag reference as C_db in preprocessing)
        2. Compute headroom = current_db - noise_floor_db
        3. If headroom < session.headroom_db, it's too close to the noise
           floor to be a real note → gate it
 
    Example with headroom_db=12:
        noise floor = -64 dB  →  anything below -52 dB is gated
        noise floor = -58 dB  →  anything below -46 dB is gated
 
    This directly implements what you described: the session learns the
    actual noise floor and anything not sufficiently above it is suppressed.
    """
    if session.running_energy_floor is None:
        return False  # not enough history yet
 
    current_db = float(librosa.amplitude_to_db(
        np.array([np.median(C_mag)]), ref=session.session_max_mag
    )[0])
 
    headroom = current_db - session.running_energy_floor
    return headroom < session.headroom_db

def get_top_k_pitches(C_mag, k=6, threshold=0.5):
    n_bins, T = C_mag.shape
    final_matrix = np.zeros((n_bins, T), dtype=np.float32)

    for t in range(T):
        frame = C_mag[:, t]

        # normalize
        frame = frame / (np.max(frame) + 1e-8)

        # threshold
        valid_idxs = np.where(frame > threshold)[0]

        # sort by strength
        sorted_idxs = valid_idxs[np.argsort(frame[valid_idxs])[::-1]]

        # remove nearby duplicates
        deduped_idxs = filter_close_bins_vector(sorted_idxs, frame)

        # take top K
        top_k = deduped_idxs[:k]

        # ✅ fill matrix directly
        final_matrix[top_k, t] = frame[top_k]

    return final_matrix

def get_onsets(C_mag, session, threshold=0.3):
    diff = np.diff(C_mag, axis=1)
    diff = np.maximum(diff, 0)
    flux = np.sum(diff, axis=0)
    flux = np.concatenate([[0], flux])
    
    # Update global history with this new flux data
    session.update_flux_stats(flux)
    
    # Normalize using global stats
    # This ensures a "peak" is actually a peak relative to the whole performance
    norm_flux = (flux - session.flux_mean) / (session.flux_std + 1e-8)
    
    onsets = np.zeros_like(norm_flux)
    for i in range(1, len(norm_flux)-1):
        if norm_flux[i] > threshold and norm_flux[i] > norm_flux[i-1] and norm_flux[i] > norm_flux[i+1]:
            onsets[i] = 1
    return onsets

def bin_to_midi(bin_idx, fmin=librosa.note_to_hz('C2')):
    freq = librosa.cqt_frequencies(
        n_bins=144,
        fmin=fmin,
        bins_per_octave=24
    )[bin_idx]

    return librosa.hz_to_midi(freq)

def detect_silence(C_mag, session):
    energy = np.mean(C_mag, axis=0)
    # Use the session's tracked floor instead of a local percentile
    threshold = session.running_energy_floor if session.running_energy_floor else 0
    return (energy < threshold).astype(np.float32)

def filter_close_bins_vector(sorted_idxs, frame, min_distance=2):
    if len(sorted_idxs) == 0:
        return np.array([], dtype=int)

    selected = []
    taken = np.zeros_like(frame, dtype=bool)

    for idx in sorted_idxs:
        if not taken[idx]:
            selected.append(idx)

            # mark neighborhood as taken
            start = max(0, idx - min_distance)
            end = min(len(frame), idx + min_distance + 1)
            taken[start:end] = True

    return np.array(selected)