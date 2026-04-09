# LynxHealth
An app for Rhodes Health Center

## Running the App

Start from the project root:

### Windows

Use PowerShell:

```powershell
.\start.ps1
```

If PowerShell blocks the script, run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\start.ps1
```

What this script does:
- activates the Python virtual environment if `.venv` exists
- starts the frontend from `frontend`
- starts the FastAPI backend on `http://localhost:8000`

### macOS or Linux

```bash
./start.sh
```

If needed, make it executable first:

```bash
chmod +x ./start.sh
./start.sh
```

### First-time setup

If startup fails because dependencies are missing:

```bash
pip install -r requirements.txt
cd frontend
npm install
```

## Planning

[Google Drive](https://drive.google.com/drive/u/1/folders/1ygJ4fZOfbDO0bYAbOHXsf_lC90die02E)
[Trello](https://trello.com/invite/b/697001788efc1defe5a3c0e6/ATTIee4065e776be3bd7c7b64f4d1da0c7a9BC3157F0/comp486)

## Testing

### Backend unit tests
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run tests:
   ```bash
   pytest
   ```
