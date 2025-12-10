#!/bin/bash

# Function to kill all background processes on exit
cleanup() {
    echo "Stopping all services..."
    kill $(jobs -p) 2>/dev/null
    exit
}

trap cleanup SIGINT SIGTERM

echo "🚀 Starting PaperDrop Development Environment..."

# Start Backend
echo "📦 Starting Backend on port 3000..."
cd backend
npm run dev &
BACKEND_PID=$!
cd ..

# Start Frontend
echo "🎨 Starting Frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

# Start Agent
echo "🤖 Starting Device Agent..."
cd agent
source venv/bin/activate
python3 agent.py &
AGENT_PID=$!
cd ..

echo "✅ All services started!"
echo "   - Backend: http://localhost:3000/health"
echo "   - Frontend: http://localhost:5173"
echo "   - Agent: Running in background"
echo "Press Ctrl+C to stop everything."

wait
