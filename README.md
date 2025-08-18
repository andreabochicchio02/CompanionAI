# CompanionAI

CompanionAI is a prototype AI system designed to provide friendly companionship, adaptive support, and practical assistance — all while keeping your data private and fully offline. The project is built with *Flask* to showcase its features through a simple web application.

## Features

### 1. Friendly Companionship

Engage in warm, reassuring conversations that make you feel supported and less alone. The system is designed to respond naturally and provide a comforting presence.

### 2. Smart Adaptation

CompanionAI continuously learns from your interactions, adjusting to your habits, preferences, and emotional needs. Over time, it becomes more personalized and aligned with your lifestyle.

### 3. Event & Reminder Tracking

Stay on top of your daily life. CompanionAI remembers important events, medications, and appointments, sending reminders so you never miss what matters.

### 4. Family Access Dashboard

Relatives and caregivers can securely access a dedicated dashboard (example password: `1234`). From there, they can add personal details, schedule reminders, and review chat history to stay updated on the user’s wellbeing.

### 5. Works Completely Offline

All features are available without internet. No cloud services are involved — your data remains on your device only.

### 6. Guaranteed Privacy

Privacy is at the core of CompanionAI. Nothing is transmitted or shared; your conversations and personal information stay fully private.

---

## Project Structure

* All source code is inside the `app/` folder.
* The main entry point is `app.py`.

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/andreabochicchio02/CompanionAI.git
cd CompanionAI
```

### 2. Set Up Python Environment

Using a Conda environment with Python 3.11 is recommended:

```bash
conda create -n companionai python=3.11
conda activate companionai
```

### 3. Install Dependencies

Install all required packages from `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 4. Install and Configure Ollama

This project relies on [Ollama](https://ollama.ai/) to run local LLMs. Make sure it is installed and then download the models:

```bash
ollama pull llama3.2:3b
ollama pull gemma3:1b
```

### 5. Run the Application

Start Ollama, then launch the web app:

```bash
python app.py
```

### 6. Access the Web Application

Once running, open: [http://127.0.0.1:5000](http://127.0.0.1:5000)

You will find:

* **User Page**: chat directly with CompanionAI.
* **Family Dashboard**: access with password `1234` to add events, manage reminders, and view chat history.

## Notes

* The dashboard password is hardcoded as `1234` for demonstration only.
* All information is stored locally. Deleting the project folder will erase your data.

---

## License

This project is released under the MIT License.