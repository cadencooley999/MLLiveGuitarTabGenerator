import torch

def tabs_to_front(likely_tab):

    #tabs = [(), ()]

    notes = [
        {"string": int(t[0]), "fret": int(t[1])}
        for t in likely_tab
    ]

    return {"notes" : notes}

def make_preds_json(note_preds, string_preds):
    note_preds = note_preds
    string_preds = string_preds

    return {"notes" : note_preds, "strings": string_preds}