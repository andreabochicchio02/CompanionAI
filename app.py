from app import create_app

#from app.services.rag import monitor_file_changes

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)  