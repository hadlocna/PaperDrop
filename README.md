# PaperDrop

PaperDrop is a plug-and-play thermal printer that allows family members to send physical printed messages to loved ones at home.

## Architecture

- **Backend**: Node.js (Express) API with WebSocket support for real-time device communication.
- **Frontend**: React application for managing devices and sending messages.
- **Agent**: Python application running on Raspberry Pi to handle printing and cloud communication.

## Directory Structure

- `/backend`: Cloud API and WebSocket server
- `/frontend`: Web dashboard
- `/agent`: Device-side software

## Setup

See specific READMEs in each directory for setup instructions.
