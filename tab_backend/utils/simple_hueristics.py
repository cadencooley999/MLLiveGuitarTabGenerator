import math
import random
import numpy as np
import torch


STANDARD_FRETBOARD = [
    list(range(40, 65)), list(range(45, 70)), list(range(50, 75)),
    list(range(55, 80)), list(range(59, 84)), list(range(64, 89))
]


def generate_combos(midi_notes, candidate_strings, fretboard):
    midi_notes = sorted(midi_notes)
    all_combos = []

    def backtrack(note_idx, remaining_strings, current_combo):
        if note_idx == len(midi_notes):
            all_combos.append(current_combo.copy())
            return
        note = midi_notes[note_idx]
        for string_idx in remaining_strings:
            if note in fretboard[string_idx]:
                fret = note - fretboard[string_idx][0]
                current_combo[note_idx] = (string_idx, fret)
                next_strings = [s for s in remaining_strings if s != string_idx]
                backtrack(note_idx + 1, next_strings, current_combo)
                del current_combo[note_idx]

    backtrack(0, candidate_strings, {})
    return all_combos


def compute_combo_cost(combo, prev_tab):
    frets = [v[1] for v in combo.values()]
    prev_frets = [v[1] for v in prev_tab]
    non_zero_frets = [f for f in frets if f > 0]
    stretch = max(non_zero_frets) - min(non_zero_frets) if non_zero_frets else 0
    stretch_cost = math.exp(stretch - 3) if stretch > 0 else 0
    move_cost = 0
    if prev_frets:
        move = max(abs(max(frets) - min(prev_frets)), abs(max(prev_frets) - min(frets)))
        move_cost = move * 1.5 if move <= 8 else 12 + math.log(move - 7)
    high_fret_cost = min(max(frets) * 0.3, 2.0)
    open_bonus = (len(frets) - len(non_zero_frets)) * 0.5
    return stretch_cost + move_cost + high_fret_cost - open_bonus


def choose_best_combo(combos, prev_tab):
    if not combos:
        return [], float("inf")
    best_combo = min(combos, key=lambda c: compute_combo_cost(c, prev_tab))
    best_cost = compute_combo_cost(best_combo, prev_tab)
    ordered = [best_combo[k] for k in sorted(best_combo.keys())]
    return ordered, best_cost


def get_anchor_threshold(
    probs,
    min_threshold=0.5,
    preferred_threshold=0.75,
    use_second_gap=True
):
    sorted_probs = np.sort(probs)
    gaps = np.diff(sorted_probs)

    if len(gaps) == 0:
        return None, 0

    # Sort gap indices from largest -> smallest
    sorted_gap_indices = np.argsort(gaps)[::-1]

    # Pick 2nd-largest gap if possible
    if use_second_gap and len(sorted_gap_indices) > 1:
        gap_idx = sorted_gap_indices[1]
    else:
        gap_idx = sorted_gap_indices[0]

    gap = gaps[gap_idx]

    threshold = max(
        (sorted_probs[gap_idx] + sorted_probs[gap_idx + 1]) / 2,
        sorted_probs[gap_idx + 1] - 0.01
    )

    if threshold < min_threshold:
        return None, 0

    return max(threshold, preferred_threshold), gap


def get_string_permutation(idx, probs, count):
    sorted_indices = np.argsort(probs)[::-1]
    if idx == 0:
        return list(sorted_indices[:count])
    pool = sorted_indices[:min(len(sorted_indices), count + 4)]
    return random.sample(list(pool), min(count, len(pool)))


def get_note_permutation(idx, probs, count):
    sorted_indices = np.argsort(probs)[::-1]
    if idx == 0:
        selected = sorted_indices[:count]
    elif idx == 1:
        selected = sorted_indices[:count + 1][:count]
    else:
        pool = sorted_indices[:min(len(sorted_indices), count + 8)]
        selected = random.sample(list(pool), min(count, len(pool)))
    return [i + 28 for i in selected]


def get_possible_combos(note_logits, string_logits, prev_tab, fretboard):
    all_combos = []
    n_probs = torch.sigmoid(torch.squeeze(torch.tensor(note_logits))).detach().cpu().numpy()
    s_probs = torch.sigmoid(torch.squeeze(torch.tensor(string_logits))).detach().cpu().numpy()
    s_thresh, s_gap = get_anchor_threshold(s_probs)
    n_thresh, n_gap = get_anchor_threshold(n_probs)
    if s_thresh is None and n_thresh is None:
        return []
    use_note_anchor = n_thresh is not None and n_gap > s_gap
    for remove_lowest in [False, True]:
        curr_s_probs = s_probs.copy()
        if remove_lowest:
            curr_s_probs[np.argmin(curr_s_probs)] = -np.inf
        if use_note_anchor:
            note_anchor = [n + 28 for n in np.where(n_probs > n_thresh)[0]]
            if not note_anchor:
                continue
            for p_idx in range(5):
                strings = get_string_permutation(p_idx, curr_s_probs, len(note_anchor))
                all_combos.extend(generate_combos(note_anchor, strings, fretboard))
        else:
            string_anchor = np.where(curr_s_probs > s_thresh)[0]
            if len(string_anchor) == 0:
                continue
            for p_idx in range(6):
                notes = get_note_permutation(p_idx, n_probs, len(string_anchor))
                all_combos.extend(generate_combos(notes, list(string_anchor), fretboard))
    return all_combos


def get_most_likely_tab(note_logits, string_logits, prev_tab, tuning="standard", max_cost=25):
    if tuning != "standard":
        raise ValueError("Only standard tuning supported")
    combos = get_possible_combos(note_logits, string_logits, prev_tab, STANDARD_FRETBOARD)
    if not combos:
        return []
    best_combo, best_cost = choose_best_combo(combos, prev_tab)
    return best_combo if best_cost <= max_cost else []


def print_tab(tab):
    for string_idx, fret in tab:
        print(f"String {6 - string_idx} | Fret {fret}")