import json
import mimetypes
import os
import ssl
import threading
import uuid
import urllib.error
import urllib.request

import obspython as obs


SCRIPT_VERSION = "1.0.0"
SUPPORTED_GAMES = {"cod1", "cod2", "cod4"}

GAME_OPTIONS = [
    ("cod1", "Call of Duty 1"),
    ("cod2", "Call of Duty 2"),
    ("cod4", "Call of Duty 4"),
]

DEFAULT_BASE_URL = "https://codtube.tv"

script_settings = None
upload_in_progress = False
last_status = "Idle. Pick a clip, fill the fields, then upload."
pending_status = None
pending_clear_fields = False


def script_description():
    return (
        "<b>CoDTUBE OBS Uploader</b><br/>"
        "Version %s<br/>"
        "Upload clips directly from OBS with your CoDTUBE upload token.<br/><br/>"
        "Get your token in CoDTUBE Dashboard -> Profile settings -> OBS upload token."
        % SCRIPT_VERSION
    )


def script_defaults(settings):
    obs.obs_data_set_default_string(settings, "game", "cod1")
    obs.obs_data_set_default_bool(settings, "clear_after_upload", False)
    obs.obs_data_set_default_string(settings, "status", last_status)


def script_update(settings):
    global script_settings
    script_settings = settings
    _apply_status(last_status)


def script_load(settings):
    del settings
    # OBS UI updates behave more reliably when we flush queued changes on a short timer.
    obs.timer_add(_flush_ui_state, 250)


def script_unload():
    obs.timer_remove(_flush_ui_state)


def script_properties():
    props = obs.obs_properties_create()

    obs.obs_properties_add_text(props, "upload_token", "Upload token", obs.OBS_TEXT_PASSWORD)

    game_prop = obs.obs_properties_add_list(
        props,
        "game",
        "Game",
        obs.OBS_COMBO_TYPE_LIST,
        obs.OBS_COMBO_FORMAT_STRING,
    )
    for value, label in GAME_OPTIONS:
        obs.obs_property_list_add_string(game_prop, label, value)

    obs.obs_properties_add_text(props, "title", "Title", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(props, "mapname", "Map", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(props, "weapon", "Weapon", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(props, "tags", "Tags", obs.OBS_TEXT_DEFAULT)

    obs.obs_properties_add_path(
        props,
        "file_path",
        "Clip file",
        obs.OBS_PATH_FILE,
        "Video files (*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.ts *.mpeg *.mpg);;All files (*.*)",
        None,
    )

    obs.obs_properties_add_bool(props, "clear_after_upload", "Clear text fields after successful upload")
    obs.obs_properties_add_button(props, "upload_now", "Upload to CoDTUBE", _on_upload_clicked)
    obs.obs_properties_add_button(props, "reset_form", "Reset form", _on_reset_clicked)
    obs.obs_properties_add_text(props, "status", "Status", obs.OBS_TEXT_INFO)

    return props


def _get_str(settings, key):
    return obs.obs_data_get_string(settings, key).strip()


def _set_text_field(key, value):
    if script_settings is None:
        return
    obs.obs_data_set_string(script_settings, key, value)


def _set_bool_field(key, value):
    if script_settings is None:
        return
    obs.obs_data_set_bool(script_settings, key, value)


def _apply_status(message):
    global last_status
    last_status = message.strip() or "Idle."
    if script_settings is not None:
        obs.obs_data_set_string(script_settings, "status", last_status)
    obs.script_log(obs.LOG_INFO, "[CoDTUBE] %s" % last_status)


def _set_busy(is_busy):
    global upload_in_progress
    upload_in_progress = is_busy


def _queue_status(message):
    global pending_status
    pending_status = message.strip() or "Idle."


def _queue_clear_fields():
    global pending_clear_fields
    pending_clear_fields = True


def _flush_ui_state():
    global pending_status, pending_clear_fields

    if pending_status is not None:
        _apply_status(pending_status)
        pending_status = None

    if pending_clear_fields:
        _set_text_field("title", "")
        _set_text_field("mapname", "")
        _set_text_field("weapon", "")
        _set_text_field("tags", "")
        _set_text_field("file_path", "")
        pending_clear_fields = False


def _reset_form_fields():
    _set_text_field("title", "")
    _set_text_field("mapname", "")
    _set_text_field("weapon", "")
    _set_text_field("tags", "")
    _set_text_field("file_path", "")
    _set_bool_field("clear_after_upload", False)
    _apply_status("Form reset. Pick a clip, fill the fields, then upload.")


def _build_payload_from_settings():
    if script_settings is None:
        return None, "OBS script settings are not ready yet."

    # Keep the outgoing payload small and predictable so OBS side validation stays simple.
    payload = {
        "base_url": DEFAULT_BASE_URL,
        "upload_token": _get_str(script_settings, "upload_token"),
        "game": _get_str(script_settings, "game"),
        "title": _get_str(script_settings, "title"),
        "mapname": _get_str(script_settings, "mapname"),
        "weapon": _get_str(script_settings, "weapon"),
        "tags": _get_str(script_settings, "tags"),
        "file_path": _get_str(script_settings, "file_path"),
        "clear_after_upload": obs.obs_data_get_bool(script_settings, "clear_after_upload"),
    }
    error = _validate_payload(payload)
    if error:
        return None, error
    return payload, ""


def _start_upload(payload):
    _set_busy(True)
    _apply_status("Uploading clip to CoDTUBE...")
    # Run the upload in the background so the OBS script panel does not freeze.
    threading.Thread(target=_upload_worker, args=(payload,), daemon=True).start()


def _on_upload_clicked(props, prop):
    del props, prop

    if upload_in_progress:
        _apply_status("Upload already running. Please wait.")
        return False

    payload, error = _build_payload_from_settings()
    if error:
        _apply_status(error)
        return False

    _start_upload(payload)
    return False


def _on_reset_clicked(props, prop):
    del props, prop
    if upload_in_progress:
        _apply_status("Cannot reset while an upload is running.")
        return False
    _reset_form_fields()
    return False


def _validate_payload(data):
    if not data["upload_token"]:
        return "Missing upload token."
    if not data["title"]:
        return "Missing title."
    if data["game"] not in SUPPORTED_GAMES:
        return "Choose a valid game."
    if not data["file_path"]:
        return "Choose a clip file first."
    if not os.path.isfile(data["file_path"]):
        return "Selected clip file does not exist."
    return ""


def _upload_worker(data):
    try:
        result = _upload_clip(data)
        share_url = result.get("share_url") or ""
        status = result.get("status") or "unknown"
        message = "Upload complete. Server status: %s." % status
        if share_url:
            message += " %s" % _absolute_share_url(data["base_url"], share_url)
        _queue_status(message)

        if data.get("clear_after_upload"):
            _queue_clear_fields()
    except Exception as exc:
        _queue_status("Upload failed: %s" % exc)
    finally:
        _set_busy(False)


def _absolute_share_url(base_url, share_url):
    if share_url.startswith("http://") or share_url.startswith("https://"):
        return share_url
    if not share_url.startswith("/"):
        share_url = "/" + share_url
    return base_url + share_url


def _upload_clip(data):
    # These text fields match the regular CoDTUBE upload endpoint on the website.
    fields = {
        "game": data["game"],
        "title": data["title"],
        "playername": "OBS Upload",
        "tags": data["tags"],
        "mapname": data["mapname"],
        "weapon": data["weapon"],
    }
    boundary = "----CoDTUBEOBS%s" % uuid.uuid4().hex
    chunks = []

    def add_text(name, value):
        chunks.append(("--%s\r\n" % boundary).encode("utf-8"))
        chunks.append(('Content-Disposition: form-data; name="%s"\r\n\r\n' % name).encode("utf-8"))
        chunks.append((value or "").encode("utf-8"))
        chunks.append(b"\r\n")

    for key, value in fields.items():
        add_text(key, value)

    file_path = data["file_path"]
    filename = os.path.basename(file_path)
    mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    try:
        # Build one regular multipart/form data request so the backend can treat OBS uploads
        # the same way as browser uploads.
        chunks.append(("--%s\r\n" % boundary).encode("utf-8"))
        chunks.append(
            ('Content-Disposition: form-data; name="file"; filename="%s"\r\n' % filename).encode("utf-8")
        )
        chunks.append(("Content-Type: %s\r\n\r\n" % mime_type).encode("utf-8"))
        with open(file_path, "rb") as handle:
            while True:
                chunk = handle.read(256 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)

        chunks.append(b"\r\n")
        chunks.append(("--%s--\r\n" % boundary).encode("utf-8"))
        body = b"".join(chunks)

        request = urllib.request.Request(
            data["base_url"] + "/api/upload",
            data=body,
            method="POST",
            headers={
                "Content-Type": "multipart/form-data; boundary=%s" % boundary,
                "Content-Length": str(len(body)),
                "Accept": "application/json",
                "X-CoDTUBE-Upload-Token": data["upload_token"],
                "User-Agent": "CoDTUBE-OBS-Uploader/%s" % SCRIPT_VERSION,
            },
        )

        with urllib.request.urlopen(request, context=ssl.create_default_context(), timeout=300) as response:
            payload = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        text = err.read().decode("utf-8", "replace").strip()
        if text:
            raise RuntimeError("%s (%s)" % (text, err.code))
        raise RuntimeError("HTTP error %s" % err.code)
    except urllib.error.URLError as err:
        raise RuntimeError("Could not reach CoDTUBE: %s" % err.reason)
    except OSError as err:
        raise RuntimeError("Local file error: %s" % err)

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        raise RuntimeError("Unexpected server response.")

    # The API always replies with a small JSON envelope, even when the upload is rejected.
    if not data.get("ok"):
        raise RuntimeError(data.get("error") or "Upload was rejected.")
    return data
