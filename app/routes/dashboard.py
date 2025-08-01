from flask import Blueprint, render_template, jsonify, request
import os, json
import app.services.config as config
from datetime import datetime, time
import uuid

bp = Blueprint('dashboard', __name__)

@bp.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@bp.route('/dashboard/getEvents', methods=['POST'])
def get_events():
    try:
        if not os.path.exists(config.EVENTS_PATH):
            return jsonify({"success": False, "message": "Events file not found."})

        with open(config.EVENTS_PATH, 'r', encoding='utf-8') as f:
            events = json.load(f)

        filtered_events = [event for event in events if keep_event(event)]

        with open(config.EVENTS_PATH, 'w', encoding='utf-8') as f:
            json.dump(filtered_events, f, indent=2)

        return jsonify({"success": True, "message": filtered_events})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    
@bp.route('/dashboard/addNewEvent', methods=['POST'])
def add_new_event():
    try:
        new_event = request.get_json()
        new_event['id'] = str(uuid.uuid4())

        if not new_event:
            return jsonify({"success": False, "message": "No data received"})

        # Load existing events
        if os.path.exists(config.EVENTS_PATH):
            with open(config.EVENTS_PATH, 'r', encoding='utf-8') as f:
                events = json.load(f)
        else:
            events = []

        # Add new event
        events.append(new_event)

        # Save back to file
        with open(config.EVENTS_PATH, 'w', encoding='utf-8') as f:
            json.dump(events, f, ensure_ascii=False, indent=2)

        return jsonify({"success": True, "message": "Event added successfully"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    
@bp.route('/dashboard/getParagraphs', methods=['POST'])
def get_paragraphs():
    try:
        with open('document.txt', 'r', encoding='utf-8') as f:
            content = f.read()

        raw_paragraphs = content.strip().split('\n\n\n')
        paragraphs = []

        for p in raw_paragraphs:
            lines = p.strip().split('\n', 1)
            title = lines[0].strip()
            body = lines[1].strip()
            paragraphs.append({
                "title": title,
                "content": body
            })

        return jsonify({"success": True, "message": paragraphs})

    except Exception as e:
        return jsonify({"success": False, "message": f"Errore durante la lettura del file: {str(e)}"}), 500
    

@bp.route('/dashboard/saveParagraphs', methods=['POST'])
def save_paragraphs():
    try:
        data = request.get_json()
        paragraphs = data.get('paragraphs', [])

        if not paragraphs:
            return jsonify({"success": False, "message": "No paragraphs provided."}), 400

        with open('document.txt', 'w', encoding='utf-8') as f:
            for p in paragraphs:
                title = p.get('title', '').strip()
                content = p.get('content', '').strip()
                if title and content:
                    f.write(f"{title}\n{content}\n\n\n")

        return jsonify({"success": True, "message": "Document saved successfully."})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@bp.route('/dashboard/deleteEvent', methods=['POST'])
def delete_event():
    data = request.get_json()
    event_id = data.get('id')

    if not event_id:
        return jsonify({'error': 'No ID provided'})

    # Load events from file
    if not os.path.exists(config.EVENTS_PATH):
        return jsonify({'error': 'Events file not found'})

    with open(config.EVENTS_PATH, 'r') as f:
        try:
            events = json.load(f)
        except json.JSONDecodeError:
            return jsonify({'error': 'Invalid JSON format'}), 500

    # Filter out the event
    updated_events = [event for event in events if event.get('id') != event_id]

    # Save updated events
    with open(config.EVENTS_PATH, 'w') as f:
        json.dump(updated_events, f, indent=2)

    return jsonify({'success': True}), 200


def keep_event(event):
    now = datetime.now()
    date_str = event.get("date")
    recurrence = event.get("recurrence")

    if 'T' in date_str:
        event_date = datetime.fromisoformat(date_str)
    else:
        event_date = datetime.fromisoformat(date_str)
        event_date = datetime.combine(event_date.date(), time(23, 59, 59))

    event_date = datetime.fromisoformat(date_str)

    if event_date >= now:
        return True

    if not recurrence:
        return False

    end_str = recurrence.get("end")
    if end_str:
        if 'T' in date_str:
            end_date = datetime.fromisoformat(date_str)
        else:
            end_date = datetime.fromisoformat(date_str)
            end_date = datetime.combine(end_date.date(), time(23, 59, 59))
        if end_date < now:
            return False
        else:
            return True
    else:
        return True