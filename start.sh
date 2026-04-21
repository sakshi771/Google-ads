#!/bin/bash
# Start both backend and frontend in one command
# Usage: ./start.sh

cd "$(dirname "$0")"

# Kill any leftover processes from previous runs
kill $(lsof -ti:8000) 2>/dev/null
kill $(lsof -ti:5173) 2>/dev/null
sleep 1

echo "Starting backend (port 8000)..."
cd backend
../venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

echo "Starting frontend (port 5173)..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "Dashboard running at: http://localhost:5173"
echo "Press Ctrl+C to stop both servers"

# Stop both when Ctrl+C is pressed
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
