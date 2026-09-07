"""
Combined STT + tone/cadence analysis route. Deliberately isolated from
tts_routes.py and lazy-loaded — this depends on Whisper/librosa/
sentence-transformers, which your environment's startup log showed as
missing. A failure here must never take down TTS or the rest of the app.

Register in app.py with:
    from audio_routes import audio_bp
    app.register_blueprint(audio_bp)
"""
from __future__ import annotations
from flask import Blueprint, request, jsonify
import tempfile
import os
import logging

logger = logging.getLogger(__name__)
audio_bp = Blueprint("audio_process", __name__, url_prefix="/audio")

_processor = None


def _get_processor():
    global _processor
    if _processor is None:
        from audio_processor import InterviewAudioProcessor
        # "small" gives meaningfully better accent/accent-drift robustness
        # than "base" for a modest speed cost — see audio_processor.py docstring.
        _processor = InterviewAudioProcessor(model_size="small")
    return _processor


@audio_bp.route("/process", methods=["POST"])
def process_answer():
    if "audio" not in request.files:
        return jsonify({"error": "no audio file uploaded"}), 400

    audio_file = request.files["audio"]
    question = request.form.get("question", "")
    topic = request.form.get("topic", "")
    reference_answer = request.form.get("reference_answer") or None
    user_id = request.form.get("user_id", "default")
    time_to_first_sound = request.form.get("time_to_first_sound", type=float)

    suffix = os.path.splitext(audio_file.filename or "")[1] or ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        audio_file.save(tmp.name)
        tmp_path = tmp.name

    try:
        try:
            processor = _get_processor()
        except Exception as e:
            logger.error(f"Audio processor unavailable: {e}", exc_info=True)
            return jsonify({
                "error": f"Voice processing is unavailable: {e}",
                "terminated": False,
                "transcript": "",
            }), 503  # service unavailable, not a hard 500 -- distinguishable client-side

        result = processor.process(
            tmp_path,
            reference_context=reference_answer,
            time_to_first_sound=time_to_first_sound,
        )

        from session_guard import check_and_enforce, SessionTerminated
        try:
            check_and_enforce(result, user_id=user_id, question=question, topic=topic)
        except SessionTerminated as e:
            return jsonify({
                "terminated": True,
                "reason": e.reason,
                "details": e.details,
            }), 200

        return jsonify({
            "terminated": False,
            "transcript": result["transcript"],
            "is_cheating": result["is_cheating"],
            "suspicion_score": result["suspicion_score"],
            "is_scripted": result.get("is_scripted", False),
            "scripted_score": result.get("scripted_score", 0.0),
            "metrics": result.get("metrics", {}),
        })
    finally:
        os.unlink(tmp_path)
