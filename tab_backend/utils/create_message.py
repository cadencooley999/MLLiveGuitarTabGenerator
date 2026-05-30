def create_response(preds=None, notes=None, error=None, stream_end=False):
    return {
        "status": "error" if error else "stream_end" if stream_end else "success",
        "notes": notes or [],
        "string_preds": preds["strings"] if preds else [],
        "note_preds": preds["notes"] if preds else [],
        "error": error
    }