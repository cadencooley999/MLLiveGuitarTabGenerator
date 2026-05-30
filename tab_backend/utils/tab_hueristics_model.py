import math
import random
import numpy as np
from collections import deque


# ---------------------------------------------------------------------------
# Fretboard
# ---------------------------------------------------------------------------

STANDARD_FRETBOARD = [
    list(range(40, 65)),   # low E  (E2–E4)
    list(range(45, 70)),   # A      (A2–A4)
    list(range(50, 75)),   # D      (D3–D5)
    list(range(55, 80)),   # G      (G3–G5)
    list(range(59, 84)),   # B      (B3–B5)
    list(range(64, 89)),   # high e (E4–E6)
]

NOTE_NAMES  = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
MIDI_OFFSET = 28   # lowest note index in the 64-dim vector
N_NOTES     = 64

# ---------------------------------------------------------------------------
# Krumhansl-Schmuckler key profiles (Krumhansl 1990)
# These are empirically derived ratings of how well each pitch class fits
# each key — far more musically grounded than binary in/out-of-scale.
# Major profile: tonic(6.35) dom(5.19) mediant(4.60) ... leading(2.70)
# Minor profile: natural minor variant
# ---------------------------------------------------------------------------

KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                     2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                     2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# Normalise so profiles sum to 1 for clean dot-product scoring
KS_MAJOR = KS_MAJOR / KS_MAJOR.sum()
KS_MINOR = KS_MINOR / KS_MINOR.sum()


class MemoryHeuristicDecoder:

    def __init__(
        self,
        history_len:        int   = 12,    # frames kept (~0.56 s at 46 ms/frame)
        smooth_decay:       float = 0.65,  # EWA decay for temporal smoothing
        smooth_strength:    float = 0.4,   # how strongly smoothing biases logits
        key_strength:       float = 0.55,  # max logit boost for in-key notes
        prune_threshold:    float = 0.25,  # min prob gap to suppress cluster neighbour
        prune_radius:       int   = 2,     # semitone radius defining a cluster
    ):
        self.history_len     = history_len
        self.smooth_decay    = smooth_decay
        self.smooth_strength = smooth_strength
        self.key_strength    = key_strength
        self.prune_threshold = prune_threshold
        self.prune_radius    = prune_radius

        # Ring buffer of raw note logit arrays — shape (N_NOTES,) each
        self._logit_history: deque = deque(maxlen=history_len)
        # Ring buffer of previous tab predictions for cost computation
        self._tab_history:   deque = deque(maxlen=history_len)

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    # Absolute gates — must exceed these before gap-finding runs.
    # Prevents hallucination on silence: gap-finder is relative and
    # will always find a gap even in pure noise.
    NOTE_GATE   = 0.40   # max sigmoid(note_logit) must exceed this
    STRING_GATE = 0.30   # max sigmoid(string_logit) must exceed this

    def get_most_likely_tab(
        self,
        note_logits,
        string_logits,
        max_cost: float = 25.0,
    ) -> list:
        """
        Main entry point. Accepts logits as torch tensors or numpy arrays.
        Returns [(string_idx, fret), ...] or [].
        """
        note_logits, string_logits = self._to_numpy(note_logits, string_logits)

        # Absolute gate: if nothing clears the floor, bail immediately.
        # The gap-finder is relative and will fire on any noise floor —
        # this is the hard check that prevents silence hallucination.
        note_probs_raw   = self._sigmoid(note_logits)
        string_probs_raw = self._sigmoid(string_logits)
        if (note_probs_raw.max() < self.NOTE_GATE or
                string_probs_raw.max() < self.STRING_GATE):
            self._logit_history.append(note_logits.copy())  # still update history
            return []

        # --- Pre-processing pipeline (runs before thresholding) ---
        note_logits = self._temporal_smooth(note_logits)
        note_logits = self._key_bias(note_logits)
        note_logits = self._harmonic_prune(note_logits)

        # Store cleaned logits in history
        self._logit_history.append(note_logits.copy())

        prev_tab = self._tab_history[-1] if self._tab_history else []

        combos = self._get_possible_combos(note_logits, string_logits, prev_tab)

        if not combos:
            return []

        best, cost = self._choose_best_combo(combos, prev_tab)

        if cost <= max_cost:
            self._tab_history.append(best)

        return best if cost <= max_cost else []

    def reset(self):
        """Call between songs / recordings."""
        self._logit_history.clear()
        self._tab_history.clear()

    # -----------------------------------------------------------------------
    # Pre-processing step 1: Temporal smoothing
    # -----------------------------------------------------------------------

    def _temporal_smooth(self, note_logits: np.ndarray) -> np.ndarray:
        """
        Compute an exponentially weighted average (EWA) of the logit history
        and add it as a bias to the current frame.

        Weight for frame at lag k: decay^k  (most recent = decay^0 = 1.0)

        This means a note that has been consistently active for several frames
        gets a positive carry-forward bias, making it more stable. A note that
        suddenly appears with no history gets no boost. This directly suppresses
        single-frame flicker.

        We operate in logit space (before sigmoid) so the effect is additive
        and well-scaled relative to the model's own confidence.
        """
        if not self._logit_history:
            return note_logits

        # Build EWA over history (most recent last in deque)
        ewa    = np.zeros(N_NOTES)
        weight = 1.0
        total  = 0.0

        for past_logits in reversed(self._logit_history):
            ewa    += weight * past_logits
            total  += weight
            weight *= self.smooth_decay

        ewa /= total   # normalise so scale doesn't grow with history length

        # Apply as a bias scaled by smooth_strength
        # We scale the bias relative to the current frame's std so it's
        # proportionate to the signal magnitude rather than absolute
        scale = np.std(note_logits) + 1e-6
        bias  = self.smooth_strength * (ewa / (np.std(ewa) + 1e-6)) * scale

        return note_logits + bias

    # -----------------------------------------------------------------------
    # Pre-processing step 2: Key estimation and biasing
    # -----------------------------------------------------------------------

    def _key_bias(self, note_logits: np.ndarray) -> np.ndarray:
        """
        1. Build a pitch-class histogram from logit history (sigmoid-weighted
           so only confident notes contribute).
        2. Score all 24 keys using Krumhansl-Schmuckler profiles via dot product.
        3. Apply a graded bias: in-key notes boosted proportionally to their
           KS profile weight, out-of-key notes mildly suppressed.

        Using KS profiles instead of binary in/out-of-scale means the tonic,
        dominant and mediant get stronger boosts than passing tones — this
        reflects how guitar music actually works harmonically.
        """
        if len(self._logit_history) < 2:
            return note_logits

        # Build pitch-class histogram weighted by note probability
        pc_hist = np.zeros(12)
        decay   = 1.0
        total   = 0.0

        for past_logits in reversed(self._logit_history):
            probs = self._sigmoid(past_logits)
            for i, p in enumerate(probs):
                pc = (i + MIDI_OFFSET) % 12
                pc_hist[pc] += decay * p
            total += decay
            decay *= self.smooth_decay

        pc_hist /= (total + 1e-9)
        pc_hist /= (pc_hist.sum() + 1e-9)   # normalise to probability distribution

        # Score all 24 keys
        best_score = -1.0
        best_profile = KS_MAJOR   # default
        best_root    = 0

        for root in range(12):
            # Rotate profiles so index 0 = root
            maj_profile = np.roll(KS_MAJOR, root)
            min_profile = np.roll(KS_MINOR, root)

            maj_score = float(np.dot(pc_hist, maj_profile))
            min_score = float(np.dot(pc_hist, min_profile))

            if maj_score > best_score:
                best_score   = maj_score
                best_profile = maj_profile
                best_root    = root

            if min_score > best_score:
                best_score   = min_score
                best_profile = min_profile
                best_root    = root

        # Build per-note bias from KS profile weight at each note's pitch class
        # In-key notes: bias proportional to their KS weight (tonic > passing tone)
        # Out-of-key notes: mild uniform suppression
        bias = np.zeros(N_NOTES)
        for i in range(N_NOTES):
            pc       = (i + MIDI_OFFSET) % 12
            ks_weight = float(best_profile[pc])
            # KS weights range ~0.04–0.13 after normalisation
            # Scale so the tonic gets +key_strength and the least-likely pc gets ~0
            bias[i] = self.key_strength * (ks_weight / KS_MAJOR.max() - 0.4)

        # Normalise bias to not overwhelm the model signal
        bias_std = np.std(bias)
        if bias_std > 1e-6:
            bias = bias / bias_std * (np.std(note_logits) * 0.4)

        return note_logits + bias

    # -----------------------------------------------------------------------
    # Pre-processing step 3: Harmonic pruning
    # -----------------------------------------------------------------------

    def _harmonic_prune(self, note_logits: np.ndarray) -> np.ndarray:
        """
        Suppress semitone/wholetone clusters caused by model bleed.

        Algorithm:
        1. Convert logits to probabilities.
        2. Find all notes above a minimum activity threshold.
        3. Group them into clusters where any two members are within
           prune_radius semitones of each other (connected-component style).
        4. Within each cluster, keep only the strongest note. Suppress all
           others by pulling their logit down toward the background level.

        This is the right operation for guitar: adjacent-semitone clusters
        are almost never intentional voicings — they're the model firing on
        harmonics or spectral bleed. Real guitar chords have notes separated
        by at least a minor third (3 semitones) except in rare cases.

        We suppress rather than zero so the model can still override if
        it's genuinely very confident about an adjacent note.
        """
        probs = self._sigmoid(note_logits)
        result = note_logits.copy()

        # Only consider notes the model is somewhat active about
        active_threshold = 0.25
        active_indices = np.where(probs > active_threshold)[0]

        if len(active_indices) < 2:
            return result

        # Build clusters via connected components in semitone proximity
        # Two notes are in the same cluster if they are within prune_radius semitones
        clusters = []
        used     = set()

        for idx in active_indices:
            if idx in used:
                continue
            # Start a new cluster
            cluster = [idx]
            used.add(idx)
            # Grow: find any other active note within prune_radius
            for other in active_indices:
                if other in used:
                    continue
                # Check proximity to any member of the current cluster
                if any(abs(int(other) - int(member)) <= self.prune_radius
                       for member in cluster):
                    cluster.append(other)
                    used.add(other)
            clusters.append(cluster)

        # Within each cluster of size > 1, suppress all but the peak
        background_logit = float(np.percentile(note_logits, 25))

        for cluster in clusters:
            if len(cluster) < 2:
                continue

            # Find the strongest note in the cluster
            peak = max(cluster, key=lambda i: probs[i])

            # Check if this is actually a tight cluster worth pruning:
            # only prune if the gap between peak and neighbours is small
            # (i.e. it looks like bleed, not two genuinely separate notes)
            for member in cluster:
                if member == peak:
                    continue
                gap = float(probs[peak]) - float(probs[member])
                if gap < self.prune_threshold:
                    # Small gap → looks like bleed → suppress the weaker note
                    # Pull logit toward background rather than zeroing it
                    result[member] = (
                        0.3 * result[member] + 0.7 * background_logit
                    )

        return result

    # -----------------------------------------------------------------------
    # Thresholding and anchoring (improved from original)
    # -----------------------------------------------------------------------

    def _get_anchor_threshold(self, probs: np.ndarray):
        """
        Find the largest gap in the sorted probability distribution and place
        the threshold at the midpoint of that gap.

        Returns (threshold, gap_size) or (None, 0) if no meaningful gap.
        """
        s = np.sort(probs)
        if len(s) < 3:
            th = float(np.percentile(s, 80)) if len(s) > 0 else None
            return th, 0.0

        gaps = np.diff(s)
        i    = int(np.argmax(gaps))
        i    = min(i, len(s) - 2)
        th   = float((s[i] + s[i + 1]) / 2.0)

        if th < 0.45:
            return None, float(gaps[i])

        return th, float(gaps[i])

    # -----------------------------------------------------------------------
    # Combo generation (unchanged — it was correct)
    # -----------------------------------------------------------------------

    def _generate_combos(self, notes, strings, fretboard):
        notes = sorted([int(n) for n in notes])
        out   = []

        def backtrack(i, rem, cur):
            if i == len(notes):
                out.append(cur.copy())
                return
            n = notes[i]
            for s in rem:
                fret = n - fretboard[s][0]
                if 0 <= fret < len(fretboard[s]):
                    cur[i] = (s, int(fret))
                    backtrack(i + 1, [x for x in rem if x != s], cur)
                    del cur[i]

        backtrack(0, strings, {})
        return out

    def _get_possible_combos(self, note_logits, string_logits, prev_tab):
        n = self._sigmoid(note_logits)
        s = self._sigmoid(string_logits)

        ns, ng = self._get_anchor_threshold(n)
        ss, sg = self._get_anchor_threshold(s)

        if ns is None and ss is None:
            return []

        use_note = (ns is not None) and (ng > sg)
        out      = []

        for trial in range(2):
            s2 = s.copy()
            if trial == 1:
                s2[np.argmin(s2)] = -np.inf

            if use_note:
                anchors = [i + MIDI_OFFSET for i in np.where(n > ns)[0]]
                if not anchors:
                    continue
                for i in range(5):
                    strs = self._get_string_perm(i, s2, len(anchors))
                    out += self._generate_combos(anchors, strs, STANDARD_FRETBOARD)
            else:
                if ss is None:
                    continue
                strs = np.where(s2 > ss)[0]
                if len(strs) == 0:
                    continue
                for i in range(6):
                    notes = self._get_note_perm(i, n, len(strs))
                    out  += self._generate_combos(notes, list(strs), STANDARD_FRETBOARD)

        return out

    # -----------------------------------------------------------------------
    # Cost function (unchanged — it was correct)
    # -----------------------------------------------------------------------

    def _compute_combo_cost(self, combo, prev_tab):
        frets      = [v[1] for v in combo.values()]
        prev_frets = [v[1] for v in prev_tab] if prev_tab else []
        nz         = [f for f in frets if f > 0]

        stretch      = max(nz) - min(nz) if nz else 0
        stretch_cost = math.exp(stretch - 3) if stretch > 0 else 0

        move_cost = 0.0
        if prev_frets:
            move      = max(abs(max(frets) - min(prev_frets)),
                            abs(max(prev_frets) - min(frets)))
            move_cost = move * 1.5 if move <= 8 else 12 + math.log(move - 7)

        high_fret_cost = min(max(frets) * 0.3, 10.0) if frets else 0
        open_bonus     = (len(frets) - len(nz)) * 0.5

        return stretch_cost + move_cost + high_fret_cost - open_bonus

    def _choose_best_combo(self, combos, prev_tab):
        if not combos:
            return [], float("inf")
        best    = min(combos, key=lambda c: self._compute_combo_cost(c, prev_tab))
        cost    = self._compute_combo_cost(best, prev_tab)
        ordered = [best[k] for k in sorted(best.keys())]
        return ordered, cost

    # -----------------------------------------------------------------------
    # Permutation helpers (unchanged)
    # -----------------------------------------------------------------------

    def _get_string_perm(self, i, probs, k):
        idx = np.argsort(probs)[::-1]
        if i == 0:
            return list(idx[:k])
        pool = idx[:min(len(idx), k + 4)]
        return random.sample(list(pool), min(k, len(pool)))

    def _get_note_perm(self, i, probs, k):
        idx = np.argsort(probs)[::-1]
        if i == 0:
            sel = idx[:k]
        elif i == 1:
            sel = idx[:k + 1][:k]
        else:
            pool = idx[:min(len(idx), k + 8)]
            sel  = random.sample(list(pool), min(k, len(pool)))
        return [int(x) + MIDI_OFFSET for x in sel]

    # -----------------------------------------------------------------------
    # Utilities
    # -----------------------------------------------------------------------

    @staticmethod
    def _sigmoid(x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))

    @staticmethod
    def _to_numpy(note_logits, string_logits):
        try:
            import torch
            if isinstance(note_logits, torch.Tensor):
                note_logits = note_logits.detach().cpu().numpy()
            if isinstance(string_logits, torch.Tensor):
                string_logits = string_logits.detach().cpu().numpy()
        except ImportError:
            pass
        return np.asarray(note_logits).squeeze(), np.asarray(string_logits).squeeze()