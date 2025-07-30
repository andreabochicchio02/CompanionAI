from flask import Blueprint, render_template, jsonify, request
import os, json
import app.services.config as config

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

        return jsonify({"success": True, "message": events})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    
@bp.route('/dashboard/addNewEvent', methods=['POST'])
def add_new_event():
    try:
        new_event = request.get_json()

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