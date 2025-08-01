from app import create_app
import threading

#from app.services.rag import monitor_file_changes

app = create_app()

if __name__ == "__main__":
    # uncomment - Avvia il monitoraggio dei file
    #threading.Thread(target=monitor_file_changes, daemon=True).start()
    app.run(debug=True, use_reloader=False)  