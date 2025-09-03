from flask import Blueprint, render_template, jsonify, request
from app.services.rag import create_structured_info, update_file_hashes, update_db
import os, json
import app.services.config as config
import app.services.utils as utils
import uuid
import threading

bp = Blueprint('dashboard', __name__)

@bp.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@bp.route('/dashboard/getEvents', methods=['POST'])
def get_events():
    '''Fetches events from the events file.'''
    try:
        if not os.path.exists(config.EVENTS_PATH):
            return jsonify({"success": False, "message": "Events file not found."})

        with open(config.EVENTS_PATH, 'r', encoding='utf-8') as f:
            events = json.load(f)

        filtered_events = [event for event in events if utils.keep_event(event)]

        with open(config.EVENTS_PATH, 'w', encoding='utf-8') as f:
            json.dump(filtered_events, f, indent=2)

        return jsonify({"success": True, "message": filtered_events})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    
@bp.route('/dashboard/addNewEvent', methods=['POST'])
def add_new_event():
    '''Adds a new event to the events file.'''
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
    '''Fetches paragraphs from the personal_info.txt file.'''
    try:
        with open('app/resources/personal_info.txt', 'r', encoding='utf-8') as f:
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

        return jsonify({"success": True, "message": paragraphs, "userReliable": config.USER_RELIABLE})

    except Exception as e:
        return jsonify({"success": False, "message": f"Errore durante la lettura del file: {str(e)}"}), 500
    

@bp.route('/dashboard/saveParagraphs', methods=['POST'])
def save_paragraphs():
    '''Saves paragraphs to the personal_info.txt file and updates structured info.'''
    try:
        data = request.get_json()
        paragraphs = data.get('paragraphs', [])
        reliable = bool(data.get('reliable', False))
        config.set_user_reliable(reliable)

        if not paragraphs:
            return jsonify({"success": False, "message": "No paragraphs provided."}), 400

        with open('app/resources/personal_info.txt', 'w', encoding='utf-8') as f:
            for p in paragraphs:
                title = p.get('title', '').strip()
                content = p.get('content', '').strip()
                if title and content:
                    f.write(f"{title}\n{content}\n\n\n")

        def background_processing():
            try:
                utils.append_server_log("Starting background processing...")
                create_structured_info()  # Lento
                update_db()               # Molto lento
                update_file_hashes()      # Veloce
                utils.append_server_log("Background processing completed successfully")
            except Exception as e:
                utils.append_server_log(f"Background processing failed: {e}")
        
        thread = threading.Thread(target=background_processing)
        thread.daemon = True
        thread.start()

        return jsonify({
            "success": True, 
            "message": "Document saved successfully. Processing in background..."
        })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@bp.route('/dashboard/deleteEvent', methods=['POST'])
def delete_event():
    '''Deletes an event by ID from the events file.'''
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